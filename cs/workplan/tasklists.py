#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb.objects import Object, Reference_1, Reference_N, Forward
from cdb import ue, util, sqlapi
from cdb import transactions
from cdb.objects.operations import operation
from cdbwrapc import I18nCatalogEntry
from cdb.platform.gui import CDBCatalog
from cs.workplan.tasks import Task


class TaskList(Object):
    __classname__ = "cswp_task_list"
    __maps_to__ = "cswp_task_list"

    WPlan = Forward("cs.workplan.Workplan")
    TList = Forward("cs.workplan.tasklists.TaskList")

    Workplan = Reference_1(
        WPlan,
        WPlan.workplan_id == TList.workplan_id,
        WPlan.workplan_index == TList.workplan_index,
    )

    Tasks = Reference_N(
        Task,
        Task.workplan_id == TList.workplan_id,
        Task.workplan_index == TList.workplan_index,
        Task.task_list_id == TList.task_list_id,
    )

    MainTasks = Reference_N(
        Task,
        Task.workplan_id == TList.workplan_id,
        Task.workplan_index == TList.workplan_index,
        Task.task_list_id == TList.task_list_id,
        Task.parent_task_id == "",
    )

    ReferenceTaskList = Reference_1(
        TList,
        TList.workplan_id == TList.workplan_id,
        TList.workplan_index == TList.workplan_index,
        TList.task_list_id == TList.reference_task_list,
    )

    RefererTaskLists = Reference_N(
        TList,
        TList.workplan_id == TList.workplan_id,
        TList.workplan_index == TList.workplan_index,
        TList.reference_task_list == TList.task_list_id,
    )

    StartTask = Reference_1(
        Task,
        Task.workplan_id == TList.workplan_id,
        Task.workplan_index == TList.workplan_index,
        Task.task_list_id == TList.reference_task_list,
        Task.task_id == TList.start_task,
    )

    ReturnTask = Reference_1(
        Task,
        Task.workplan_id == TList.workplan_id,
        Task.workplan_index == TList.workplan_index,
        Task.task_list_id == TList.reference_task_list,
        Task.task_id == TList.return_task,
    )

    def get_next_task_list_id(self):
        result = sqlapi.RecordSet2(
            sql="SELECT MAX(task_list_id) as task_list_id "
            "FROM cswp_task_list "
            "WHERE workplan_id='%s' and workplan_index='%s' "
            % (sqlapi.quote(self.workplan_id), sqlapi.quote(self.workplan_index))
        )
        if not result[0].task_list_id:
            highest_task_list_id = 0
        else:
            highest_task_list_id = int(result[0].task_list_id[2:])
            highest_task_list_id += 1
        return highest_task_list_id

    def set_task_list_id(self, ctx):
        task_list_id = self.get_next_task_list_id()
        self.task_list_id = "SQ%04d" % task_list_id

    def set_root_task_list(self, ctx):
        if not self.reference_task_list:
            self.reference_task_list = self.Workplan.RootTaskList.task_list_id

    def check_lot_range(self, ctx):
        # lot size from has to be smaller than lot size to (if they are set)
        if self.lot_size_from:
            if self.lot_size_from >= self.lot_size_to:
                raise ue.Exception("cswp_workplan_lot_size_range")

    def check_task_list_rules(self, ctx):
        reference_task_list = self.ReferenceTaskList
        if self.task_list_type == "alternative":
            if reference_task_list.task_list_type != "standard":
                raise ue.Exception("cswp_task_list_alternative_only_refer_to_standard")

        elif self.task_list_type == "parallel":
            depth = 0
            self._check_depth(reference_task_list, depth)

    def check_start_and_return_tasks(self, ctx):
        if self.task_list_type != "standard":
            if self.ReturnTask.task_position < self.StartTask.task_position:
                raise ue.Exception(
                    "cswp_task_return_position_greater_than_start_position"
                )

    # checks recursively depth of sequence structure
    def _check_depth(self, task_list, depth):
        if depth == 2:
            raise ue.Exception("cswp_task_list_max_depth_reached")
        if task_list.task_list_type == "standard":
            return
        depth += 1
        ref_task_list = TaskList.ByKeys(
            workplan_id=self.workplan_id,
            workplan_index=self.workplan_index,
            task_list_id=task_list.reference_task_list,
        )
        self._check_depth(ref_task_list, depth)

    def set_readonly_behavior(self, ctx):
        ctx.set_fields_readonly(["task_list_type"])
        fields = [
            "task_list_type",
            "reference_task_list",
            "start_task",
            "return_task",
            "lot_size_from",
            "lot_size_to",
        ]
        if self.task_list_type == "standard":
            ctx.set_fields_readonly(fields)
            ctx.set_optional(fields)

        # set reference sequence read only for alternative sequences
        if self.task_list_type == "alternative":
            ctx.set_fields_readonly(["reference_task_list"])

    def clear_task_type(self, ctx):
        if self.task_list_type == "standard":
            self.task_list_type = ""

    def check_deletion_permission(self, ctx):
        if self.task_list_type == "standard":
            raise ue.Exception(
                "cswp_task_list_deletion_of_standard_sequence_not_allowed"
            )

        # check if there is any task list which refers to current task list
        result = TaskList.KeywordQuery(
            workplan_id=self.workplan_id,
            workplan_index=self.workplan_index,
            reference_task_list=self.task_list_id,
        )

        if result:
            raise ue.Exception(
                "cswp_task_list_prohibition_to_delete", ", ".join(result.task_list_id)
            )

    @classmethod
    def on_query_catalog_pre(cls, ctx):
        if ctx.catalog_name == "CDBTask_List_Catalog":
            if ctx.catalog_invoking_dialog.workplan_index == "":
                ctx.set("workplan_index", "=''")
        if ctx.catalog_name == "CDBTask_List_Import_Catalog":
            if ctx.catalog_invoking_dialog.source_workplan_index == "":
                ctx.set("workplan_index", "=''")

    def get_highest_task_id(self):
        # Finding out what the max task_id is to append the new task_ids after that
        max_id_task = sqlapi.RecordSet2(
            sql="SELECT MAX(task_id) as task_id "
            "FROM cswp_task "
            "WHERE workplan_id='%s' AND workplan_index='%s' AND task_list_id='%s'"
            % (self.workplan_id, self.workplan_index, self.task_list_id)
        )
        if not max_id_task[0].task_id:
            highest_task_id = 0
        else:
            highest_task_id = int(max_id_task[0].task_id[2:])
        return highest_task_id

    def get_highest_position(self):
        max_pos_task = sqlapi.RecordSet2(
            sql="SELECT MAX(task_position) as pos "
            "FROM cswp_task "
            "WHERE workplan_id='%s' AND workplan_index='%s' "
            "AND task_list_id='%s' AND parent_task_id=''"
            % (self.workplan_id, self.workplan_index, self.task_list_id)
        )
        if not max_pos_task[0].pos:
            max_position = 0
        else:
            max_position = max_pos_task[0].pos

        return max_position

    def import_tasks(self, task_list_to_import):
        # Track to which the imported tasks will get mapped to
        task_id_map = {}

        position_shift = self.get_highest_position()
        for original_task in task_list_to_import.MainTasks:
            args = {}
            args["cdb_object_id"] = None
            args["task_list_id"] = self.task_list_id
            args["workplan_id"] = self.workplan_id
            args["workplan_index"] = self.workplan_index
            args["task_position"] = original_task.task_position + position_shift

            new_task = operation("CDB_Copy", original_task, **args)
            task_id_map[original_task.task_id] = new_task.task_id
        return task_id_map

    def import_task_list(self, ctx):
        import_task_list = TaskList.ByKeys(workplan_id=ctx.dialog.source_workplan_id,
                                           workplan_index=ctx.dialog.source_workplan_index,
                                           task_list_id=ctx.dialog.import_task_list)
        with transactions.Transaction():
            self.import_tasks(import_task_list)

    def import_task_list_pre_mask(self, ctx):
        if not self.Workplan.CheckAccess("save"):
            raise ue.Exception("cswp_workplan_not_modifiable")

    def set_reference_sequence_changeable(self, ctx):
        ctx.set_fields_writeable(
            ["reference_task_list", "lot_size_to", "lot_size_from"]
        )
        # set reference sequence read only for alternative sequences
        if self.task_list_type == "alternative":
            ctx.set_fields_readonly(["reference_task_list"])
            self.reference_task_list = self.Workplan.RootTaskList.task_list_id
        if self.task_list_type == "parallel":
            self.lot_size_from = ""
            self.lot_size_to = ""
            ctx.set_fields_readonly(["lot_size_to", "lot_size_from"])

    def task_list_type_color(self):
        """Returns the color of the task_list
        used throughout the module GUI
        pending on the type (parallel,alternative,standard)
        """
        if self.task_list_type == "alternative":
            return "#727272"
        elif self.task_list_type == "parallel":
            return "#ADC902"
        else:
            return "#0080C5"

    def task_list_type_color_light(self):
        """Returns the color of the task_list
        used throughout the module GUI
        pending on the type (parallel,alternative,standard)
        """
        if self.task_list_type == "alternative":
            return "#F7F7F7"
        elif self.task_list_type == "parallel":
            return "#F6F9E4"
        else:
            return "#E4F1F8"

    def task_list_type_name(self):
        """Returns the type name
        (depending on language setting)
         of the task_list
        """
        if self.task_list_type == "alternative":
            return util.get_label("cswp_task_list_type_alternative")
        elif self.task_list_type == "parallel":
            return util.get_label("cswp_task_list_type_parallel")
        else:
            return util.get_label("cswp_task_list_type_standard")

    def set_hash(self, ctx):
        self.task_list_id = "#"

    event_map = {
        ("create", "pre_mask"): ("set_hash", "set_root_task_list"),
        ("modify", "pre_mask"): "set_readonly_behavior",
        ("copy", "pre_mask"): ("set_root_task_list", "clear_task_type"),
        (("create", "copy"), "pre"): "set_task_list_id",
        (("create", "modify", "copy"), "pre"): (
            "check_lot_range",
            "check_task_list_rules",
            "check_start_and_return_tasks",
        ),
        ("create", "dialogitem_change"): "set_reference_sequence_changeable",
        ("delete", "pre"): "check_deletion_permission",
        ("cswp_import_task_list", "now"): "import_task_list",
        ("cswp_import_task_list", "pre_mask"): "import_task_list_pre_mask",
    }


class TaskListTypeCatalog(CDBCatalog):
    """
    Implements a CDB Catalog/Browser that returns
    the list which appear in the 'Task List / Sequence' Combobox
    """

    def __init__(self):
        CDBCatalog.__init__(self)

    def handlesI18nEnumCatalog(self):
        return True

    def getI18nEnumCatalogEntries(self):
        task_list_types = [
            ("alternative", "cswp_task_list_type_alternative"),
            ("parallel", "cswp_task_list_type_parallel"),
        ]
        # only the task list types 'alternative' and 'parallel' should be selectable,
        # when creating new task list
        operation = self.getInvokingOpName()
        if operation != "CDB_Create" and operation != "CDB_Copy":
            task_list_types.insert(0, ("standard", "cswp_task_list_type_standard"))

        result = []
        for key, label in task_list_types:
            result.append(I18nCatalogEntry(key, util.get_label(label)))

        return result


class TaskLists2Documents(Object):
    __classname__ = "cswp_task_lists2documents"
    __maps_to__ = "cswp_task_lists2documents"
