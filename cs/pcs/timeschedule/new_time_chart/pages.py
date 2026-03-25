#!/usr/bin/env python
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__revision__ = "$Id$"

import json

from cdb import auth, elink, sqlapi, ue
from cdb.constants import kOperationDelete, kOperationModify, kOperationNew
from cdb.elink.engines.chameleon.engine import _OpHelper
from cdb.fls import get_license
from cdb.objects import ByID, IconCache
from cdb.objects.operations import operation

from cs.pcs.projects.chart import ChartConfig
from cs.pcs.projects.tasks import (
    ALLOWED_TASK_GROUP_DEPENDECIES,
    TaskRelation,
    TaskRelationType,
)
from cs.pcs.timeschedule import TimeScheduleObject, TSHelper, new_base_chart
from cs.pcs.timeschedule.new_base_chart import _getapp as _base_getapp
from cs.pcs.timeschedule.new_base_chart import nanoroute
from cs.pcs.timeschedule.new_base_chart.helper import BaseHelper
from cs.pcs.timeschedule.new_time_chart.helper import TimeScheduleHelper


class MyPage(elink.VirtualPathTemplate):
    __template__ = "index.html"

    def render(self, context):
        vpath = self.get_path_segments(cleanup=True)
        time_schedule_id = vpath[0] if len(vpath) else ""
        time_schedule = TimeScheduleHelper.get_schedule(time_schedule_id)
        base_app = _base_getapp()
        time_app = self.application
        result = {
            "time_schedule": time_schedule,
            "base_macros": base_app.getTemplates(),
            "base_localres": base_app.getURLPaths()["localres"],
            "time_macros": time_app.getTemplates(),
        }
        if not time_schedule:
            return result

        result.update(
            {
                "time_localres": time_app.getURLPaths()["localres"],
                "resource_schedule": None,
                "resource_macros": None,
                "resource_localres": None,
                "app_base_data": "%sbase_api" % (base_app.getURLPaths()["approot"]),
                "app_time_data": "%stime_api/%s"
                % (time_app.getURLPaths()["approot"], time_schedule_id),
                "app_resource_data": None,
                "app_full_data": None,
                "chart_type": "time",
                "custom_base_templates": BaseHelper.get_custom_templates(
                    new_base_chart.__path__[0]
                ),
                "custom_time_templates": BaseHelper.get_custom_templates(__file__),
            }
        )
        return result


router = nanoroute.LookUp()


# =======================
# handle data api request
# =======================


@router.json(":time_schedule_id/settings")
def get_app_settings(page, time_schedule_id):
    schedule = TimeScheduleHelper.get_schedule(time_schedule_id)
    if not schedule:
        return None
    chart_type = page.get_form_data("chart_type")
    permission_denied = not schedule.CheckAccess("save", auth.persno)
    rel_dict = TaskRelationType.getTypeLabels()
    rel_types = list(rel_dict.values())
    rel_default = rel_dict["EA"]
    columns = BaseHelper.get_chart_columns(auth.persno, time_schedule_id)
    ts_ops = []
    op_list = _OpHelper.get_object_operations_for_context(
        schedule, "pcs_timeschedule_timeschedule", "CDB_ShowObject"
    )
    not_web_context = elink.isCDBPC()
    if not_web_context:
        for op in op_list:
            ts_ops.append(TSHelper.get_op_info(op))
    allowed_task_group_dependecies = [
        v
        for k, v in TaskRelationType.getTypeLabels().items()
        if k in ALLOWED_TASK_GROUP_DEPENDECIES
    ]
    result = dict(
        time_schedule_id=schedule.cdb_object_id,
        schedule_name=schedule.name,
        _columns_as_dict=columns,
        rel_types=rel_types,
        rel_default=rel_default,
        ts_ops=ts_ops,
        operations_deactivated=not bool(len(ts_ops)),
        default_info_icon=IconCache.getIcon("Information"),
        schedule_permission_denied=permission_denied,
        allowed_task_group_dependecies=allowed_task_group_dependecies,
    )
    if chart_type == "time":
        columns_collapsed = ChartConfig.getValue(
            auth.persno, schedule.cdb_object_id, "#config#", "columns_collapsed"
        )
        columns_collapsed = bool(int(columns_collapsed)) if columns_collapsed else False
        left_panel_width = ChartConfig.getValue(
            auth.persno, schedule.cdb_object_id, "#config#", "left_panel_width"
        )
        left_panel_width = int(left_panel_width) if left_panel_width else None
        personal_start_date = ChartConfig.getValue(
            auth.persno, schedule.cdb_object_id, "#config#", "personal_start_date"
        )
        personal_start_date = (
            int(personal_start_date) if personal_start_date else personal_start_date
        )
        pixels_per_day = ChartConfig.getValue(
            auth.persno, schedule.cdb_object_id, "#config#", "pixels_per_day"
        )
        pixels_per_day = float(pixels_per_day) if pixels_per_day else pixels_per_day
        result.update(
            {
                "columns_collapsed": columns_collapsed,
                "left_panel_width": left_panel_width,
                "personal_start_date": personal_start_date,
                "pixels_per_day": pixels_per_day,
            }
        )
    return result


