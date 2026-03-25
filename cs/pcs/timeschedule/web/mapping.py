#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Mapping helper to fit heterogenous objects in a common schema, for example to
use in a single cs.web table.

"""

import json
import logging
from collections import defaultdict

from cdb import util
from cdb.lru_cache import lru_cache
from cdb.objects import Object

from cs.pcs.projects.common import get_restname


class ColumnDefinition(Object):
    """
    Defines a column in Gantt Chart application's table.
    """

    __maps_to__ = "cdbpcs_ts_coldef"
    __classname__ = "cdbpcs_ts_coldef"

    @staticmethod
    @lru_cache(maxsize=1)
    def ByGroup(colgroup):
        """
        :param colgroup: Column group to query definitions for.
        :type colgroup: str

        :returns: Column definitions for given ``colgroup`` ordered by
            ``col_position``.
        :rtype: cdb.objects.references.ObjectCollection of ColumnDefinition

        .. note ::

            This function uses a cache to always return
            the first call's return value.
            Reset the cache by calling ``get_table_columns.cache_clear()``.

        """
        return ColumnDefinition.KeywordQuery(
            colgroup=colgroup,
            order_by="col_position",
        )


class ColumnMapping(Object):
    """
    Mapping instructions for a given ``ColumnDefinition`` and classname.
    """

    __maps_to__ = "cdbpcs_ts_colmap"
    __classname__ = "cdbpcs_ts_colmap"
    __txt_field__ = "cdbpcs_ts_colmap_txt"
    __component__ = "### component ###"

    def get_json_value(self):
        """
        :returns: The deserialized JSON value in ``self.__txt_field__``
        :rtype: anything serializable as JSON

        :raises ValueError: if value is not valid JSON
        """
        json_value = self.GetText(self.__txt_field__)
        try:
            return json.loads(json_value)
        except (TypeError, ValueError, AttributeError) as exc:
            logging.exception(
                "could not deserialize column mapping JSON: %s", json_value
            )
            raise ValueError from exc

    @classmethod
    def GetFieldWhitelist(cls, plugin, **kwargs):
        """
        :param plugin: The plugin to get required fields for
        :type plugin: subclass of
            ``cs.pcs.timeschedule.web.plugins.TimeschedulePlugin``

        :param kwargs: Additional query parameters for mappings. ``classname``
            will always be overwritten with the plugin's classname.
        :type kwargs: dict

        :returns: All fields required for frontend mapping of the plugin's
            objects. Never includes system fields from
            ``cs.pcs.timeschedule.web.rest_objects.REST_WHITELIST`` or the
            placeholder for "component fetches its own values " (defined as
            ``cls.__component__``).
        :rtype: set

        :raises TypeError: if ``plugin.GetRequiredFields`` does not return
            an iterable value.

        :raises AttributeError: if any mapping identified by query does not
            contain valid mapping data.
        """
        from cs.pcs.timeschedule.web.rest_objects import REST_WHITELIST

        result = set(["cdb_object_id"]).union(plugin.GetRequiredFields())

        kwargs["classname"] = plugin.classname
        mappings = cls.KeywordQuery(**kwargs)

        for mapping in mappings:
            json_value = mapping.get_json_value()

            if isinstance(json_value, str):
                result.add(json_value)
            else:
                result.update(list(json_value.values()))

        return (
            result.difference([cls.__component__])
            .difference([None])
            .difference(REST_WHITELIST)
        )

    @classmethod
    def ByColumns(cls, colgroup, column_ids):
        """
        :param colgroup: Column group to query mappings for.
        :type colgroup: str

        :param column_ids: Column IDs to query mappings for.
        :type column_ids: list

        :returns: Mapping values indexed by column ID, indexed by restname.
            The restname is determined by classname attribute of mapping.
            Each value includes a "readonly" flag and the frontend mapping
            (field name of object) in "field".
        :rtype: dict of dict

        :raises ValueError: if any mapping value is not valid JSON.
        """
        mappings = cls.KeywordQuery(
            colgroup=colgroup,
            id=column_ids,
            order_by="classname",
        )
        result = defaultdict(dict)

        for mapping in mappings:
            result[
                # resnames are cached already
                get_restname(mapping.classname)
            ][mapping.id] = {
                "readonly": bool(mapping.readonly),
                "field": mapping.get_json_value(),
            }

        return result

    event_map = {
        (("create", "copy", "modify"), "pre"): "validate",
    }

    def validate(self, ctx):
        """
        Validates the long text ``self.__txt_field__`` in the dialog is

        - valid JSON and
        - a valid mapping value (either a simple string or a dict with simple
          string values).

        :raises cdb.util.ErrorMessage: if either constraint is violated.
        """
        try:
            value = json.loads(ctx.dialog[self.__txt_field__])
        except (ValueError, TypeError) as exc:
            raise util.ErrorMessage("cdbpcs_ts_colmap_invalid_json") from exc

        if isinstance(value, str):
            return

        if isinstance(value, dict) and all(isinstance(v, str) for v in value.values()):
            return

        raise util.ErrorMessage("cdbpcs_ts_colmap_invalid_value")
