#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=W0102,C1801,R0913,W0622,too-many-locals

import functools
import itertools
from datetime import datetime

from cdb import auth, sqlapi
from cdb.objects import ClassRegistry
from cdb.platform.mom.entities import CDBClassDef
from cs.pcs.projects.chart import ChartConfig
from cs.pcs.resources.resourceschedule import (
    ResourceColumnDefinition,
    ResourceSchedule,
    ResourceScheduleObject,
)
from cs.pcs.timeschedule import TSHelper


class ResourceScheduleHelper:
    @staticmethod
    def find_parent_cls(classname):
        cd = CDBClassDef(classname)
        return ClassRegistry().find(cd.getPrimaryTable())

    @staticmethod
    def get_marked_objects_attrs():
        return [
            {
                "classname": "cdbpcs_pool_person_assign",
                "key": "objCdbObjectId",
                "attr_name": "by_rpa_id",
            },
            {
                "classname": "cdbpcs_resource_pool",
                "key": "objCdbObjectId",
                "attr_name": "by_pool_id",
            },
            {
                "classname": "cdbpcs_prj_demand",
                "key": "objCdbObjectId",
                "attr_name": "by_resource_id",
            },
            {
                "classname": "cdbpcs_prj_alloc",
                "key": "objCdbObjectId",
                "attr_name": "by_resource_id",
            },
        ]

    @staticmethod
    def is_JSON_true(val):
        return val.lower() in {"true", "True", "yes", "t", "1"}

    @staticmethod
    def get_object_list(schedule):
        objs = []
        rs_objs = []
        if schedule:
            rs_objs = ResourceScheduleObject.Query(
                ResourceScheduleObject.view_oid == schedule.cdb_object_id,
                order_by="position",
            )
            classnames = list({rso.cdb_content_classname for rso in rs_objs})
            _objs = []
            for classname in classnames:
                cls = ResourceScheduleHelper.find_parent_cls(classname)
                obj_ids = [
                    rso.content_oid
                    for rso in rs_objs
                    if rso.cdb_content_classname == classname
                ]
                _objs += cls.KeywordQuery(cdb_object_id=obj_ids)
            # keep correct objs order
            id2idx = {obj.cdb_object_id: idx for (idx, obj) in enumerate(_objs)}
            objs = [_objs[id2idx[rso.content_oid]] for rso in rs_objs]
        return objs, rs_objs

    @staticmethod
    def get_schedule(schedule_oid):
        schedule = None
        schedule_list = ResourceSchedule.KeywordQuery(cdb_object_id=schedule_oid)
        if schedule_list:
            schedule = schedule_list[0]
        return schedule

    @staticmethod
    def get_expanded_children_structure(
        parent_obj,
        start,
        end,
        evaluate_project_ids,
        loaded_time_stamp=None,
        expanded_ids=[],
        demand_expanded_ids=[],
        assignment_expanded_ids=[],
        ids_server=[],
    ):
        my_obj = None
        if loaded_time_stamp is None or parent_obj.cdb_object_id not in ids_server:
            my_obj = parent_obj
        try:
            ids_server.index(parent_obj.cdb_object_id)
        except ValueError:
            ids_server.append(parent_obj.cdb_object_id)
        sc_structure = {parent_obj.cdb_object_id: {"obj": my_obj, "children": []}}
        expand_children = parent_obj.cdb_object_id in expanded_ids
        expand_demands = parent_obj.cdb_object_id in demand_expanded_ids
        expand_assignments = parent_obj.cdb_object_id in assignment_expanded_ids
        if expand_children or expand_demands or expand_assignments:
            children = []
            if expand_demands:
                children += parent_obj.getRSDemands(
                    start=start, end=end, prj_ids=evaluate_project_ids
                )
            if expand_assignments:
                children += parent_obj.getRSAssignments(
                    start=start, end=end, prj_ids=evaluate_project_ids
                )
            if expand_children:
                children += parent_obj.getChildrenObjects(start=start, end=end)
            for child in children:
                rec_result = ResourceScheduleHelper.get_expanded_children_structure(
                    child,
                    start,
                    end,
                    evaluate_project_ids,
                    loaded_time_stamp,
                    expanded_ids,
                    demand_expanded_ids,
                    assignment_expanded_ids,
                    ids_server,
                )
                sc_structure[parent_obj.cdb_object_id]["children"].append(
                    rec_result["sc_structure"]
                )
                ids_server = rec_result["ids_server"]
        return {"sc_structure": sc_structure, "ids_server": ids_server}

    @staticmethod
    def get_changed_data(
        resource_schedule_id,
        start,
        end,
        evaluate_project_ids,
        loaded_time_stamp=None,
        expanded_ids=[],
        demand_expanded_ids=[],
        assignment_expanded_ids=[],
    ):
        schedule = ResourceScheduleHelper.get_schedule(resource_schedule_id)
        if not schedule:
            return {"scheduleContents": [], "start_date": start, "end_date": end}
        objs, rs_objs = ResourceScheduleHelper.get_object_list(schedule)

        if (not loaded_time_stamp) or (
            (hasattr(loaded_time_stamp, "__len__") and not len(loaded_time_stamp))
        ):
            # first load, get saved expanded_ids
            demand_expanded_ids = ChartConfig.getSetting(
                auth.persno, schedule.cdb_object_id, setting_name="#expandedDemandId#"
            )
            assignment_expanded_ids = ChartConfig.getSetting(
                auth.persno,
                schedule.cdb_object_id,
                setting_name="#expandedAssignmentId#",
            )
            expanded_ids = ChartConfig.getSetting(
                auth.persno, schedule.cdb_object_id, setting_name="#expandedId#"
            )
            evaluate_project_ids = ChartConfig.getValue(
                auth.persno, resource_schedule_id, "#config#", "evaluate_project_ids"
            )
            evaluate_project_ids = (
                [x.strip() for x in evaluate_project_ids.split(",")]
                if evaluate_project_ids
                else []
            )
        else:
            # save expanded_ids
            ChartConfig.setSetting(
                auth.persno,
                schedule.cdb_object_id,
                expanded_ids,
                setting_name="#expandedId#",
            )
            ChartConfig.setSetting(
                auth.persno,
                schedule.cdb_object_id,
                demand_expanded_ids,
                setting_name="#expandedDemandId#",
            )
            ChartConfig.setSetting(
                auth.persno,
                schedule.cdb_object_id,
                assignment_expanded_ids,
                setting_name="#expandedAssignmentId#",
            )
        display_project_depended = ChartConfig.getValue(
            auth.persno, resource_schedule_id, "#config#", "display_project_depended"
        )
        display_project_depended = (
            bool(int(display_project_depended)) if display_project_depended else False
        )
        if not display_project_depended:
            evaluate_project_ids = []
        ids_server = []
        sc_structure = []
        # recursively get structure with raw objects. will get data for them afterwards
        for obj in objs:
            personalnummer = getattr(obj, "personalnummer", "")
            if personalnummer and evaluate_project_ids:
                rs = sqlapi.RecordSet2(
                    "cdbpcs_team",
                    "cdb_person_id = '%s' and cdb_project_id in ('%s')"
                    % (personalnummer, "','".join(evaluate_project_ids)),
                )
                if len(rs) == 0:
                    continue
            result = ResourceScheduleHelper.get_expanded_children_structure(
                obj,
                start,
                end,
                evaluate_project_ids,
                loaded_time_stamp,
                expanded_ids,
                demand_expanded_ids,
                assignment_expanded_ids,
                ids_server,
            )
            sc_structure.append(result["sc_structure"])
            ids_server = result["ids_server"]
        # objs that we need data for
        objs_server = ResourceScheduleHelper.parse_structure(sc_structure, [])
        obj_id_2_rso = functools.reduce(
            lambda x, y: x.update(y) or x, [{x.content_oid: x} for x in rs_objs], {}
        )
        objs_data = ResourceScheduleHelper.get_data_for_objects(
            objs_server, obj_id_2_rso
        )
        scheduleContents = ResourceScheduleHelper.get_structure_with_data(
            sc_structure, objs_data
        )
        return {
            "scheduleContents": scheduleContents,
            "start_date": start,
            "end_date": end,
            "loaded_time_stamp": TSHelper.date2utc(datetime.utcnow()),
        }

    @staticmethod
    def get_structure_with_data(sc_structure, objs_data):
        for sc in sc_structure:
            vals = list(sc.values())[0]
            obj = vals["obj"]
            if obj:
                vals["obj"] = objs_data[obj.cdb_object_id]
            children = vals["children"]
            if len(children):
                children = ResourceScheduleHelper.get_structure_with_data(
                    children, objs_data
                )
        return sc_structure

    @staticmethod
    def get_data_for_objects(objs_server, obj_id_2_rso):
        objs_server_by_class = ResourceScheduleHelper.objs_by_class(objs_server)
        # dict of cdb_object_id: data_dict
        data = {}
        has_licence = True
        for key in list(objs_server_by_class):
            data.update(
                ResourceScheduleHelper.get_data_for_objects_by_class(
                    objs_server_by_class[key], key, obj_id_2_rso, has_licence
                )
            )
        return data

    @staticmethod
    def get_data_for_objects_by_class(objs, classname, obj_id_2_rso, has_licence):
        # if you find a way to get the correct class definition by classname, that ACTUALLY WORKS for inherited classes
        # in our object framework, replace this
        cls = objs[0].__class__
        # dict of cdb_object_id: data_dict
        data = {obj.cdb_object_id: {} for obj in objs}
        columns = ResourceColumnDefinition.KeywordQuery(
            chart="resources", order_by="position"
        )
        for column in columns:
            # Optimization: direct sql instead for calling relations for each object
            # implemented when effort per performance gain is worth it
            cls_col_val_name = "get_ts_col_val_" + column.name
            if hasattr(cls, cls_col_val_name):
                col_data = getattr(cls, cls_col_val_name)(objs, obj_id_2_rso)
                for _, d, o in zip(itertools.count(), col_data, objs):
                    data[o.cdb_object_id].update({column.name: d})
            else:
                for obj in objs:
                    ts_obj = obj_id_2_rso.get(obj.cdb_object_id, None)
                    data[obj.cdb_object_id].update(
                        {column.name: column.get_column_value(obj, ts_obj)}
                    )
        for obj in objs:
            data[obj.cdb_object_id].update(
                obj.getTSFieldsPerObject(has_licence=has_licence, a_sync=True)  # noqa
            )
        # Optimization: direct sql instead for calling relations for each object
        objs_more_data = cls.getTSFieldsPerClass(cls, objs)
        for _, d, o in zip(itertools.count(), objs_more_data, objs):
            data[o.cdb_object_id].update(d)
        return data

    @staticmethod
    def objs_by_class(objs_server):
        objs_server_by_class = {}
        keys = []
        for obj in objs_server:
            classname = obj.GetClassname()
            try:
                keys.index(classname)
            except ValueError:
                objs_server_by_class[classname] = []
                keys.append(classname)
            objs_server_by_class[classname].append(obj)
        return objs_server_by_class

    @staticmethod
    def parse_structure(sc_structure, objs_server=[]):
        # gets objects from structure
        for sc in sc_structure:
            vals = list(sc.values())[0]
            obj = vals["obj"]
            if obj:
                objs_server.append(obj)
            children = vals["children"]
            if len(children):
                objs_server = ResourceScheduleHelper.parse_structure(
                    children, objs_server
                )
        return objs_server

    @staticmethod
    def get_chart_data(schedule, ids, scale, start, end, evaluate_project_ids):
        result = {}
        chart_data = schedule.getData(
            ids=ids,
            scale=scale,
            start=start,
            end=end,
            evaluate_project_ids=evaluate_project_ids,
        )
        for id in ids:
            chart_total_entries = chart_data["total_entries"].get(id, [])
            chart_project_entries = chart_data["project_entries"].get(
                id, [[0, 0, 0]] * len(chart_total_entries)
            )
            result[id] = [
                list(itertools.chain.from_iterable(x))
                for x in zip(chart_total_entries, chart_project_entries)
            ]
        return (
            result,
            TSHelper.date2utc(chart_data["start_date"]),
            TSHelper.date2utc(chart_data["end_date"]),
        )