@BaseHelper.exception_decorator
def _change_position(**kwargs):
    schedule = ByID(kwargs["time_schedule_id"])
    ids = kwargs["ids"]
    for tsc in schedule.TimeScheduleContents:
        tsc.position = ids.index(tsc.content_oid)
    return


@router.json(":time_schedule_id/change_position/post")
def change_position(page, time_schedule_id):
    ids = json.loads(page.get_form_data("ids"))
    return _change_position(**{"time_schedule_id": time_schedule_id, "ids": ids})


@BaseHelper.exception_decorator
def _update_columns(**kwargs):
    columns = kwargs["columns"]
    time_schedule_id = kwargs["time_schedule_id"]
    for column in columns:
        ChartConfig.setValue(
            auth.persno,
            time_schedule_id,
            column["name"],
            "visible",
            str(int(column["visible"])),
        )
        ChartConfig.setValue(
            auth.persno,
            time_schedule_id,
            column["name"],
            "position",
            str(int(column["position"])),
        )
    return


@router.json(":time_schedule_id/update_columns/post")
def update_columns(page, time_schedule_id):
    columns = json.loads(page.get_form_data("columns"))
    return _update_columns(**{"time_schedule_id": time_schedule_id, "columns": columns})


@BaseHelper.exception_decorator
def _reveal_id(**kwargs):
    schedule = ByID(kwargs["time_schedule_id"])
    tso = ByID(kwargs["my_id"])
    schedule.reveal_tso_in_schedule(tso, True)


@router.json(":time_schedule_id/reveal_id/post")
def reveal_id(page, time_schedule_id):
    my_id = page.get_form_data("id")
    return _reveal_id(**{"time_schedule_id": time_schedule_id, "my_id": my_id})


@BaseHelper.exception_decorator
def _fully_expand_id(**kwargs):
    schedule = ByID(kwargs["time_schedule_id"])
    tso = ByID(kwargs["my_id"])
    schedule.fully_expand_tso_in_schedule(tso)


@router.json(":time_schedule_id/fully_expand_id/post")
def fully_expand_id(page, time_schedule_id):
    my_id = page.get_form_data("id")
    return _fully_expand_id(**{"time_schedule_id": time_schedule_id, "my_id": my_id})


