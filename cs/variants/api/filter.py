#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
import logging
from collections import defaultdict
from typing import Any, Optional, Self

from morepath import Request
from webob import exc

from cdb.objects import IconCache
from cdb.sqlapi import Record
from cs.classification import api as classification_api
from cs.platform.web.rest import get_collection_app
from cs.platform.web.rest.support import get_object_from_rest_name
from cs.platform.web.root.main import _get_dummy_request
from cs.variants import VariabilityModel, Variant
from cs.variants.api.selection_condition import SelectionConditionEvaluator
from cs.variants.classification_helper import ensure_existence_of_float_normalize
from cs.variants.web.common import update_app_setup
from cs.vp.bom.enhancement.plugin import (
    AbstractPlugin,
    AbstractRestPlugin,
    Dependencies,
)
from cs.vp.bom.web.filter import add_group_component_for_filter_plugin
from cs.vp.items import Item
from cs.vp.utils import parse_url_query_args
from cs.web.components.base.main import SettingDict
from cs.web.components.ui_support.outlets import OutletConfig

INSTANCE_NAME_VARIANT_STRUCTURE = (
    "cs-variants-web-common-INSTANCE_NAME_VARIANT_STRUCTURE"
)


class PropertiesBasedVariantFilter:
    def __init__(
        self, variability_model_id, classification_data, ignore_not_set_properties=True
    ):
        self.classification_data = classification_data
        self.ignore_not_set_properties = ignore_not_set_properties

        self.selection_condition_evaluator = SelectionConditionEvaluator(
            variability_model_id=variability_model_id,
            properties=classification_data,
        )

    def has_selection_condition(self, bom_item):
        return self.selection_condition_evaluator.has_selection_condition(bom_item)

    def eval_bom_item(self, bom_item):
        """
        Apply filter to bom item.

        :returns: `True` if the bom position is in the filtered product structure for
            the variant, `False` otherwise.
        """
        return self.selection_condition_evaluator(
            ref_object=bom_item,
            ignore_not_found_selection_condition=True,
            ignore_not_set_properties=self.ignore_not_set_properties,
        )

    def eval_amount_of_filtered_bom_item_occurrences(self, bom_item_occurrence_ids):
        filtered_bom_item_occurrences = 0
        for each in bom_item_occurrence_ids:
            if not self.selection_condition_evaluator(
                ref_object_id=each,
                ignore_not_found_selection_condition=True,
                ignore_not_set_properties=self.ignore_not_set_properties,
            ):
                filtered_bom_item_occurrences += 1

        return filtered_bom_item_occurrences


class VariantFilter(PropertiesBasedVariantFilter):
    """
    A filter object for a saved variant to be used with the methods from cs.vp
    """

    def __init__(self, variant, ignore_not_set_properties=False):
        self.classification = classification_api.get_classification(
            variant, narrowed=False
        )

        super().__init__(
            variant.variability_model_id,
            self.classification["properties"],
            ignore_not_set_properties=ignore_not_set_properties,
        )


class CsVariantsVariabilityModelContextPlugin(AbstractRestPlugin):
    DISCRIMINATOR = "cs.variants.variabilityModelContext"

    def __init__(
        self, variability_model_id: str, set_as_reset_data: bool = False
    ) -> None:
        if variability_model_id is None:
            raise ValueError("Need a variability_model_id")

        self.variability_model_id = variability_model_id
        self.set_as_reset_data = set_as_reset_data

    @staticmethod
    def get_variability_model_id_from_rest_data(rest_data: Any) -> Any:
        return rest_data["variability_model_id"]

    @classmethod
    def create_for_default_data(
        cls, dependencies: Dependencies, **kwargs: Any
    ) -> Optional[Self]:
        instance_name = kwargs.get("instance_name", "")
        additional_data = kwargs.get("additional_data", {})

        variability_model_id = None
        set_as_reset_data = False

        if instance_name.startswith("bom-table-with-details-instance-"):
            root_item_cdb_object_id = kwargs.get("root_item_cdb_object_id")
            root_item = Item.ByKeys(cdb_object_id=root_item_cdb_object_id)
            if root_item is None:
                return None

            if len(root_item.VariabilityModels) == 1:
                variability_model_id = root_item.VariabilityModels[0].cdb_object_id
                set_as_reset_data = True

        elif instance_name == INSTANCE_NAME_VARIANT_STRUCTURE:
            variability_model_id = additional_data["variabilityModelId"]

        if variability_model_id is None:
            bom_table_url = kwargs.get("bom_table_url")
            if bom_table_url:
                url_query_args = parse_url_query_args(bom_table_url)
                variability_model_id = url_query_args.get("variabilityModel", None)

        if variability_model_id is None:
            return None

        return cls(variability_model_id, set_as_reset_data=set_as_reset_data)

    @classmethod
    def create_from_rest_data(
        cls, rest_data: Optional[Any], dependencies: Dependencies
    ) -> Optional[Self]:
        if not isinstance(rest_data, dict) or "variability_model_id" not in rest_data:
            return None

        variability_model_id = cls.get_variability_model_id_from_rest_data(rest_data)
        return cls(variability_model_id)

    def get_default_data(self) -> Any:
        variability_model = VariabilityModel.ByKeys(
            cdb_object_id=self.variability_model_id
        )
        if variability_model is None:
            return None, None

        initial_data = {
            "variability_model_id": self.variability_model_id,
            "system:description": variability_model.GetDescription(),
        }
        reset_data = initial_data if self.set_as_reset_data else None

        return initial_data, reset_data


