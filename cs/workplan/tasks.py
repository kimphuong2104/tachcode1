#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb.objects import Object, Reference_N, Reference_1, Forward
from cdb import sqlapi, ue, util
from cdb.cad import isTrue

fTaskInputParts = Forward(__name__ + ".TaskInputParts")
fTaskPrtParts = Forward(__name__ + ".TaskPrtParts")
fWorkPlan = Forward("cs.workplan.Workplan")

_ureg = None


def get_unit_registry():
    import pint
    global _ureg
    if _ureg is None:
        _ureg = pint.UnitRegistry()
    return _ureg


class Task(Object):
    __classname__ = "cswp_task"
    __maps_to__ = "cswp_task"

    WPlan = Forward("cs.workplan.Workplan")
    TList = Forward("cs.workplan.tasklists.TaskList")
    TTask = Forward("cs.workplan.tasks.Task")

    RefererStartTaskTaskLists = Reference_N(
        TList,
        TList.workplan_id == TTask.workplan_id,
        TList.workplan_index == TTask.workplan_index,
        TList.reference_task_list == TTask.task_list_id,
        TList.start_task == TTask.task_id,
    )
    RefererReturnTaskTaskLists = Reference_N(
        TList,
        TList.workplan_id == TTask.workplan_id,
        TList.workplan_index == TTask.workplan_index,
        TList.reference_task_list == TTask.task_list_id,
        TList.return_task == TTask.task_id,
    )
    TaskList = Reference_1(
        TList,
        TList.workplan_id == TTask.workplan_id,
        TList.workplan_index == TTask.workplan_index,
        TList.task_list_id == TTask.task_list_id,
    )

    Workplan = Reference_1(
        WPlan,
        WPlan.workplan_id == TTask.workplan_id,
        WPlan.workplan_index == TTask.workplan_index,
    )

    ParentTask = Reference_1(
        TTask,
        TTask.workplan_id == TTask.workplan_id,
        TTask.workplan_index == TTask.workplan_index,
        TTask.task_list_id == TTask.task_list_id,
        TTask.task_id == TTask.parent_task_id,
    )

    def set_task_id(self, ctx):
        result = sqlapi.RecordSet2(
            sql="SELECT MAX(task_id) as task_id "
            "FROM cswp_task "
            "WHERE workplan_id='%s' and workplan_index='%s' and task_list_id='%s'"
            % (
                sqlapi.quote(self.workplan_id),
                sqlapi.quote(self.workplan_index),
                sqlapi.quote(self.task_list_id),
            )
        )
        if not result[0].task_id:
            task_id = 0
        else:
            task_id = int(result[0].task_id[2:])
            task_id += 1
        self.task_id = "OP%04d" % task_id

    def set_position(self, ctx):

        result = sqlapi.RecordSet2(
            sql="SELECT MAX(task_position) as pos "
            "FROM cswp_task "
            "WHERE workplan_id='%s' and workplan_index='%s' and task_list_id='%s' and "
            "parent_task_id='%s'"
            % (
                self.workplan_id,
                self.workplan_index,
                self.task_list_id,
                self.parent_task_id,
            )
        )
        if result[0].pos is None:
            position = 10
        else:
            position = result[0].pos
            position = position + (10 - (position % 10))

        self.task_position = position

    def set_default_plant(self, ctx):
        if self.Workplan.plant_id:
            self.plant_id = self.Workplan.plant_id

    def set_sap_operation_id(self, ctx):
        prefix = "OP"
        sap_id_length = 8
        r_set = sqlapi.RecordSet2(
            table=self.__maps_to__,
            condition="workplan_id='%s' AND workplan_index='%s'"
            % (self.workplan_id, self.workplan_index),
            columns=["MAX(sap_operation_id) AS operation_id"],
        )
        next_id = 0
        if r_set and r_set[0]["operation_id"]:
            next_id = int(r_set[0]["operation_id"][len(prefix):]) + 1
        self.sap_operation_id = prefix + str(next_id).zfill(sap_id_length - len(prefix))
        if self.ParentTask is not None:
            self.parent_sap_operation_id = self.ParentTask.sap_operation_id

    def check_deletion_permission(self, ctx):
        # check if there is any task list which refers to current task list
        sql_request = (
            "SELECT task_list_id from cswp_task_list "
            "WHERE (start_task='%s' OR return_task='%s') "
            "AND reference_task_list='%s' "
            "AND workplan_id ='%s' "
            "AND workplan_index ='%s'"
            % (
                self.task_id,
                self.task_id,
                self.task_list_id,
                self.workplan_id,
                self.workplan_index,
            )
        )
        result = sqlapi.RecordSet2(sql=sql_request)

        if any(result):
            task_list_ids = [r.task_list_id for r in result]
            raise ue.Exception(
                "cswp_task_prohibition_to_delete", ", ".join(task_list_ids)
            )

    def set_normalized_times(self, ctx):

        if self.machine_time:
            machine_time = get_unit_registry().Quantity(
                self.machine_time, self.time_unit_machine_time
            )
            self.normalized_machine_time = round(machine_time.to("minute").magnitude, 2)

        if self.setup_time:
            setup_time = get_unit_registry().Quantity(
                self.setup_time, self.time_unit_setup_time
            )
            self.normalized_setup_time = round(setup_time.to("minute").magnitude, 2)

    @classmethod
    def on_query_catalog_pre(cls, ctx):
        if ctx.catalog_name == "CDBTask_Catalog":
            if ctx.catalog_invoking_dialog.workplan_index == "":
                ctx.set("workplan_index", "=''")

    def validate_sap_compatibility(self, ctx):
        """
        SAP Compatibility checks
        """
        # only when SAP flag is set
        if isTrue(util.get_prop("wpsc")):
            if self.ParentTask:
                # no sub operations of sub operation
                if self.ParentTask.parent_task_id:
                    raise ue.Exception("cswp_sap_no_subtasks_of_subtasks")

    def set_hash(self, ctx):
        self.task_id = "#"

    event_map = {
        ("create", "pre_mask"): "set_hash",
        (("create", "copy"), "pre_mask"): (
            "set_position",
            "set_default_plant",
            "validate_sap_compatibility",
        ),
        (("create", "copy"), "pre"): ("set_task_id", "set_sap_operation_id"),
        ("delete", "pre"): "check_deletion_permission",
        (("create", "modify"), "pre"): "set_normalized_times",
    }