@BaseHelper.exception_decorator
def _create_relations(**kwargs):
    relations_data = kwargs["relations_data"]
    relations = []
    db_rel_types = {v: k for k, v in TaskRelationType.getTypeLabels().items()}
    for relation_data in relations_data:
        pred_task = ByID(relation_data["predecessorID"])
        pred_proj = pred_task.Project
        succ_task = ByID(relation_data["successorID"])
        succ_proj = succ_task.Project
        rel_data_dict = {
            "cdb_project_id": succ_proj.cdb_project_id,
            "task_id": succ_task.task_id,
            "cdb_project_id2": pred_proj.cdb_project_id,
            "task_id2": pred_task.task_id,
            "rel_type": db_rel_types[relation_data["type"]],
            "pred_project_oid": pred_proj.cdb_object_id,
            "pred_task_oid": pred_task.cdb_object_id,
            "succ_project_oid": succ_proj.cdb_object_id,
            "succ_task_oid": succ_task.cdb_object_id,
        }
        if not TaskRelation.KeywordQuery(**rel_data_dict):
            relation = TaskRelation.createRelation(**rel_data_dict)
            minimal_gap = relation_data["minimal_gap"]
            if (
                minimal_gap is not None
                and relation
                and (minimal_gap != relation.minimal_gap)
            ):
                relations.append((relation, minimal_gap))
    if len(relations):
        _move_relations(**{"relations": relations})


@router.json(":time_schedule_id/create_relations/post")
def create_relations(page, time_schedule_id):
    relations_data = json.loads(page.get_form_data("relations_data"))
    return _create_relations(
        **{"time_schedule_id": time_schedule_id, "relations_data": relations_data}
    )


@router.json(":time_schedule_id/refresh_data")
def get_changed_app_content(page, time_schedule_id):
    loaded_time_stamp = page.get_form_data("loaded_time_stamp")
    ids_client = json.loads(page.get_form_data("ids_client"))
    expanded_ids = json.loads(page.get_form_data("expanded_ids"))
    use_serverside_settings = TimeScheduleHelper.is_JSON_true(
        page.get_form_data("use_serverside_settings")
    )
    # first load, get saved expanded_ids
    if use_serverside_settings:
        expanded_ids = ChartConfig.getSetting(
            auth.persno, time_schedule_id, setting_name="#expandedId#"
        )
    # save expanded_ids
    else:
        ChartConfig.setSetting(
            auth.persno, time_schedule_id, expanded_ids, setting_name="#expandedId#"
        )
    return TimeScheduleHelper.get_changed_data(
        time_schedule_id=time_schedule_id,
        loaded_time_stamp=int(loaded_time_stamp) if loaded_time_stamp else None,
        ids_client=ids_client,
        expanded_ids=expanded_ids,
    )


@router.json(":time_schedule_id/load_async_data")
def load_async_data(page, time_schedule_id):
    obj_ids = json.loads(page.get_form_data("obj_ids"))
    has_licence = get_license("TIMESCHEDULE_005")
    return {id: ByID(id).getTSFieldsAsync(has_licence) for id in obj_ids}


@BaseHelper.exception_decorator
def _save_expanded_ids(**kwargs):
    ChartConfig.setSetting(
        auth.persno,
        kwargs["time_schedule_id"],
        kwargs["expanded_ids"],
        setting_name="#expandedId#",
    )


@router.json(":time_schedule_id/save_expanded_ids/post")
def save_expanded_ids(page, time_schedule_id):
    expanded_ids = json.loads(page.get_form_data("expanded_ids"))
    return _save_expanded_ids(
        **{"time_schedule_id": time_schedule_id, "expanded_ids": expanded_ids}
    )


@BaseHelper.exception_decorator
def _toggle_ts_obj_in(**kwargs):
    operation(kOperationNew, TimeScheduleObject, **kwargs)