def get_variant_filter(
    variability_model_cdb_object_id: str,
    variant_id: int,
    classification_properties: dict,
) -> PropertiesBasedVariantFilter:
    if variant_id is None and classification_properties is None:
        raise ValueError("variant_id **or** classification_properties is needed")

    if variant_id is not None and classification_properties is not None:
        raise ValueError(
            "Only variant_id **or** classification_properties is supported"
        )

    if variant_id is not None:
        variant = Variant.ByKeys(
            variability_model_id=variability_model_cdb_object_id,
            id=variant_id,
        )

        if variant is None:
            raise exc.HTTPNotFound(
                f"Not able to find variant with id '{variant_id}' and "
                f"variability_model_id '{variability_model_cdb_object_id}'"
            )

        return variant.make_variant_filter()

    elif classification_properties is not None:
        ensure_existence_of_float_normalize(classification_properties)
        return PropertiesBasedVariantFilter(
            variability_model_cdb_object_id, classification_properties
        )


class CsVariantsFilterContextPlugin(AbstractRestPlugin):
    DISCRIMINATOR = "cs.variants.variantFilterContext"
    DEPENDENCIES = (CsVariantsVariabilityModelContextPlugin,)

    def __init__(
        self,
        variability_model_context_plugin: CsVariantsVariabilityModelContextPlugin,
        variant_id: Optional[int] = None,
        classification_properties: Optional[dict] = None,
    ) -> None:
        self.variability_model_context_plugin = variability_model_context_plugin
        self.variant_id = variant_id
        self.classification_properties = classification_properties
        self._variant_filter = None
        self.request = None

    @staticmethod
    def get_filter_context_data_from_rest_data(
        rest_data: Any,
    ) -> tuple[int, dict]:
        variant_id = None
        try:
            variant_data = rest_data["variantData"]
            if variant_data is not None:
                variant_id = variant_data["object"]["id"]
        except KeyError:
            pass

        classification_properties = rest_data.get("classificationProperties")

        return variant_id, classification_properties

    @property
    def variant_filter(self):
        if self._variant_filter is None:
            self._variant_filter = get_variant_filter(
                self.variability_model_context_plugin.variability_model_id,
                self.variant_id,
                self.classification_properties,
            )

        return self._variant_filter

    @classmethod
    def create_for_default_data(
        cls, dependencies: Dependencies, **kwargs: Any
    ) -> Optional[Self]:
        variability_model_context_plugin = dependencies[
            CsVariantsVariabilityModelContextPlugin
        ]
        if not isinstance(
            variability_model_context_plugin, CsVariantsVariabilityModelContextPlugin
        ):
            return None

        instance_name = kwargs.get("instance_name", None)
        additional_data = kwargs.get("additional_data", {})
        if instance_name == INSTANCE_NAME_VARIANT_STRUCTURE:
            variant_id = additional_data["variantId"]
        else:
            bom_table_url = kwargs.get("bom_table_url")
            url_query_args = parse_url_query_args(bom_table_url)
            variant_id = url_query_args.get("variantId", None)
            if variant_id is None:
                return None

        obj = cls(variability_model_context_plugin, variant_id=variant_id)
        obj.request = kwargs.get("request", _get_dummy_request())
        return obj

    def get_default_data(self) -> Any:
        from cs.classification.classification_data import ClassificationData
        from cs.classification.rest import utils as classification_rest_utils
        from cs.variants.api import VariantsClassification

        variant = Variant.ByKeys(
            variability_model_id=self.variability_model_context_plugin.variability_model_id,
            id=self.variant_id,
        )
        if variant is None:
            logging.warning(
                "Variant not found: variability_model_id=%s variant_id=%s",
                self.variability_model_context_plugin.variability_model_id,
                self.variant_id,
            )
            return None, None

        data = ClassificationData(
            variant,
            class_codes=[variant.VariabilityModel.class_code],
            request=self.request,
        )
        values, _, _ = data.get_classification()

        variants_classification = VariantsClassification(
            [variant.VariabilityModel.class_code]
        )
        properties = variants_classification.get_variant_driving_properties_by_class()

        variant_driving_classification = {}
        for property_definition in properties[variant.VariabilityModel.class_code]:
            code = property_definition["code"]
            variant_driving_classification[code] = values[code]

        return {
            "variantData": {
                "object": self.request.view(
                    variant, app=get_collection_app(self.request)
                ),
                "classification": classification_rest_utils.ensure_json_serialiability(
                    variant_driving_classification
                ),
            }
        }, None

    @classmethod
    def create_from_rest_data(
        cls, rest_data: Optional[Any], dependencies: Dependencies
    ) -> Optional[Self]:
        if rest_data is None:
            return None

        variability_model_context_plugin = dependencies.get(
            CsVariantsVariabilityModelContextPlugin
        )
        if not isinstance(
            variability_model_context_plugin, CsVariantsVariabilityModelContextPlugin
        ):
            return None

        (
            variant_id,
            classification_properties,
        ) = cls.get_filter_context_data_from_rest_data(rest_data)
        return cls(
            variability_model_context_plugin,
            variant_id=variant_id,
            classification_properties=classification_properties,
        )


