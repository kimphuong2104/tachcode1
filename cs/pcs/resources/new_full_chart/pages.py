#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=C1801

import json
from collections import defaultdict

from cdb import auth, elink, sqlapi
from cdb.objects import ByID
from cs.pcs.projects.chart import ChartConfig
from cs.pcs.resources import new_resource_chart
from cs.pcs.resources.new_resource_chart import _getapp as _resource_getapp
from cs.pcs.resources.new_resource_chart.helper import ResourceScheduleHelper
from cs.pcs.timeschedule import new_base_chart, new_time_chart
from cs.pcs.timeschedule.new_base_chart import _getapp as _base_getapp
from cs.pcs.timeschedule.new_base_chart import nanoroute
from cs.pcs.timeschedule.new_base_chart.helper import BaseHelper
from cs.pcs.timeschedule.new_time_chart import _getapp as _time_getapp
from cs.pcs.timeschedule.new_time_chart.helper import TimeScheduleHelper


class MyPage(elink.VirtualPathTemplate):
    __template__ = "index.html"

    def render(self, context):
        vpath = self.get_path_segments(cleanup=True)
        time_schedule_id = vpath[0] if len(vpath) else ""
        resource_schedule_id = vpath[1] if len(vpath) else ""
        full_app = self.application
        base_app = _base_getapp()
        time_app = _time_getapp()
        resource_app = _resource_getapp()
        return {
            "time_schedule": TimeScheduleHelper.get_schedule(time_schedule_id),
            "resource_schedule": ResourceScheduleHelper.get_schedule(
                resource_schedule_id
            ),
            "base_macros": base_app.getTemplates(),
            "base_localres": base_app.getURLPaths()["localres"],
            "time_macros": time_app.getTemplates(),
            "time_localres": time_app.getURLPaths()["localres"],
            "resource_macros": resource_app.getTemplates(),
            "resource_localres": resource_app.getURLPaths()["localres"],
            "full_macros": full_app.getTemplates(),
            "full_localres": full_app.getURLPaths()["localres"],
            "app_base_data": "%sbase_api" % (base_app.getURLPaths()["approot"]),
            "app_time_data": "%stime_api/%s"
            % (time_app.getURLPaths()["approot"], time_schedule_id),
            "app_resource_data": "%sresource_api/%s"
            % (resource_app.getURLPaths()["approot"], resource_schedule_id),
            "app_full_data": "%sfull_api/%s/%s"
            % (
                full_app.getURLPaths()["approot"],
                time_schedule_id,
                resource_schedule_id,
            ),
            "chart_type": "full",
            "custom_base_templates": BaseHelper.get_custom_templates(
                new_base_chart.__path__[0]
            ),
            "custom_time_templates": BaseHelper.get_custom_templates(
                new_time_chart.__path__[0]
            ),
            "custom_resource_templates": BaseHelper.get_custom_templates(
                new_resource_chart.__path__[0]
            ),
            "custom_full_templates": BaseHelper.get_custom_templates(__file__),
            "resources_marked_objects_attrs": ResourceScheduleHelper.get_marked_objects_attrs(),
        }


router = nanoroute.LookUp()


# =======================
# handle data api request
# =======================


@router.json(":time_schedule_id/:resource_schedule_id/settings")
def get_app_settings(page, time_schedule_id, resource_schedule_id):
    key = time_schedule_id + "/" + resource_schedule_id
    chart_ratio = ChartConfig.getValue(auth.persno, key, "#config#", "chart_ratio")
    columns_collapsed = ChartConfig.getValue(
        auth.persno, key, "#config#", "columns_collapsed"
    )
    columns_collapsed = bool(int(columns_collapsed)) if columns_collapsed else False
    left_panel_width = ChartConfig.getValue(
        auth.persno, key, "#config#", "left_panel_width"
    )
    left_panel_width = int(left_panel_width) if left_panel_width else None
    personal_start_date = ChartConfig.getValue(
        auth.persno, key, "#config#", "personal_start_date"
    )
    if not personal_start_date:
        ChartConfig.getValue(
            auth.persno, time_schedule_id, "#config#", "personal_start_date"
        )
        if not personal_start_date:
            ChartConfig.getValue(
                auth.persno, resource_schedule_id, "#config#", "personal_start_date"
            )
    pixels_per_day = ChartConfig.getValue(
        auth.persno, key, "#config#", "pixels_per_day"
    )
    if not pixels_per_day:
        ChartConfig.getValue(
            auth.persno, time_schedule_id, "#config#", "pixels_per_day"
        )
        if not pixels_per_day:
            ChartConfig.getValue(
                auth.persno, resource_schedule_id, "#config#", "pixels_per_day"
            )
    if not personal_start_date or not pixels_per_day:
        personal_start_date = pixels_per_day = None
    personal_start_date = (
        int(personal_start_date) if personal_start_date else personal_start_date
    )
    pixels_per_day = float(pixels_per_day) if pixels_per_day else pixels_per_day
    return {
        "chart_ratio": float(chart_ratio) if chart_ratio else 1,
        "columns_collapsed": columns_collapsed,
        "left_panel_width": left_panel_width,
        "personal_start_date": personal_start_date,
        "pixels_per_day": pixels_per_day,
    }