@BaseHelper.exception_decorator
def _toggle_ts_obj_out(**kwargs):
    # need to remove expandedId settings for children which are no longer displayed
    tso = kwargs["tso"]
    expanded_ids = ChartConfig.getSetting(
        auth.persno, tso.view_oid, setting_name="#expandedId#"
    )
    s = """SELECT content_oid FROM cdbpcs_ts_content WHERE view_oid = '%s'""" % (
        tso.view_oid
    )
    rs = sqlapi.RecordSet2(sql=s)
    ids_in_schedule = [e["content_oid"] for e in rs]
    obj = tso.getContentObject()

    def remove_settings(obj, expanded_ids):
        if obj.cdb_object_id in expanded_ids:
            expanded_ids.remove(obj.cdb_object_id)
            children = obj.getChildrenObjects()
            for child in children:
                if child.cdb_object_id not in ids_in_schedule:
                    expanded_ids = remove_settings(child, expanded_ids)
        return expanded_ids

    operation(kOperationDelete, tso)
    parent = obj.getParentObject()
    if not (parent and parent.cdb_object_id in ids_in_schedule):
        remove_settings(obj, expanded_ids)
        ChartConfig.setSetting(
            auth.persno, tso.view_oid, expanded_ids, setting_name="#expandedId#"
        )


@router.json(":time_schedule_id/toggle_ts_obj/post")
def toggle_ts_obj(page, time_schedule_id):
    oid = page.get_form_data("oid")
    in_schedule = TimeScheduleHelper.is_JSON_true(page.get_form_data("inSchedule"))
    tso = TimeScheduleObject.ByKeys(view_oid=time_schedule_id, content_oid=oid)
    if not in_schedule:
        if not tso:
            return
        return _toggle_ts_obj_out(**{"tso": tso})
    else:
        obj = ByID(oid)
        if not obj or tso:
            return
        kwargs = {
            "view_oid": time_schedule_id,
            "content_oid": oid,
            "cdb_content_classname": obj.GetClassname(),
            "cdb_project_id": obj.cdb_project_id,
        }
        return _toggle_ts_obj_in(**kwargs)


@BaseHelper.exception_decorator
def _update_duration(**kwargs):
    cdb_object_id = kwargs["cdb_object_id"]
    if cdb_object_id:
        obj = ByID(cdb_object_id)
        obj.setDaysFcast(days=kwargs["new_duration"])
    return


@router.json(":time_schedule_id/update_duration/post")
def update_duration(page, time_schedule_id):
    new_duration = page.get_form_data("duration")
    new_duration = int(new_duration) if new_duration else ""
    cdb_object_id = page.get_form_data("cdb_object_id")
    return _update_duration(
        **{"new_duration": new_duration, "cdb_object_id": cdb_object_id}
    )


@BaseHelper.exception_decorator
def _update_effort(**kwargs):
    cdb_object_id = kwargs["cdb_object_id"]
    if cdb_object_id:
        obj = ByID(cdb_object_id)
        obj.setEffortFcast(kwargs["new_effort"])
    return


@router.json(":time_schedule_id/update_effort_fcast/post")
def update_effort(page, time_schedule_id):
    new_effort = page.get_form_data("effort_fcast")
    new_effort = float(new_effort) if new_effort else ""
    cdb_object_id = page.get_form_data("cdb_object_id")
    return _update_effort(**{"new_effort": new_effort, "cdb_object_id": cdb_object_id})


@BaseHelper.exception_decorator
def _update_effort_act(**kwargs):
    cdb_object_id = kwargs["cdb_object_id"]
    if cdb_object_id:
        obj = ByID(cdb_object_id)
        obj.setEffortAct(kwargs["new_effort"])
    return


@router.json(":time_schedule_id/update_effort_act/post")
def update_effort_act(page, time_schedule_id):
    new_effort = page.get_form_data("effort_act")
    new_effort = float(new_effort) if new_effort else ""
    cdb_object_id = page.get_form_data("cdb_object_id")
    return _update_effort_act(
        **{"new_effort": new_effort, "cdb_object_id": cdb_object_id}
    )


@BaseHelper.exception_decorator
def _update_effort_demand(**kwargs):
    cdb_object_id = kwargs["cdb_object_id"]
    if cdb_object_id:
        obj = ByID(cdb_object_id)
        obj.setEffortDemand(kwargs["new_effort"])
    return


