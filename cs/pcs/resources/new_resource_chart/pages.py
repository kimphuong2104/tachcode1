#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import json

from cdb import auth, elink, sqlapi, ue
from cdb.constants import kOperationDelete, kOperationNew
from cdb.elink.engines.chameleon.engine import _OpHelper
from cdb.objects import ByID, IconCache
from cdb.objects.operations import operation
from cs.pcs.projects.chart import ChartConfig
from cs.pcs.resources.new_resource_chart.helper import ResourceScheduleHelper
from cs.pcs.resources.resourceschedule import (
    ResourceColumnDefinition,
    ResourceScheduleObject,
)
from cs.pcs.timeschedule import TSHelper, new_base_chart
from cs.pcs.timeschedule.new_base_chart import _getapp as _base_getapp
from cs.pcs.timeschedule.new_base_chart import nanoroute
from cs.pcs.timeschedule.new_base_chart.helper import BaseHelper


class MyPage(elink.VirtualPathTemplate):
    __template__ = "index.html"

    def render(self, context):
        vpath = self.get_path_segments(cleanup=True)
        resource_schedule_id = vpath[0] if len(vpath) else ""  # pylint: disable=C1801
        resource_schedule = ResourceScheduleHelper.get_schedule(resource_schedule_id)
        base_app = _base_getapp()
        resource_app = self.application
        result = {
            "resource_schedule": resource_schedule,
            "base_macros": base_app.getTemplates(),
            "base_localres": base_app.getURLPaths()["localres"],
            "resource_macros": resource_app.getTemplates(),
        }
        if not resource_schedule:
            return result
        result.update(
            {
                "resource_localres": resource_app.getURLPaths()["localres"],
                "time_localres": None,
                "time_schedule": None,
                "time_macros": None,
                "app_base_data": "%sbase_api" % (base_app.getURLPaths()["approot"]),
                "app_time_data": None,
                "app_resource_data": "%sresource_api/%s"
                % (resource_app.getURLPaths()["approot"], resource_schedule_id),
                "app_full_data": None,
                "chart_type": "resource",
                "custom_base_templates": BaseHelper.get_custom_templates(
                    new_base_chart.__path__[0]
                ),
                "custom_resource_templates": BaseHelper.get_custom_templates(__file__),
                "resources_marked_objects_attrs": ResourceScheduleHelper.get_marked_objects_attrs(),
            }
        )
        return result


router = nanoroute.LookUp()


# =======================
# handle data api request
# =======================
@router.json(":resource_schedule_id/refresh_data")
def get_changed_app_content(page, resource_schedule_id):
    loaded_time_stamp = page.get_form_data("loaded_time_stamp")
    expanded_ids = json.loads(page.get_form_data("expanded_ids"))
    demand_expanded_ids = json.loads(page.get_form_data("demand_expanded_ids"))
    assignment_expanded_ids = json.loads(page.get_form_data("assignment_expanded_ids"))
    evaluate_project_ids = page.get_form_data("evaluate_project_ids")
    evaluate_project_ids = (
        [x.strip() for x in evaluate_project_ids.split(",")]
        if evaluate_project_ids
        else []
    )
    start = page.get_form_data("start")
    end = page.get_form_data("end")
    use_serverside_settings = ResourceScheduleHelper.is_JSON_true(
        page.get_form_data("use_serverside_settings")
    )
    # first load, get saved expanded_ids
    if use_serverside_settings:
        demand_expanded_ids = ChartConfig.getSetting(
            auth.persno, resource_schedule_id, setting_name="#expandedDemandId#"
        )
        assignment_expanded_ids = ChartConfig.getSetting(
            auth.persno, resource_schedule_id, setting_name="#expandedAssignmentId#"
        )
        expanded_ids = ChartConfig.getSetting(
            auth.persno, resource_schedule_id, setting_name="#expandedId#"
        )
        evaluate_project_ids = ChartConfig.getValue(
            auth.persno, resource_schedule_id, "#config#", "evaluate_project_ids"
        )
        evaluate_project_ids = (
            [x.strip() for x in evaluate_project_ids.split(",")]
            if evaluate_project_ids
            else []
        )
    # save expanded_ids
    else:
        ChartConfig.setSetting(
            auth.persno, resource_schedule_id, expanded_ids, setting_name="#expandedId#"
        )
        ChartConfig.setSetting(
            auth.persno,
            resource_schedule_id,
            demand_expanded_ids,
            setting_name="#expandedDemandId#",
        )
        ChartConfig.setSetting(
            auth.persno,
            resource_schedule_id,
            assignment_expanded_ids,
            setting_name="#expandedAssignmentId#",
        )
    return ResourceScheduleHelper.get_changed_data(
        resource_schedule_id=resource_schedule_id,
        start=TSHelper.utc2date(start),
        end=TSHelper.utc2date(end),
        evaluate_project_ids=evaluate_project_ids,
        loaded_time_stamp=loaded_time_stamp,
        expanded_ids=expanded_ids,
        demand_expanded_ids=demand_expanded_ids,
        assignment_expanded_ids=assignment_expanded_ids,
    )


