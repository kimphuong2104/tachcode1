#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from datetime import datetime
from functools import reduce

from cdb import auth
from cdb.fls import get_license
from cdb.objects import ClassRegistry
from cdb.platform.mom.entities import CDBClassDef

from cs.pcs.timeschedule import (
    ColumnDefinition,
    TimeSchedule,
    TimeScheduleObject,
    TSHelper,
)
from cs.pcs.timeschedule.new_base_chart.helper import BaseHelper


class TimeScheduleHelper:
    @staticmethod
    def find_parent_cls(classname):
        cd = CDBClassDef(classname)
        return ClassRegistry().find(cd.getPrimaryTable())

    @staticmethod
    def get_object_list(schedule):
        objs = []
        ts_objs = []
        if schedule:
            ts_objs = TimeScheduleObject.Query(
                TimeScheduleObject.view_oid == schedule.cdb_object_id,
                order_by="position",
            )
            classnames = list(set([tso.cdb_content_classname for tso in ts_objs]))
            _objs = []
            for classname in classnames:
                cls = TimeScheduleHelper.find_parent_cls(classname)
                obj_ids = [
                    tso.content_oid
                    for tso in ts_objs
                    if tso.cdb_content_classname == classname
                ]
                _objs += cls.KeywordQuery(cdb_object_id=obj_ids)
            # keep correct objs order
            id2idx = {obj.cdb_object_id: idx for (idx, obj) in enumerate(_objs)}
            objs = [_objs[id2idx[tso.content_oid]] for tso in ts_objs]
        return objs, ts_objs

    @staticmethod
    def get_schedule(schedule_oid):
        schedule = None
        schedule_list = TimeSchedule.KeywordQuery(cdb_object_id=schedule_oid)
        if schedule_list:
            schedule = schedule_list[0]
        return schedule

    @staticmethod
    def is_JSON_true(val):
        return val and val.lower() in ("true", "True", "yes", "t", "1")

    @staticmethod
    def get_expanded_children_structure(
        parent_obj,
        ids_client=None,
        loaded_time_stamp=None,
        expanded_ids=None,
        ids_server=None,
        pinned_oid=None,
    ):
        if ids_client is None:
            ids_client = []
        if expanded_ids is None:
            expanded_ids = []
        if ids_server is None:
            ids_server = []
        my_obj = None
        if (
            loaded_time_stamp is None
            or parent_obj.cdb_object_id not in ids_server
            and (
                (parent_obj.cdb_object_id not in ids_client)
                or (
                    hasattr(parent_obj, "cdb_mdate")
                    and bool(parent_obj.cdb_mdate)
                    and TSHelper.date2utc(parent_obj.cdb_mdate) >= loaded_time_stamp
                )
                or (
                    hasattr(parent_obj, "cdb_adate")
                    and bool(parent_obj.cdb_adate)
                    and TSHelper.date2utc(parent_obj.cdb_adate) >= loaded_time_stamp
                )
            )
        ):
            my_obj = parent_obj
        try:
            ids_server.index(parent_obj.cdb_object_id)
        except ValueError:
            ids_server.append(parent_obj.cdb_object_id)
        sc_structure = {parent_obj.cdb_object_id: {"obj": my_obj, "children": []}}
        if pinned_oid is None:
            pinned_oid = parent_obj.cdb_object_id

        expand_children = parent_obj.cdb_object_id in expanded_ids
        if expand_children:
            children = parent_obj.getChildrenObjects()
            for child in children:
                rec_result = TimeScheduleHelper.get_expanded_children_structure(
                    child,
                    ids_client,
                    loaded_time_stamp,
                    expanded_ids,
                    ids_server,
                    pinned_oid,
                )
                sc_structure[parent_obj.cdb_object_id]["children"].append(
                    rec_result["sc_structure"]
                )
                ids_server = rec_result["ids_server"]
        return dict(sc_structure=sc_structure, ids_server=ids_server)

    @staticmethod
    def get_changed_data(
        time_schedule_id, loaded_time_stamp=None, ids_client=None, expanded_ids=None
    ):
        if ids_client is None:
            ids_client = []
        if expanded_ids is None:
            expanded_ids = []
        # FIXME objects -> SQL
        schedule = TimeScheduleHelper.get_schedule(time_schedule_id)
        if not schedule:
            return dict(scheduleContents=[])
        objs, ts_objs = TimeScheduleHelper.get_object_list(schedule)
        ids_server = []
        sc_structure = []
        # recursively get structure with raw objects. will get data for them afterwards
        for obj in objs:
            # obj is a pinned object
            result = TimeScheduleHelper.get_expanded_children_structure(
                obj, ids_client, loaded_time_stamp, expanded_ids, ids_server
            )
            sc_structure.append(result["sc_structure"])
            ids_server = result["ids_server"]

        # objs that we need data for
        objs_server = TimeScheduleHelper.parse_structure(sc_structure, [])
        obj_id_2_tso = reduce(
            lambda x, y: x.update(y) or x, [{x.content_oid: x} for x in ts_objs], {}
        )
        objs_data = TimeScheduleHelper.get_data_for_objects(
            time_schedule_id, objs_server, obj_id_2_tso
        )
        scheduleContents = TimeScheduleHelper.get_structure_with_data(
            sc_structure, objs_data
        )
        return dict(
            scheduleContents=scheduleContents,
            loaded_time_stamp=TSHelper.date2utc(datetime.utcnow()),
        )

    @staticmethod
    def get_structure_with_data(sc_structure, objs_data):
        for sc in sc_structure:
            vals = list(sc.values())[0]
            obj = vals["obj"]
            if obj:
                vals["obj"] = objs_data[obj.cdb_object_id]
            children = vals["children"]
            if len(children):
                children = TimeScheduleHelper.get_structure_with_data(
                    children, objs_data
                )
        return sc_structure

    @staticmethod
    def get_data_for_objects(time_schedule_id, objs_server, obj_id_2_tso):
        objs_server_by_class = TimeScheduleHelper.objs_by_class(objs_server)
        # dict of cdb_object_id: data_dict
        data = {}
        has_licence = get_license("TIMESCHEDULE_005")
        for key in list(objs_server_by_class):
            data.update(
                TimeScheduleHelper.get_data_for_objects_by_class(
                    time_schedule_id,
                    objs_server_by_class[key],
                    key,
                    obj_id_2_tso,
                    has_licence,
                )
            )
        return data

    @staticmethod
    def get_data_for_objects_by_class(
        time_schedule_id, objs, classname, obj_id_2_tso, has_licence
    ):
        # if you find a way to get the correct class definition by
        # classname, that ACTUALLY WORKS for inherited classes
        # in our object framework, replace this
        cls = objs[0].__class__
        # dict of cdb_object_id: data_dict
        data = {obj.cdb_object_id: {} for obj in objs}
        columns = ColumnDefinition.KeywordQuery(
            chart="timeschedule", order_by="position"
        )
        config_dict = {}
        columns_config = BaseHelper.get_chart_columns(auth.persno, time_schedule_id)
        for config in columns_config:
            config_dict[config["name"]] = config
        attrs = [
            "obj_icon",
            "status_color",
            "title",
            "operations",
            "project_number",
            "start_date",
            "end_date",
            "start_date_plan",
            "end_date_plan",
        ]
        for column in columns:
            cfg = config_dict[column.name]
            if cfg["visible"] or column.name in attrs:
                # Optimization: direct sql instead for calling relations for each object
                # implemented when effort per performance gain is worth it
                cls_col_val_name = "get_ts_col_val_" + column.name
                if hasattr(cls, cls_col_val_name):
                    col_data = getattr(cls, cls_col_val_name)(objs, obj_id_2_tso)
                    for d, o in zip(col_data, objs):
                        data[o.cdb_object_id].update({column.name: d})
                else:
                    for obj in objs:
                        ts_obj = obj_id_2_tso.get(obj.cdb_object_id, None)
                        data[obj.cdb_object_id].update(
                            {column.name: column.get_column_value(obj, ts_obj)}
                        )
            else:
                for obj in objs:
                    data[obj.cdb_object_id].update({column.name: None})
        for obj in objs:
            data[obj.cdb_object_id].update(
                obj.getTSFieldsPerObject(has_licence=has_licence, asynchronous=True)
            )
        # Optimization: direct sql instead for calling relations for each object
        objs_more_data = cls.getTSFieldsPerClass(objs)
        for d, o in zip(objs_more_data, objs):
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
    def parse_structure(sc_structure, objs_server=None):
        if objs_server is None:
            objs_server = []
        # gets objects from structure
        for sc in sc_structure:
            vals = list(sc.values())[0]
            obj = vals["obj"]
            if obj:
                objs_server.append(obj)
            children = vals["children"]
            if len(children):
                objs_server = TimeScheduleHelper.parse_structure(children, objs_server)
        return objs_server