@router.json(":time_schedule_id/update_effort_fcast_d/post")
def update_effort_demand(page, time_schedule_id):
    new_effort = page.get_form_data("effort_fcast_d")
    new_effort = float(new_effort) if new_effort else ""
    cdb_object_id = page.get_form_data("cdb_object_id")
    return _update_effort_demand(
        **{"new_effort": new_effort, "cdb_object_id": cdb_object_id}
    )


@BaseHelper.exception_decorator
def _update_effort_assignment(**kwargs):
    cdb_object_id = kwargs["cdb_object_id"]
    if cdb_object_id:
        obj = ByID(cdb_object_id)
        obj.setEffortAssignment(kwargs["new_effort"])
    return


@router.json(":time_schedule_id/update_effort_fcast_a/post")
def update_effort_assignment(page, time_schedule_id):
    new_effort = page.get_form_data("effort_fcast_a")
    new_effort = float(new_effort) if new_effort else ""
    cdb_object_id = page.get_form_data("cdb_object_id")
    return _update_effort_assignment(
        **{"new_effort": new_effort, "cdb_object_id": cdb_object_id}
    )


@BaseHelper.exception_decorator
def _update_position(**kwargs):
    cdb_object_id = kwargs["cdb_object_id"]
    if cdb_object_id:
        obj = ByID(cdb_object_id)
        if obj:
            obj.setNewPosition(kwargs["new_position"])
    return


@router.json(":time_schedule_id/update_position/post")
def update_position(page, time_schedule_id):
    new_position = page.get_form_data("position")
    new_position = int(new_position) if new_position else ""
    cdb_object_id = page.get_form_data("cdb_object_id")
    return _update_position(
        **{"new_position": new_position, "cdb_object_id": cdb_object_id}
    )


@BaseHelper.exception_decorator
def _update_title(**kwargs):
    cdb_object_id = kwargs["cdb_object_id"]
    if cdb_object_id:
        obj = ByID(cdb_object_id)
        if obj:
            obj.setName(kwargs["new_title"])
    return


@router.json(":time_schedule_id/update_title/post")
def update_title(page, time_schedule_id):
    new_title = page.get_form_data("title")
    cdb_object_id = page.get_form_data("cdb_object_id")
    return _update_title(**{"new_title": new_title, "cdb_object_id": cdb_object_id})


@BaseHelper.exception_decorator
def _update_start_end_dates(**kwargs):
    in_table = kwargs["in_table"]
    cdb_object_id = kwargs["cdb_object_id"]
    _start = kwargs["_start"]
    _end = kwargs["_end"]
    drag = kwargs["drag"]
    obj = ByID(cdb_object_id)
    start = TSHelper.utc2date(_start)
    end = TSHelper.utc2date(_end)
    if drag:
        if _start is not None or _end is not None:
            obj.moveTimeframe(start=start, end=end)
    else:
        if _start is not None:
            if in_table:
                obj.setStartTimeFcast(start=start)
            else:
                obj.setStartTimeFcastByBar(start=start)
        elif _end is not None:
            if in_table:
                obj.setEndTimeFcast(end=end)
            else:
                obj.setEndTimeFcastByBar(end=end)
    return


@router.json(":time_schedule_id/update_start_end_dates/post")
def update_start_end_dates(page, time_schedule_id):
    in_table = TimeScheduleHelper.is_JSON_true(page.get_form_data("in_table"))
    cdb_object_id = page.get_form_data("cdb_object_id")
    _start = page.get_form_data("start_date")
    _end = page.get_form_data("end_date")
    drag = json.loads(page.get_form_data("drag"))
    return _update_start_end_dates(
        **{
            "in_table": in_table,
            "cdb_object_id": cdb_object_id,
            "_start": _start,
            "_end": _end,
            "drag": drag,
        }
    )


