#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

"""
Indicators aggregate project data in as few database roundtrips as possible.
They can be used in frontend components, for example as part of project cards.
"""


from collections import defaultdict
from string import Formatter

from cdb import sig, sqlapi, util
from cdb.objects import Object
from cdb.tools import getObjectByName

from cs.pcs.projects.common.webdata.util import get_sql_condition
from cs.pcs.projects.data_sources import DataSource

VIEW_PROJECT_INDICATORS = "cdbpcs_project_indicators_v"
VIEW_TASK_INDICATORS = "cdbpcs_task_indicators_v"

map_restname_to_view = {
    "project": VIEW_PROJECT_INDICATORS,
    "project_task": VIEW_TASK_INDICATORS,
}

ResolveIndicators = sig.signal()


class DefaultToZeroFormatter(Formatter):
    def get_value(self, key, args, kwargs):
        if isinstance(key, str):
            try:
                return kwargs[key] if kwargs[key] else 0
            except KeyError:
                return 0
        else:
            return super().get_value(key, args, kwargs)


def generate_cdbpcs_project_indicators_v():
    """view containing project data sources"""
    stmt = DataSource.GetCombinedViewStatement("project", ["cdb_project_id"])
    if stmt == "":
        # no data sources yet; return dummy statement so generation won't fail
        stmt = """
            SELECT
                NULL AS data_source,
                0 AS quantity,
                NULL AS cdb_project_id,
                '' AS ce_baseline_id
            FROM cdbpcs_project
            WHERE 1=2
        """
    return stmt


def generate_cdbpcs_task_indicators_v():
    """view containing task sate sources"""
    stmt = DataSource.GetCombinedViewStatement(
        "project_task", ["cdb_project_id", "task_id"]
    )
    if stmt == "":
        # no data sources yet; return dummy statement so generation won't fail
        stmt = """
            SELECT
                NULL AS data_source,
                0 AS quantity,
                NULL AS cdb_project_id,
                '' AS ce_baseline_id,
                NULL AS task_id
            FROM cdbpcs_task
            WHERE 1=2
        """
    return stmt


class Indicator(Object):
    __classname__ = "cdbpcs_indicator"
    __maps_to__ = "cdbpcs_indicator"

    event_map = {
        (("create", "copy", "modify"), "pre"): "validate_fqpyname",
    }

    def validate_fqpyname(self, ctx=None):
        if self.indicator_fqpyname:
            try:
                getObjectByName(self.indicator_fqpyname)
            except (KeyError, ImportError) as error:
                raise util.ErrorMessage("cdbpcs_indicator_invalid_fqpyname", error)

    def to_json(self, raw_data):
        """
        Returns a JSON-serializable version of resolved indicator values.
        The return value always contains these keys:

        icon
            The icon ID ``self.icon``.

        label
            The resolved label ``self.label``

        data
            Indicator data from ``raw_data``,
            indexed by context object keys, e.g. ``cdb_project_id``.
            Values are strings
            (the amount of rows
            defined by the datas ource pattern of the indicator ).

        .. rubric :: Example Return Value

        .. code-block :: python

            {
                "icon": "cdbpcs_task",
                "label": "Critical Tasks",
                "list_config_name": "Critical Tasks",
                "overlay_component_name": "",
                "data": {
                    "P0815": "1/4",
                    "P4711": "0/2",
                }
            }

        :param raw_data: All data sources associated
            with the restname of the object.
        :type raw_data: dict of object keys containing
            a dict of data sources and count of elements

        :returns: JSON-serializable version of given ``raw_data``.
        :rtype: dict
        """

        result = {
            "icon": self.icon,
            "label": util.get_label(self.label) if self.label else "",
            "list_config_name": self.list_config_name,
            "overlay_component_name": self.overlay_component_name,
            "data": {},
        }
        if self.indicator_fqpyname:
            python_function = getObjectByName(self.indicator_fqpyname)
            # call python function for adjusting result
            result["data"] = python_function(self, raw_data)
        else:
            formatter = DefaultToZeroFormatter()
            for rest_key, data in raw_data.items():
                result["data"][rest_key] = {
                    "value": formatter.format(self.data_source_pattern, **data),
                }
        return result


