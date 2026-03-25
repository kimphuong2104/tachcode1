# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
These plugins can be used to filter or enhance BOM queries see :ref:`enhancement_api`.
"""

# Exported objects
__all__ = [
    "FilterFunctionPlugin",
    "EffectivityDatesPlugin",
    "SiteBomAttributePlugin",
    "ComponentJoinPlugin",
]

import logging
from datetime import datetime
from typing import Callable, Any, Optional, Self

import cdbwrapc

from cdb import util
from cdb.sqlapi import Record
from cdb.objects.org import Organization
from cs.platform.web.rest.generic import convert

from cs.vp.bom import AssemblyComponent
from cs.vp.bom.enhancement.plugin import AbstractRestPlugin, Dependencies
from cs.vp.bom.web.bommanager.utils import (
    SiteFilterPurpose,
    site_bom_filter,
    get_site_bom_filter_class,
)
from cs.vp.utils import get_sql_row_limit, parse_url_query_args

LOG = logging.getLogger(__name__)


class FilterFunctionPlugin(AbstractRestPlugin):
    """
    REST plugin which uses a function to filter the product structure results.
    This filter is done after SQL query on the result list.

    .. note::
        If performance is important filter with SQL extension should be preferred.

    :param function_reference: reference to a function which gets a single argument
                               `bom_item_records` (list[:class:`cdb.sqlapi.Record`]) and
                               has to return the filtered list of these records

    :return: a constructed :class:`cs.vp.bom.bomqueries_plugin.FilterFunctionPlugin` object
    """


    def __init__(self, function_reference: Callable[..., Any]) -> None:
        self.function_reference: Callable[..., Any] = function_reference
        """
        Reference to the provided function
        """

    def filter_bom_item_records(self, bom_item_records: Any) -> Any:
        return self.function_reference(bom_item_records)


class EffectivityDatesPlugin(AbstractRestPlugin):
    """
    Filter plugin which filters based on effectivity dates
    `valid_from` and `valid_to` for `bom_item` and **also** optionally for `part`.
    This plugin filters with SQL extensions.

    :keyword valid_to: datetime for filter
    :keyword valid_from: datetime for filter

    :return: a constructed :class:`cs.vp.bom.bomqueries_plugin.EffectivityDatesPlugin` object
    """

    DISCRIMINATOR = "cs.vp.effectivityDatesFilter"

    def __init__(
        self,
        valid_to: Optional[datetime] = None,
        valid_from: Optional[datetime] = None,
        *args: Any,
        **kwargs: Any
    ) -> None:
        super().__init__()
        if valid_to is None and valid_from is None:
            raise ValueError("valid_to and/or valid_from has to be set")

        if valid_from and not valid_to:
            valid_to = valid_from
        if valid_to and not valid_from:
            valid_from = valid_to

        self.valid_to = valid_to
        self.valid_from = valid_from

    @classmethod
    def create_from_rest_data(
        cls, rest_data: Optional[Any], dependencies: Dependencies
    ) -> Optional[Self]:
        if rest_data is None:
            return None

        valid_from, valid_to = get_validity_dates(rest_data)
        return cls(valid_to=valid_to, valid_from=valid_from)

    def get_bom_item_where_stmt_extension(self) -> Optional[str]:
        result = []

        if self.valid_from:
            valid_from_stmt = f"({self.BOM_ITEM_TABLE_ALIAS}.ce_valid_to is Null"
            valid_from_stmt += f" OR {self.BOM_ITEM_TABLE_ALIAS}.ce_valid_to " \
                               f">= {cdbwrapc.SQLdate_literal(self.valid_from)})"

            result.append(valid_from_stmt)

        if self.valid_to:
            valid_to_stmt = f"({self.BOM_ITEM_TABLE_ALIAS}.ce_valid_from is Null"
            valid_to_stmt += f" OR {self.BOM_ITEM_TABLE_ALIAS}.ce_valid_from " \
                             f"<= {cdbwrapc.SQLdate_literal(self.valid_to)})"
            
            result.append(valid_to_stmt)

        return " AND ".join(result) if result else None


def convert_date(plugin_data, date_key: Any) -> Any:
    date_str = plugin_data.get(date_key)
    if date_str:
        try:
            return convert.load_datetime(date_str)
        except convert.LoadConversionError:
            LOG.exception(
                "Could not convert {} date: {}, ignoring it for BOM filtering".format(
                    date_key, date_str
                )
            )
    return None


def get_validity_dates(plugin_data: Any) -> Any:
    return convert_date(plugin_data, "validFrom"), convert_date(plugin_data, "validTo")


class SiteBomAttributePlugin(AbstractRestPlugin):
    """
    data plugin for 'site'
    """

    DISCRIMINATOR = "cs.vp.siteBomAttributePlugin"

    def __init__(self, site_object_id: str):
        if site_object_id is None:
            raise ValueError("site_object_id is needed")

        self.site_object_id = site_object_id

    @classmethod
    def create_from_rest_data(
        cls, rest_data: Optional[Any], dependencies: Dependencies
    ) -> Optional[Self]:
        if rest_data is None:
            return None

        site_object_id = rest_data.get("cdb_object_id", None)

        try:
            return cls(site_object_id)
        except ValueError:
            return None

    @classmethod
    def create_for_default_data(
        cls,
        dependencies: Dependencies,
        *,
        instance_name: str | None = None,
        **kwargs: Any
    ) -> Optional[Self]:
        # special for instance_name (xbom)
        # only load default values for the right bomtable
        # only the right bomtable ist filtered
        if instance_name != "bommanager_right":
            return None
        bom_table_url = kwargs.get("bom_table_url")
        url_query_args = parse_url_query_args(bom_table_url)

        site_id = url_query_args.get("site", None)
        if site_id is None:
            return None

        return cls(site_id)

    def get_default_data(self) -> Any:
        if self.site_object_id is None:
            return None
        org = Organization.ByKeys(cdb_object_id=self.site_object_id)
        if org is None:
            # todo: E070958 non existing site in url - logging / error?
            return None

        return (
            {
                "cdb_object_id": self.site_object_id,
                "system:description": org.GetDescription(),
            },
            None,
        )


class Site2BomAttributePlugin(SiteBomAttributePlugin):
    """data plugin for 'site2'"""

    DISCRIMINATOR = "cs.vp.site2BomAttributePlugin"

    @classmethod
    def create_for_default_data(
        cls,
        dependencies: Dependencies,
        *,
        instance_name: str | None = None,
        **kwargs: Any
    ) -> Optional[Self]:
        # special for instance_name (xbom)
        # only load default values for the right bomtable
        # only the right bomtable ist filtered
        if instance_name != "bommanager_right":
            return None
        bom_table_url = kwargs.get("bom_table_url")
        url_query_args = parse_url_query_args(bom_table_url)

        site_id = url_query_args.get("site2", None)
        if site_id is None:
            return None

        return cls(site_id)


class SiteBomAdditionalAttrFilterPlugin(AbstractRestPlugin):
    """The logic for the site handling

    Add `from_other_site` attribute for BomTable usage.
    """

    DISCRIMINATOR = "cs.vp.siteBomFilterPlugin"
    DEPENDENCIES = (SiteBomAttributePlugin, Site2BomAttributePlugin)

    def __init__(
        self,
        site_plugin: Optional[SiteBomAttributePlugin] = None,
        site2_plugin: Optional[Site2BomAttributePlugin] = None,
    ):
        self.site_plugin: Optional[SiteBomAttributePlugin] = site_plugin
        self.site2_plugin: Optional[Site2BomAttributePlugin] = site2_plugin

    @classmethod
    def create_from_rest_data(
        cls, rest_data: Optional[Any], dependencies: Dependencies
    ) -> Optional[Self]:
        site: SiteBomAttributePlugin = dependencies[SiteBomAttributePlugin]
        site2: Site2BomAttributePlugin = dependencies[Site2BomAttributePlugin]
        return cls(site, site2)

    def get_additional_bom_item_attributes(
        self, bom_item_record: Record
    ) -> Optional[dict[Any, Any]]:
        """
        Add `from_other_site` attribute for BomTable usage.

        :param function_reference: reference to a function which has to set attribute
                                   `_from_other_site` on records

        :return: a constructed :class:`cs.vp.bom.bomqueries_plugin.SiteBomAttributePlugin` object
        """
        return {
            "from_other_site": getattr(bom_item_record, "_from_other_site", False),
            "site_transparency_behavior": get_site_bom_filter_class().get_other_site_transparency_behavior(),
        }


class SiteBomPurposeLoadPlugin(SiteBomAdditionalAttrFilterPlugin):
    DISCRIMINATOR = "cs.vp.siteBomPurposePlugin"
    PURPOSE = SiteFilterPurpose.LOAD_TREE_DATA

    def get_selected_sites(self) -> list[str]:
        result = []

        if self.site_plugin is not None:
            result.append(self.site_plugin.site_object_id)
        if self.site2_plugin is not None:
            result.append(self.site2_plugin.site_object_id)

        return result

    def filter_bom_item_records(self, bom_item_records: list[Record]) -> list[Record]:
        return site_bom_filter(
            bom_item_records,
            selected_sites=self.get_selected_sites(),
            purpose=self.PURPOSE,
        )


class SiteBomPurposeSyncPlugin(SiteBomPurposeLoadPlugin):
    PURPOSE = SiteFilterPurpose.SYNC_VIEW


class SiteBomPurposeFindDifferencePlugin(SiteBomPurposeLoadPlugin):
    PURPOSE = SiteFilterPurpose.FIND_DIFFERENCE


class SiteBomPurposeLoadDiffTablePlugin(SiteBomPurposeLoadPlugin):
    PURPOSE = SiteFilterPurpose.LOAD_DIFF_TABLE_DATA


class ComponentJoinPlugin(AbstractRestPlugin):
    """
    Plugin that implements the BomItem component join. The default ComponentJoinPlugin used to query the
    product structure is 'as_saved'.
    Only one ComponentJoinPlugin is supported to query the product structure.

    :keyword imprecise_view: supported views are "as_saved", "latest_working", "latest_released" and "released_at".
        if no date is given for released_at view than the actual date is taken which means latest_released.

    :return: a constructed :class:`cs.vp.bom.bomqueries_plugin.ComponentJoinPlugin` object
    """

    DISCRIMINATOR = "cs.vp.ComponentJoinPlugin"

    def __init__(
        self, imprecise_view: Optional[str] = "", release_date: Optional[datetime] = None) -> None:
        super().__init__()
        self.imprecise_view = imprecise_view
        self.release_date = release_date if release_date else datetime.utcnow()

    @classmethod
    def create_from_rest_data(cls, rest_data: Optional[Any], dependencies: Dependencies) -> Optional[Self]:
        if rest_data is None:
            return None

        return cls(
            imprecise_view=rest_data.get("imprecise_view", ""),
            release_date=convert_date(rest_data, "release_date")
        )

    @classmethod
    def create_for_default_data(cls, dependencies: Dependencies, **kwargs: Any) -> Optional[Self]:
        return cls(imprecise_view='latest_working')

    def get_default_data(self) -> tuple[Any, Any]:
        if AssemblyComponent.get_bom_mode() == AssemblyComponent.BOM_MODE_PRECISE:
            return None, None
        default_data = {
            'imprecise_view': self.imprecise_view,
            'release_date': str(self.release_date)
        }
        return default_data, default_data

    def get_sql_join_stmt_extension(self) -> Optional[str]:
        if self.imprecise_view == "as_saved":
            join_condition = f"{self.BOM_ITEM_TABLE_ALIAS}.t_index"
        elif self.imprecise_view == "latest_working":
            join_condition = f"""
                CASE WHEN {self.BOM_ITEM_TABLE_ALIAS}.is_imprecise = 1
                    THEN (
                        SELECT t_index FROM teile_stamm 
                        WHERE teilenummer = {self.BOM_ITEM_TABLE_ALIAS}.teilenummer 
                        AND ce_valid_from = (
                            SELECT MAX(ce_valid_from) FROM teile_stamm 
                            WHERE teilenummer = {self.BOM_ITEM_TABLE_ALIAS}.teilenummer
                        )
                    )
                    ELSE {self.BOM_ITEM_TABLE_ALIAS}.t_index
                END
            """
        elif self.imprecise_view in ("latest_released", "released_at", "as_released"):
            if not self.release_date and not self.imprecise_view == "latest_released":
                raise ValueError(f"release date required for imprecise view {self.imprecise_view}")
            release_date = cdbwrapc.SQLdate_literal(
                datetime.utcnow() if self.imprecise_view == "latest_released" else self.release_date
            )
            select_limit, where_limit = get_sql_row_limit()
            join_condition = f"""
                CASE WHEN {self.BOM_ITEM_TABLE_ALIAS}.is_imprecise = 1
                    THEN (
                        SELECT {select_limit} CASE
                            WHEN (
                                SELECT {select_limit} t_index FROM teile_stamm
                                WHERE teilenummer = {self.BOM_ITEM_TABLE_ALIAS}.teilenummer
                                AND ce_valid_from <= {release_date}
                                AND (ce_valid_to > {release_date} OR ce_valid_to is Null)
                                {where_limit}
                            ) IS NULL THEN (
                                SELECT t_index FROM teile_stamm 
                                WHERE teilenummer = {self.BOM_ITEM_TABLE_ALIAS}.teilenummer 
                                AND ce_valid_from = (
                                    SELECT MAX(ce_valid_from) FROM teile_stamm 
                                    WHERE teilenummer = {self.BOM_ITEM_TABLE_ALIAS}.teilenummer
                                )
                            )
                            ELSE (
                                SELECT t_index FROM teile_stamm 
                                WHERE teilenummer = {self.BOM_ITEM_TABLE_ALIAS}.teilenummer
                                AND ce_valid_from <= {release_date}
                                AND (ce_valid_to > {release_date} OR ce_valid_to is Null)
                            )
                            END AS t_index
                        FROM teile_stamm 
                        WHERE teile_stamm.teilenummer = {self.BOM_ITEM_TABLE_ALIAS}.teilenummer
                        {where_limit}                    
                    )
                    ELSE {self.BOM_ITEM_TABLE_ALIAS}.t_index
                END
            """
        else:
            raise ValueError(f"view type '{self.imprecise_view}' not supported")
        return f"""
            LEFT JOIN teile_stamm {self.COMPONENT_TABLE_ALIAS} ON 
                {self.COMPONENT_TABLE_ALIAS}.teilenummer={self.BOM_ITEM_TABLE_ALIAS}.teilenummer AND
                {self.COMPONENT_TABLE_ALIAS}.t_index={join_condition}
        """

    def resolve_bom_item_children(self, bom_item_record: Record) -> bool:
        return bom_item_record.baugruppenart == "Baugruppe"