@BaseHelper.exception_decorator
def _update_start_end_plan_dates(**kwargs):
    start_date_plan = TSHelper.utc2date(kwargs["_start_date_plan"])
    obj = ByID(kwargs["cdb_object_id"])
    if start_date_plan is not None:
        obj.moveTimeframePlan(start=start_date_plan)
    return


@router.json(":time_schedule_id/update_start_end_plan_dates/post")
def update_start_end_plan_dates(page, time_schedule_id):
    _start_date_plan = page.get_form_data("start_date_plan")
    cdb_object_id = page.get_form_data("cdb_object_id")
    return _update_start_end_plan_dates(
        **{"_start_date_plan": _start_date_plan, "cdb_object_id": cdb_object_id}
    )


@BaseHelper.exception_decorator
def _update_constraint_date(**kwargs):
    cdb_object_id = kwargs["cdb_object_id"]
    _constraint_date = kwargs["_constraint_date"]
    obj = ByID(cdb_object_id)
    constraint_date = TSHelper.utc2date(_constraint_date)
    return obj.setConstraint(constraint_date=constraint_date)


@router.json(":time_schedule_id/update_constraint_date/post")
def update_constraint_date(page, time_schedule_id):
    cdb_object_id = page.get_form_data("cdb_object_id")
    _constraint_date = page.get_form_data("constraint_date")
    return _update_constraint_date(
        **{"cdb_object_id": cdb_object_id, "_constraint_date": _constraint_date}
    )


@router.json(":time_schedule_id/update_columns_visibility/post")
def update_column_visibility(page, time_schedule_id):
    column_name = page.get_form_data("column_name")
    visible = 1 if TimeScheduleHelper.is_JSON_true(page.get_form_data("visible")) else 0
    ChartConfig.setValue(
        auth.persno, time_schedule_id, column_name, "visible", str(visible)
    )
    return


@router.json(":time_schedule_id/update_columns_width/post")
def update_columns_width(page, time_schedule_id):
    column_name = page.get_form_data("column_name")
    width = int(page.get_form_data("width"))
    ChartConfig.setValue(
        auth.persno, time_schedule_id, column_name, "width", str(width)
    )
    return


@router.json(":time_schedule_id/update_columns_collapsed/post")
def update_columns_collapsed(page, time_schedule_id):
    columns_collapsed = (
        1
        if TimeScheduleHelper.is_JSON_true(page.get_form_data("columns_collapsed"))
        else 0
    )
    ChartConfig.setValue(
        auth.persno,
        time_schedule_id,
        "#config#",
        "columns_collapsed",
        str(columns_collapsed),
    )
    return


@router.json(":time_schedule_id/update_left_panel_width/post")
def update_left_panel_width(page, time_schedule_id):
    left_panel_width = page.get_form_data("left_panel_width")
    ChartConfig.setValue(
        auth.persno,
        time_schedule_id,
        "#config#",
        "left_panel_width",
        int(left_panel_width),
    )
    return


@BaseHelper.exception_decorator
def _delete_relations(**kwargs):
    relations = kwargs["relations"]
    for relation in relations:
        operation(kOperationDelete, relation)


@router.json(":time_schedule_id/delete_relations/post")
def delete_relations(page, time_schedule_id):
    primary_keys = json.loads(page.get_form_data("primary_keys"))
    relations = []
    for key in primary_keys:
        relation = TaskRelation.ByKeys(**key)
        if relation:
            relations.append(relation)
    return _delete_relations(**{"relations": relations})


@BaseHelper.exception_decorator
def _move_relations(**kwargs):
    relations = kwargs["relations"]
    for (relation, minimal_gap) in relations:
        operation(kOperationModify, relation, **{"minimal_gap": minimal_gap})