@router.json(":time_schedule_id/:resource_schedule_id/update_left_panel_width/post")
def update_left_panel_width(page, time_schedule_id, resource_schedule_id):
    left_panel_width = page.get_form_data("left_panel_width")
    key = time_schedule_id + "/" + resource_schedule_id
    ChartConfig.setValue(
        auth.persno, key, "#config#", "left_panel_width", int(left_panel_width)
    )


@router.json(":time_schedule_id/:resource_schedule_id/update_columns_collapsed/post")
def update_columns_collapsed(page, time_schedule_id, resource_schedule_id):
    columns_collapsed = (
        1
        if ResourceScheduleHelper.is_JSON_true(page.get_form_data("columns_collapsed"))
        else 0
    )
    key = time_schedule_id + "/" + resource_schedule_id
    ChartConfig.setValue(
        auth.persno, key, "#config#", "columns_collapsed", str(columns_collapsed)
    )


@router.json(":time_schedule_id/:resource_schedule_id/save_chart_ratio/post")
def save_chart_ratio(page, time_schedule_id, resource_schedule_id):
    key = time_schedule_id + "/" + time_schedule_id
    chart_ratio = page.get_form_data("chart_ratio")
    ChartConfig.setValue(
        auth.persno, key, "#config#", "chart_ratio", float(chart_ratio)
    )


@router.json(":time_schedule_id/:resource_schedule_id/update_time_frame/post")
def update_time_frame(page, time_schedule_id, resource_schedule_id):
    personal_start_date = page.get_form_data("personal_start_date")
    pixels_per_day = page.get_form_data("pixels_per_day")
    key = time_schedule_id + "/" + resource_schedule_id
    if personal_start_date:
        ChartConfig.setValue(
            auth.persno,
            key,
            "#config#",
            "personal_start_date",
            str(personal_start_date),
        )
    if pixels_per_day:
        ChartConfig.setValue(
            auth.persno, key, "#config#", "pixels_per_day", str(pixels_per_day)
        )


@BaseHelper.exception_decorator
def _add_responsibles_to_schedule(**kwargs):
    resource_schedule = ByID(kwargs["resource_schedule_id"])
    resource_schedule.insertObjectsByOID(kwargs["responsible_oids"])


@router.json(
    ":time_schedule_id/:resource_schedule_id/add_responsibles_to_schedule/post"
)
def add_responsibles_to_schedule(page, time_schedule_id, resource_schedule_id):
    responsible_oids = json.loads(page.get_form_data("responsible_oids", []))
    return _add_responsibles_to_schedule(
        **{
            "resource_schedule_id": resource_schedule_id,
            "responsible_oids": responsible_oids,
        }
    )


@BaseHelper.exception_decorator
def _get_task_subjects(**kwargs):
    ts_id = kwargs["ts_id"]
    qry = (
        "SELECT dem.pool_oid, dem.assignment_oid AS rpa_oid, dem.task_object_id, "
        "  dem.cdb_object_id AS oid"
        "  FROM cdbpcs_ts_content tsc, cdbpcs_prj_demand_v dem"
        "  WHERE tsc.cdb_project_id = dem.cdb_project_id"
        "    AND tsc.view_oid = '%s'"
        "  UNION"
        "  SELECT alc.pool_oid, alc.assignment_oid AS rpa_oid, alc.task_object_id, "
        "  alc.cdb_object_id AS oid"
        "  FROM cdbpcs_ts_content tsc, cdbpcs_prj_alloc_v alc"
        "  WHERE tsc.cdb_project_id = alc.cdb_project_id"
        "    AND tsc.view_oid = '%s'"
    ) % (ts_id, ts_id)
    task2resource = defaultdict(set)
    pool2task = defaultdict(set)
    rpa2task = defaultdict(set)
    task2rpa = defaultdict(set)
    task2pool = defaultdict(set)
    for rec in sqlapi.RecordSet2(sql=qry):
        task2resource[rec.task_object_id].add(rec.oid)
        if rec.rpa_oid:
            rpa2task[rec.rpa_oid].add(rec.task_object_id)
            task2rpa[rec.task_object_id].add(rec.rpa_oid)
        else:
            pool2task[rec.pool_oid].add(rec.task_object_id)
            task2pool[rec.task_object_id].add(rec.pool_oid)
    return {
        "rpa2task": {k: list(v) for k, v in rpa2task.items()},
        "pool2task": {k: list(v) for k, v in pool2task.items()},
        "task2rpa": {k: list(v) for k, v in task2rpa.items()},
        "task2pool": {k: list(v) for k, v in task2pool.items()},
        "task2resource": {k: list(v) for k, v in task2resource.items()},
    }


@router.json(":time_schedule_id/:resource_schedule_id/get_task_subjects")
def get_task_subjects(page, time_schedule_id, resource_schedule_id):
    ts_id = sqlapi.quote(time_schedule_id)
    return _get_task_subjects(**{"ts_id": ts_id})