class CsVariantsBomTableAttributesPlugin(AbstractRestPlugin):
    DISCRIMINATOR = "cs.variants.bomTableAttributes"
    DEPENDENCIES = (CsVariantsFilterContextPlugin,)

    def __init__(
        self, variant_filter_context_plugin: Optional[CsVariantsFilterContextPlugin]
    ) -> None:
        self.variant_filter_context_plugin = variant_filter_context_plugin

    @classmethod
    def create_from_rest_data(
        cls, rest_data: Optional[Any], dependencies: Dependencies
    ) -> Optional[Self]:
        variant_filter_context_plugin = dependencies[CsVariantsFilterContextPlugin]
        return cls(variant_filter_context_plugin)

    def get_additional_bom_item_attributes(
        self, bom_item_record: Record
    ) -> Optional[dict]:
        return {
            "in_variant": True
            if self.variant_filter_context_plugin is None
            else self.variant_filter_context_plugin.variant_filter.eval_bom_item(
                bom_item_record
            )
        }


class CsVariantsVariantFilterPlugin(AbstractRestPlugin):
    DISCRIMINATOR = "cs.variants.variantFilter"
    DEPENDENCIES = (CsVariantsFilterContextPlugin,)

    def __init__(
        self, variant_filter_context_plugin: CsVariantsFilterContextPlugin
    ) -> None:
        self.variant_filter_context_plugin = variant_filter_context_plugin

    @classmethod
    def create_from_rest_data(
        cls, rest_data: Optional[Any], dependencies: Dependencies
    ) -> Optional[Self]:
        variant_filter_context_plugin = dependencies[CsVariantsFilterContextPlugin]
        if not isinstance(variant_filter_context_plugin, CsVariantsFilterContextPlugin):
            return None
        return cls(variant_filter_context_plugin)

    def filter_bom_item_records(self, bom_item_records: list[Record]) -> list[Record]:
        return [
            each
            for each in bom_item_records
            if self.variant_filter_context_plugin.variant_filter.eval_bom_item(each)
        ]