@router.json(":schedule_id/settings")
def get_app_settings(page, schedule_id):
    schedule = ResourceScheduleHelper.get_schedule(schedule_id)
    if not schedule:
        return None
    chart_type = page.get_form_data("chart_type")
    columns = []
    columns_instances = ResourceColumnDefinition.KeywordQuery(
        chart="resources", order_by="position"
    )
    permission_denied = not schedule.CheckAccess("save", auth.persno)
    evaluate_project_ids = ChartConfig.getValue(
        auth.persno, schedule_id, "#config#", "evaluate_project_ids"
    )
    display_project_depended = ChartConfig.getValue(
        auth.persno, schedule_id, "#config#", "display_project_depended"
    )
    display_project_depended = (
        bool(int(display_project_depended)) if display_project_depended else False
    )
    for col_inst in columns_instances:
        columns.append(BaseHelper.get_column_config(col_inst, auth.persno, schedule_id))
    ts_ops = []
    op_list = _OpHelper.get_object_operations_for_context(
        schedule, "res_resourceschedule_resourceschedule", "CDB_ShowObject"
    )
    for op in op_list:
        ts_ops.append(TSHelper.get_op_info(op))
    result = {
        "_columns_as_dict": columns,
        "ts_ops": ts_ops,
        "default_info_icon": IconCache.getIcon("Information"),
        "schedule_permission_denied": permission_denied,
        "evaluateProjectIds": evaluate_project_ids,
        "displayProjectDepended": display_project_depended,
    }
    if chart_type == "resource":
        columns_collapsed = ChartConfig.getValue(
            auth.persno, schedule_id, "#config#", "columns_collapsed"
        )
        columns_collapsed = bool(int(columns_collapsed)) if columns_collapsed else False
        left_panel_width = ChartConfig.getValue(
            auth.persno, schedule_id, "#config#", "left_panel_width"
        )
        left_panel_width = int(left_panel_width) if left_panel_width else None
        personal_start_date = ChartConfig.getValue(
            auth.persno, schedule_id, "#config#", "personal_start_date"
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


@router.json(":resource_schedule_id/load_async_data")
def load_async_data(page, resource_schedule_id):
    obj_ids = json.loads(page.get_form_data("obj_ids"))
    schedule = ResourceScheduleHelper.get_schedule(resource_schedule_id)
    evaluate_project_ids = page.get_form_data("evaluate_project_ids")
    evaluate_project_ids = (
        [x.strip() for x in evaluate_project_ids.split(",")]
        if evaluate_project_ids
        else []
    )
    start = TSHelper.utc2date(page.get_form_data("start"))
    end = TSHelper.utc2date(page.get_form_data("end"))
    scale = page.get_form_data("scale")
    has_licence = True
    objs_data = {}
    for oid in obj_ids:
        obj = ByID(oid)
        if obj:
            objs_data[oid] = obj.getTSFieldsAsync(has_licence)
        else:
            objs_data[oid] = {}
    (scheduleContents, start_date, end_date) = ResourceScheduleHelper.get_chart_data(
        schedule=schedule,
        ids=obj_ids,
        scale=scale,
        start=start,
        end=end,
        evaluate_project_ids=evaluate_project_ids,
    )
    return {
        "scheduleContents": scheduleContents,
        "start_date": start_date,
        "end_date": end_date,
    }


@BaseHelper.exception_decorator
def _save_expanded_ids(**kwargs):
    ChartConfig.setSetting(
        auth.persno,
        kwargs["resource_schedule_id"],
        kwargs["expanded_ids"],
        setting_name="#expandedId#",
    )


@router.json(":resource_schedule_id/save_expanded_ids/post")
def save_expanded_ids(page, resource_schedule_id):
    expanded_ids = json.loads(page.get_form_data("expanded_ids"))
    return _save_expanded_ids(
        **{"resource_schedule_id": resource_schedule_id, "expanded_ids": expanded_ids}
    )


@router.json(":resource_schedule_id/update_time_frame/post")
def update_time_frame(page, resource_schedule_id):
    personal_start_date = page.get_form_data("personal_start_date")
    pixels_per_day = page.get_form_data("pixels_per_day")
    if personal_start_date:
        ChartConfig.setValue(
            auth.persno,
            resource_schedule_id,
            "#config#",
            "personal_start_date",
            str(personal_start_date),
        )
    if pixels_per_day:
        ChartConfig.setValue(
            auth.persno,
            resource_schedule_id,
            "#config#",
            "pixels_per_day",
            str(pixels_per_day),
        )


@BaseHelper.exception_decorator
def _save_expanded_demand_ids(**kwargs):
    ChartConfig.setSetting(
        auth.persno,
        kwargs["resource_schedule_id"],
        kwargs["demand_expanded_ids"],
        setting_name="#expandedDemandId#",
    )


@router.json(":resource_schedule_id/save_expanded_demand_ids/post")
def save_expanded_demand_ids(page, resource_schedule_id):
    demand_expanded_ids = json.loads(page.get_form_data("demand_expanded_ids"))
    return _save_expanded_demand_ids(
        **{
            "resource_schedule_id": resource_schedule_id,
            "demand_expanded_ids": demand_expanded_ids,
        }
    )


@BaseHelper.exception_decorator
def _save_expanded_assignment_ids(**kwargs):
    ChartConfig.setSetting(
        auth.persno,
        kwargs["resource_schedule_id"],
        kwargs["assignment_expanded_ids"],
        setting_name="#expandedAssignmentId#",
    )


@router.json(":resource_schedule_id/save_expanded_assignment_ids/post")
def save_expanded_assignment_ids(page, resource_schedule_id):
    assignment_expanded_ids = json.loads(page.get_form_data("assignment_expanded_ids"))
    return _save_expanded_assignment_ids(
        **{
            "resource_schedule_id": resource_schedule_id,
            "assignment_expanded_ids": assignment_expanded_ids,
        }
    )


@BaseHelper.exception_decorator
def _update_demand(**kwargs):
    cdb_object_id = kwargs["cdb_object_id"]
    if cdb_object_id:
        obj = ByID(cdb_object_id)
        obj.setDemand(hours=kwargs["new_demand"])


@router.json(":resource_schedule_id/update_demand/post")
def update_demand(page, resource_schedule_id):
    new_demand = page.get_form_data("demand")
    new_demand = float(new_demand) if new_demand else 0.0
    cdb_object_id = page.get_form_data("cdb_object_id")
    return _update_demand(**{"new_demand": new_demand, "cdb_object_id": cdb_object_id})


@BaseHelper.exception_decorator
def _update_assignment(**kwargs):
    cdb_object_id = kwargs["cdb_object_id"]
    if cdb_object_id:
        obj = ByID(cdb_object_id)
        obj.setAssignment(hours=kwargs["new_assignment"])


@router.json(":resource_schedule_id/update_assignment/post")
def update_assignment(page, resource_schedule_id):
    new_assignment = page.get_form_data("assignment")
    new_assignment = float(new_assignment) if new_assignment else 0.0
    cdb_object_id = page.get_form_data("cdb_object_id")
    return _update_assignment(
        **{"new_assignment": new_assignment, "cdb_object_id": cdb_object_id}
    )


@router.json(":resource_schedule_id/update_columns_collapsed/post")
def update_columns_collapsed(page, resource_schedule_id):
    columns_collapsed = (
        1
        if ResourceScheduleHelper.is_JSON_true(page.get_form_data("columns_collapsed"))
        else 0
    )
    ChartConfig.setValue(
        auth.persno,
        resource_schedule_id,
        "#config#",
        "columns_collapsed",
        str(columns_collapsed),
    )


@router.json(":resource_schedule_id/update_display_project_depended/post")
def update_display_project_depended(page, resource_schedule_id):
    display_project_depended = (
        1
        if ResourceScheduleHelper.is_JSON_true(
            page.get_form_data("display_project_depended")
        )
        else 0
    )
    ChartConfig.setValue(
        auth.persno,
        resource_schedule_id,
        "#config#",
        "display_project_depended",
        str(display_project_depended),
    )


@router.json(":resource_schedule_id/update_evaluate_project_ids/post")
def evaluate_project_ids(page, resource_schedule_id):
    evaluate_project_ids = page.get_form_data("evaluate_project_ids")
    ChartConfig.setValue(
        auth.persno,
        resource_schedule_id,
        "#config#",
        "evaluate_project_ids",
        str(evaluate_project_ids),
    )


@BaseHelper.exception_decorator
def _change_position(**kwargs):
    schedule = ByID(kwargs["resource_schedule_id"])
    ids = kwargs["ids"]
    for tsc in schedule.ResourceScheduleContents:
        tsc.position = ids.index(tsc.content_oid)


@router.json(":resource_schedule_id/change_position/post")
def change_position(page, resource_schedule_id):
    ids = json.loads(page.get_form_data("ids"))
    return _change_position(
        **{"resource_schedule_id": resource_schedule_id, "ids": ids}
    )


@BaseHelper.exception_decorator
def _update_columns(**kwargs):
    columns = kwargs["columns"]
    time_schedule_id = kwargs["resource_schedule_id"]
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


@router.json(":resource_schedule_id/update_columns/post")
def update_columns(page, resource_schedule_id):
    columns = json.loads(page.get_form_data("columns"))
    return _update_columns(
        **{"resource_schedule_id": resource_schedule_id, "columns": columns}
    )


@router.json(":resource_schedule_id/update_left_panel_width/post")
def update_left_panel_width(page, resource_schedule_id):
    left_panel_width = page.get_form_data("left_panel_width")
    ChartConfig.setValue(
        auth.persno,
        resource_schedule_id,
        "#config#",
        "left_panel_width",
        int(left_panel_width),
    )


@router.json(":resource_schedule_id/update_columns_width/post")
def update_columns_width(page, resource_schedule_id):
    column_name = page.get_form_data("column_name")
    width = int(page.get_form_data("width"))
    ChartConfig.setValue(
        auth.persno, resource_schedule_id, column_name, "width", str(width)
    )


@BaseHelper.exception_decorator
def _reveal_id(**kwargs):
    schedule = ByID(kwargs["resource_schedule_id"])
    rso = ByID(kwargs["my_id"])
    schedule.reveal_rso_in_schedule(rso, True)


@router.json(":resource_schedule_id/reveal_id/post")
def reveal_id(page, resource_schedule_id):
    my_id = page.get_form_data("id")
    return _reveal_id(**{"resource_schedule_id": resource_schedule_id, "my_id": my_id})


@BaseHelper.exception_decorator
def _fully_expand_id(**kwargs):
    schedule = ByID(kwargs["resource_schedule_id"])
    rso = ByID(kwargs["my_id"])
    schedule.fully_expand_rso_in_schedule(rso)


@router.json(":resource_schedule_id/fully_expand_id/post")
def fully_expand_id(page, resource_schedule_id):
    my_id = page.get_form_data("id")
    return _fully_expand_id(
        **{"resource_schedule_id": resource_schedule_id, "my_id": my_id}
    )


@BaseHelper.exception_decorator
def _toggle_rs_obj_in(**kwargs):
    operation(kOperationNew, ResourceScheduleObject, **kwargs)


@BaseHelper.exception_decorator
def _toggle_rs_obj_out(**kwargs):
    # need to remove expandedId settings for children which are no longer displayed
    rso = kwargs["rso"]
    expanded_ids = ChartConfig.getSetting(
        auth.persno, rso.view_oid, setting_name="#expandedId#"
    )
    s = """SELECT content_oid FROM cdbpcs_rs_content WHERE view_oid = '%s'""" % (
        rso.view_oid
    )
    rs = sqlapi.RecordSet2(sql=s)
    ids_in_schedule = [e["content_oid"] for e in rs]
    obj = rso.getContentObject()

    def remove_settings(obj, expanded_ids):
        if obj.cdb_object_id in expanded_ids:
            expanded_ids.remove(obj.cdb_object_id)
            children = obj.getChildrenObjects()
            for child in children:
                if not child.cdb_object_id in ids_in_schedule:  # noqa
                    expanded_ids = remove_settings(child, expanded_ids)
        return expanded_ids

    operation(kOperationDelete, kwargs["rso"])
    remove_settings(obj, expanded_ids)
    ChartConfig.setSetting(
        auth.persno, rso.view_oid, expanded_ids, setting_name="#expandedId#"
    )


@router.json(":resource_schedule_id/toggle_rs_obj/post")
def toggle_rs_obj(page, resource_schedule_id):  # pylint: disable=R1710
    oid = page.get_form_data("oid")
    in_schedule = ResourceScheduleHelper.is_JSON_true(page.get_form_data("inSchedule"))
    if not in_schedule:
        rso = ResourceScheduleObject.ByKeys(
            view_oid=resource_schedule_id, content_oid=oid
        )
        if not rso:
            return {"error": str(ue.Exception("cdbpcs_error"))}
        return _toggle_rs_obj_out(**{"rso": rso})
    else:
        obj = ByID(oid)
        if not obj:
            return {"error": str(ue.Exception("cdbpcs_error"))}
        kwargs = {
            "view_oid": resource_schedule_id,
            "content_oid": oid,
            "cdb_content_classname": obj.GetClassname(),
            "cdb_project_id": "",
        }
        return _toggle_rs_obj_in(**kwargs)