@sig.connect(ResolveIndicators)
def ResolveProjectIndicators(rest_name, project_ids, indicator_whitelist=None):
    """
    Resolve all indicators for given context objects
    (projects identified by ``project_ids``).

    :param project_ids: IDs of projects to resolve indicators for.
    :type project_ids: list of str

    :param indicator_whitelist: Whitelisted Indicator names
    :type indicator_whitelist: list of str

    :returns: JSON-serializable indicator data indexed by indicator name
        (see :py:meth:`to_json` for value details).
    :rtype: dict
    """
    if rest_name != "project":
        # only process this signal request in case project indicators are needed
        return None

    # we don't include ce_baseline_id to get indicators data, in datasource
    # config we already have a WHERE clause checking for empty ce_baseline_id
    normalized_project_ids = [pid[0] for pid in project_ids]

    # Note: views are never access controlled, so no access check
    in_clause = "', '".join(sqlapi.quote(pid) for pid in normalized_project_ids)
    raw_data = sqlapi.RecordSet2(
        map_restname_to_view["project"],
        f"cdb_project_id IN ('{in_clause}')",
    )

    def make_key(project_id):
        return f"{project_id}@{''}"  # empty ce_baseline_id

    by_data_source = defaultdict(lambda: defaultdict(dict))
    for pid in project_ids:
        by_data_source[make_key(pid[0])] = defaultdict(dict)

    for data_row in raw_data:
        key = make_key(data_row.cdb_project_id)
        by_data_source[key][data_row.data_source] = int(data_row.quantity)
    ifilter = {"rest_visible_name": "project"}
    if indicator_whitelist:
        ifilter["name"] = indicator_whitelist
    return {
        indicator.name: indicator.to_json(by_data_source)
        for indicator in Indicator.KeywordQuery(**ifilter)
    }


@sig.connect(ResolveIndicators)
def ResolveTasksIndicators(rest_name, task_ids, indicator_whitelist=None):
    """
    Resolve all indicators for given context objects
    (tasks identified by ``cdb_project_id`` and ``task_ids``).

    :param task_ids: Tuples of `cdb_project_id` and `task_id`
        to resolve indicators for.
    :type task_ids: list of tuples

    :param indicator_whitelist: Whitelisted Indicator names
    :type indicator_whitelist: list of str

    :returns: JSON-serializable indicator data indexed by indicator name
        (see :py:meth:`to_json` for value details).
    :rtype: dict

    .. note ::

        No access checks are made
        - tasks identified by `task_ids` have to be readable.
    """
    if rest_name != "project_task":
        # only process this signal request in case task indicators are needed
        return None

    # we don't include ce_baseline_id to get indicators data, in datasource
    # config we already have a WHERE clause checking for empty ce_baseline_id
    normalized_task_ids = [[task[0], task[1]] for task in task_ids]

    view = map_restname_to_view["project_task"]
    condition = get_sql_condition(
        view,
        ("cdb_project_id", "task_id"),
        normalized_task_ids,
    )
    # Note: views are never access controlled, so no access check
    raw_data = sqlapi.RecordSet2(view, condition)
    by_data_source = defaultdict(lambda: defaultdict(dict))
    for data_row in raw_data:
        key = f"{data_row.cdb_project_id}@{data_row.task_id}@{''}"
        by_data_source[key][data_row.data_source] = int(data_row.quantity)

    ifilter = {"rest_visible_name": "project_task"}
    if indicator_whitelist:
        ifilter["name"] = indicator_whitelist
    return {
        indicator.name: indicator.to_json(by_data_source)
        for indicator in Indicator.KeywordQuery(**ifilter)
    }


def tasks_issues_overdue(obj, raw_data):
    def get_int(rdata, key):
        if type(rdata.get(key)) is int:
            return rdata[key]

    def get_value(obj, rdata):
        issues_overdue = get_int(rdata, "issues_overdue")
        tasks_overdue = get_int(rdata, "tasks_overdue")

        if issues_overdue is None:
            if tasks_overdue is None:
                formatter = DefaultToZeroFormatter()
                return formatter.format(obj.data_source_pattern, **rdata)
            else:
                return tasks_overdue
        else:
            if tasks_overdue is None:
                return issues_overdue
            else:
                return tasks_overdue + issues_overdue

    data_result = {}

    for rid, rdata in raw_data.items():
        data_result[rid] = {
            "value": get_value(obj, rdata),
            "indicator_style": "danger",
            "additional_icon": "cdbpcs_overdue_fixed",
        }

    return data_result


def set_indicator_style_error(obj, raw_data):
    data_result = {}

    for rid, rdata in raw_data.items():
        formatter = DefaultToZeroFormatter()
        data_result[rid] = {
            "value": formatter.format(obj.data_source_pattern, **rdata),
            "indicator_style": "danger",
        }

    return data_result


def set_indicator_style_info(obj, raw_data):
    data_result = defaultdict(lambda: defaultdict(dict))

    for rid, rdata in raw_data.items():
        formatter = DefaultToZeroFormatter()
        data_result[rid]["value"] = formatter.format(obj.data_source_pattern, **rdata)
        data_result[rid]["indicator_style"] = "info"

    return data_result


def set_indicator_style_project_cl_ko(obj, raw_data):
    data_result = defaultdict(lambda: defaultdict(dict))

    for rid, rdata in raw_data.items():
        formatter = DefaultToZeroFormatter()

        data_result[rid]["value"] = formatter.format(obj.data_source_pattern, **rdata)

        if rdata.get(obj.name):
            data_result[rid]["indicator_style"] = "danger"

    return data_result