class CsVariantsSelectionConditionRendererAttributesPlugin(AbstractRestPlugin):
    DISCRIMINATOR = "cs.variants.selectionConditionRendererAttributes"
    DEPENDENCIES = (CsVariantsVariabilityModelContextPlugin,)

    def __init__(
        self,
        variability_model_context_plugin: CsVariantsVariabilityModelContextPlugin,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self.variability_model_context_plugin = variability_model_context_plugin

        self.bom_item_occurrence_oids_for_bom_item_lookup: dict[
            str, list[str]
        ] = defaultdict(list)
        self.alternative_lookup_dict: dict[tuple[str, str, str], int] = defaultdict(int)

    @classmethod
    def create_from_rest_data(
        cls, rest_data: Optional[Any], dependencies: Dependencies
    ) -> Optional[Self]:
        variability_model_context_plugin = dependencies[
            CsVariantsVariabilityModelContextPlugin
        ]
        if not isinstance(
            variability_model_context_plugin, CsVariantsVariabilityModelContextPlugin
        ):
            return None

        return cls(variability_model_context_plugin)

    def get_sql_join_stmt_extension(self) -> Optional[str]:
        variability_model_id = (
            self.variability_model_context_plugin.variability_model_id
        )
        return f"""
            LEFT JOIN bom_item_occurrence o
            ON o.bompos_object_id={self.BOM_ITEM_TABLE_ALIAS}.cdb_object_id
            LEFT JOIN cs_selection_condition sc
            ON sc.ref_object_id=o.cdb_object_id
                AND sc.variability_model_id='{variability_model_id}'
            """

    def get_bom_item_select_stmt_extension(self) -> Optional[str]:
        variability_model_id = (
            self.variability_model_context_plugin.variability_model_id
        )
        return f""",
                CASE
                    WHEN EXISTS (
                        SELECT 42
                        FROM cs_selection_condition sc
                        WHERE sc.ref_object_id={self.BOM_ITEM_TABLE_ALIAS}.cdb_object_id
                            AND sc.variability_model_id='{variability_model_id}'
                    ) THEN 1
                    ELSE 0
                END has_sc_on_bom_item
                ,
                sc.ref_object_id as occurrence_with_sc_oid
            """

    def get_additional_bom_item_attributes(
        self, bom_item_record: Record
    ) -> Optional[dict]:
        bom_item_occurrence_oids_for_bom_item = (
            self.bom_item_occurrence_oids_for_bom_item_lookup[
                bom_item_record["cdb_object_id"]
            ]
        )
        has_selection_condition_on_oc = len(bom_item_occurrence_oids_for_bom_item) > 0

        cs_variants_has_selection_condition = (
            1
            if bom_item_record["has_sc_on_bom_item"] or has_selection_condition_on_oc
            else 0
        )

        alternative_lookup_dict_key = self.get_alternative_lookup_dict_key(
            bom_item_record
        )
        cs_variants_is_alternative = (
            1 if self.alternative_lookup_dict[alternative_lookup_dict_key] > 1 else 0
        )

        nr_of_selection_conditions_on_oc = len(bom_item_occurrence_oids_for_bom_item)

        return {
            "cs_variants_has_selection_condition": cs_variants_has_selection_condition,
            "cs_variants_is_alternative": cs_variants_is_alternative,
            "nr_of_selection_conditions_on_oc": nr_of_selection_conditions_on_oc,
            "selection_condition_icon": IconCache.getIcon(
                "cs_variants_selection_condition",
                cs_variants_has_selection_condition=cs_variants_has_selection_condition,
                cs_variants_is_alternative=cs_variants_is_alternative,
            ),
        }

    def filter_bom_item_records(self, bom_item_records: list[Record]) -> list[Record]:
        # Building a dict with key cdb_object_id so same part will be only stored once
        filtered_result = {}
        for each in bom_item_records:
            each_cdb_object_id = each["cdb_object_id"]
            occurrence_with_sc_oid = each["occurrence_with_sc_oid"]
            if occurrence_with_sc_oid is not None:
                self.bom_item_occurrence_oids_for_bom_item_lookup[
                    each_cdb_object_id
                ].append(occurrence_with_sc_oid)

            if each_cdb_object_id in filtered_result:
                continue

            filtered_result[each_cdb_object_id] = each

            alternative_lookup_dict_key = self.get_alternative_lookup_dict_key(each)
            self.alternative_lookup_dict[alternative_lookup_dict_key] += 1

        return list(filtered_result.values())

    @staticmethod
    def get_alternative_lookup_dict_key(
        bom_item_record: Record,
    ) -> tuple[str, str, str]:
        return (
            bom_item_record["baugruppe"],
            bom_item_record["b_index"],
            bom_item_record["position"],
        )


class CsVariantsMengeRendererAttributesPlugin(AbstractRestPlugin):
    DISCRIMINATOR = "cs.variants.mengeRendererAttributes"
    DEPENDENCIES = (
        CsVariantsFilterContextPlugin,
        CsVariantsSelectionConditionRendererAttributesPlugin,
    )

    def __init__(
        self,
        variant_filter_context_plugin: Optional[CsVariantsFilterContextPlugin],
        selection_condition_renderer_attributes_plugin: Optional[
            CsVariantsSelectionConditionRendererAttributesPlugin
        ],
    ) -> None:
        self.variant_filter_context_plugin = variant_filter_context_plugin
        self.selection_condition_renderer_attributes_plugin = (
            selection_condition_renderer_attributes_plugin
        )

    @classmethod
    def create_from_rest_data(
        cls, rest_data: Optional[Any], dependencies: Dependencies
    ) -> Optional[Self]:
        variant_filter_context_plugin = dependencies[CsVariantsFilterContextPlugin]
        selection_condition_renderer_attributes_plugin = dependencies[
            CsVariantsSelectionConditionRendererAttributesPlugin
        ]
        return cls(
            variant_filter_context_plugin,
            selection_condition_renderer_attributes_plugin,
        )

    def get_additional_bom_item_attributes(
        self, bom_item_record: Record
    ) -> Optional[dict[Any, Any]]:
        selection_condition_filtered_quantity = bom_item_record["menge"]
        if self.selection_condition_renderer_attributes_plugin is not None:
            selection_condition_renderer_attributes_plugin = (
                self.selection_condition_renderer_attributes_plugin
            )
            bom_item_occurrence_oids_for_bom_item_lookup = (
                selection_condition_renderer_attributes_plugin.bom_item_occurrence_oids_for_bom_item_lookup
            )
            bom_item_occurrence_oids_for_bom_item = (
                bom_item_occurrence_oids_for_bom_item_lookup[
                    bom_item_record["cdb_object_id"]
                ]
            )

            has_selection_condition_on_oc = (
                len(bom_item_occurrence_oids_for_bom_item) > 0
            )

            if (
                has_selection_condition_on_oc
                and self.variant_filter_context_plugin is not None
            ):
                variant_filter = self.variant_filter_context_plugin.variant_filter
                selection_condition_filtered_quantity -= (
                    variant_filter.eval_amount_of_filtered_bom_item_occurrences(
                        bom_item_occurrence_oids_for_bom_item
                    )
                )

        return {
            "selection_condition_filtered_quantity": selection_condition_filtered_quantity
        }


def add_variant_id_group_component(app_setup):
    group_component = "cs-variants-web-common-VariantIdContentBlock"
    add_group_component_for_filter_plugin(
        app_setup,
        group_component,
        CsVariantsVariabilityModelContextPlugin.DISCRIMINATOR,
    )
    add_group_component_for_filter_plugin(
        app_setup,
        group_component,
        CsVariantsFilterContextPlugin.DISCRIMINATOR,
    )


def initialize_default_data_for_product_structure(
    model: OutletConfig, request: Request, app_setup: SettingDict
):
    var_models = []
    if model.classdef.getClassname() == "part":
        rest_name = model.classdef.getRESTName()
        obj = get_object_from_rest_name(rest_name, model.keys)
        var_models = obj.VariabilityModels

    update_app_setup(
        request,
        app_setup,
        variability_models=var_models,
    )
    add_variant_id_group_component(app_setup)


def initialize_default_data_for_threed_cockpit(_, request, app_setup):
    part = request.app.part
    if part is not None:
        var_models = part.VariabilityModels
        update_app_setup(
            request,
            app_setup,
            variability_models=var_models,
        )
    add_variant_id_group_component(app_setup)


class BomPredicatesAttrFlatBomPlugin(AbstractPlugin):
    def get_bom_item_select_stmt_extension(self) -> Optional[str]:
        return f""",
            (
                CASE WHEN EXISTS (
                    SELECT 42
                    FROM bom_item_occurrence occ
                    JOIN cs_selection_condition sc
                    ON sc.ref_object_id=occ.cdb_object_id
                    WHERE {self.BOM_ITEM_TABLE_ALIAS}.cdb_object_id=occ.bompos_object_id
                )
                THEN 1
                ELSE 0
                END
            ) has_sc_on_oc
        """