class TaskInputParts(Object):
    __classname__ = "cswp_task2input_parts"
    __maps_to__ = "cswp_task2input_parts"

    Workplan = Reference_1(
        fWorkPlan,
        fWorkPlan.workplan_id == fTaskInputParts.workplan_id,
        fWorkPlan.workplan_index == fTaskInputParts.workplan_index,
    )

    Task = Reference_1(
        Task,
        Task.task_id == fTaskInputParts.task_id,
        Task.workplan_id == fTaskInputParts.workplan_id,
        Task.workplan_index == fTaskInputParts.workplan_index,
        Task.task_list_id == fTaskInputParts.task_list_id,
    )

    def set_assembly(self, ctx):

        # if no assembly assigned to workplan
        if not self.Workplan.assembly_id:
            raise ue.Exception("cswp_no_assembly_assigned_to_wp")

        # get number of bom items
        if self._get_num_of_bom_items() == 0:
            raise ue.Exception("cswp_no_nom_items_for_current_assembly", self.Workplan.assembly_id)

        if self.Workplan.assembly_id:
            ctx.set("joined_assembly_id", self.Workplan.assembly_id)
            ctx.set("joined_assembly_index", self.Workplan.assembly_index)

    def _get_num_of_bom_items(self):
        """
        returns number of bom items of work plan assembly
        """
        result = sqlapi.RecordSet2(
            sql="SELECT COUNT(teilenummer) as bom_count FROM einzelteile "
                "WHERE baugruppe='%s' and b_index='%s'"
                % (
                    self.Workplan.assembly_id,
                    self.Workplan.assembly_index
                )
        )
        return result[0].bom_count

    def validate_sap_compatibility(self, ctx):
        """
        SAP Compatibility checks
        """
        # only when SAP flag is set
        if isTrue(util.get_prop("wpsc")):

            # bom items can only be assigned once per work plan
            bom_items = self.KeywordQuery(
                workplan_id=self.workplan_id,
                workplan_index=self.workplan_index,
                bom_item_object_id=self.bom_item_object_id
            )
            if bom_items:
                task_list = bom_items[0].Task.TaskList
                task = bom_items[0].Task
                raise ue.Exception(
                    "cswp_sap_bom_item_already_assigned",
                    task_list.task_list_name,
                    task_list.task_list_id,
                    str(task.task_position),
                    task.task_name,
                )

    def validate_sap_compatibility_sub_tasks(self, ctx):
        """
        SAP Compatibility checks
        """
        # only when SAP flag is set
        if isTrue(util.get_prop("wpsc")):
            # No bom items may be assigned to subtasks
            if self.Task.parent_task_id:
                raise ue.Exception("cswp_sap_no_bom_items_subtasks")

    event_map = {
        (("create", "copy", "modify"), "pre_mask"): (
            "set_assembly",
            "validate_sap_compatibility_sub_tasks",
        ),
        (("create", "copy", "modify"), "pre"): "validate_sap_compatibility",
    }


class TaskPrtParts(Object):
    __classname__ = "cswp_task2prt_parts"
    __maps_to__ = "cswp_task2prt_parts"

    Task = Reference_1(
        Task,
        Task.task_id == fTaskPrtParts.task_id,
        Task.workplan_id == fTaskPrtParts.workplan_id,
        Task.workplan_index == fTaskPrtParts.workplan_index,
        Task.task_list_id == fTaskPrtParts.task_list_id,
    )

    def validate_sap_compatibility(self, ctx):
        """
        SAP Compatibility checks
        """
        # only when SAP flag is set
        if isTrue(util.get_prop("wpsc")):
            # No production resources may be assigned to subtasks
            if self.Task.parent_task_id:
                raise ue.Exception("cswp_sap_no_prt_subtasks")

    event_map = {
        (("create", "copy", "modify"), "pre_mask"): "validate_sap_compatibility"
    }


class TaskOutputParts(Object):
    __classname__ = "cswp_task2output_parts"
    __maps_to__ = "cswp_task2output_parts"


class Tasks2Documents(Object):
    __classname__ = "cswp_tasks2documents"
    __maps_to__ = "cswp_tasks2documents"