@router.json(":time_schedule_id/move_relations/post")
def move_relations(page, time_schedule_id):
    primary_keys = json.loads(page.get_form_data("primary_keys"))
    relations = []
    for key in primary_keys:
        minimal_gap = key.pop("minimal_gap")
        if not minimal_gap:
            minimal_gap = 0
        relation = TaskRelation.ByKeys(**key)
        if relation:
            relations.append((relation, minimal_gap))
    return _move_relations(**{"relations": relations})


@router.json(":time_schedule_id/update_time_frame/post")
def update_time_frame(page, time_schedule_id):
    personal_start_date = page.get_form_data("personal_start_date")
    pixels_per_day = page.get_form_data("pixels_per_day")
    if personal_start_date:
        ChartConfig.setValue(
            auth.persno,
            time_schedule_id,
            "#config#",
            "personal_start_date",
            str(personal_start_date),
        )
    if pixels_per_day:
        ChartConfig.setValue(
            auth.persno,
            time_schedule_id,
            "#config#",
            "pixels_per_day",
            str(pixels_per_day),
        )
    return


@BaseHelper.exception_decorator
def _update_early_position(**kwargs):
    cdb_object_id = kwargs["cdb_object_id"]
    if cdb_object_id:
        obj = ByID(cdb_object_id)
        if obj:
            obj.setEarlyPosition(kwargs["new_position"])
    return


@router.json(":time_schedule_id/update_early_position/post")
def update_early_position(page, time_schedule_id):
    new_position = page.get_form_data("early_position")
    new_position = int(new_position) if new_position else ""
    cdb_object_id = page.get_form_data("cdb_object_id")
    return _update_early_position(
        **{"new_position": new_position, "cdb_object_id": cdb_object_id}
    )


@BaseHelper.exception_decorator
def _update_automatic(**kwargs):
    cdb_object_id = kwargs["cdb_object_id"]
    if cdb_object_id:
        obj = ByID(cdb_object_id)
        if obj:
            obj.setAutomatic(kwargs["new_automatic"])
    return


@router.json(":time_schedule_id/update_automatic/post")
def update_automatic(page, time_schedule_id):
    new_automatic = page.get_form_data("automatic")
    new_automatic = int(new_automatic) if new_automatic else ""
    cdb_object_id = page.get_form_data("cdb_object_id")
    return _update_automatic(
        **{"new_automatic": new_automatic, "cdb_object_id": cdb_object_id}
    )


@BaseHelper.exception_decorator
def _update_auto_update_time(**kwargs):
    cdb_object_id = kwargs["cdb_object_id"]
    if cdb_object_id:
        obj = ByID(cdb_object_id)
        if obj:
            obj.setAutoUpdateTime(kwargs["new_auto"])
    return


@router.json(":time_schedule_id/update_auto_update_time/post")
def update_auto_update_time(page, time_schedule_id):
    new_auto = page.get_form_data("auto_update_time")
    new_auto = int(new_auto) if new_auto else ""
    cdb_object_id = page.get_form_data("cdb_object_id")
    return _update_auto_update_time(
        **{"new_auto": new_auto, "cdb_object_id": cdb_object_id}
    )


@BaseHelper.exception_decorator
def _get_one_object(**kwargs):
    cdb_object_id = kwargs["cdb_object_id"]
    time_schedule_id = kwargs["time_schedule_id"]
    obj = ByID(cdb_object_id)
    if not obj:
        raise ue.Exception("cdb_inv_joined_obj", "cdb_object_id= %s" % cdb_object_id)
    else:
        return TimeScheduleHelper.get_data_for_objects(
            time_schedule_id, [obj], {obj.cdb_object_id: None}
        ).get(obj.cdb_object_id, {})
    return


@router.json(":time_schedule_id/get_one_object")
def get_one_object(page, time_schedule_id):
    cdb_object_id = page.get_form_data("cdb_object_id")
    return _get_one_object(
        **{"cdb_object_id": cdb_object_id, "time_schedule_id": time_schedule_id}
    )
