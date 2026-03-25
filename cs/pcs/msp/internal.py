#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging
from collections import OrderedDict, defaultdict

from cdb import sig, sqlapi, transactions, ue
from cdb.objects import Rule

from cs.pcs.projects import Project
from cs.pcs.projects.common import partition
from cs.pcs.projects.tasks import Task, TaskRelation

OBJECTS = defaultdict()
SUBTASKS = defaultdict(list)
TASKRELATION = defaultdict(list)
TASKRELATIONS_EXTERNAL = set()
FINALIZED = set()
MODIFIABLE = set()
DELETABLE = set()
CHECKS = defaultdict(set)

PRE_PROJECT = "pre_project"
PRE_TASK_CREATE = "pre_task_create"
PRE_TASK_MODIFY = "pre_task_modify"
PRE_TASK_DELETE = "pre_task_delete"


def joined(obj, diff_obj=None):
    result = OrderedDict(**obj)
    if diff_obj:
        for k, v in diff_obj.diffs.items():
            result[k] = v["new_value"]
    return result


def get_attr(obj, attr, default=None):
    if obj and attr in obj:
        return obj[attr]
    return default


class ProjectConsistency:
    def __init__(
        self, project, tasks, internal_relations, external_relations, **kwargs
    ):
        super().__init__(**kwargs)
        self.project = project
        self.tasks = tasks
        self.internal_relations = internal_relations
        self.external_relations = external_relations
        self.initData()
        self.init_consistency_checks()

    def refresh(self):
        prj_id = self.project.cdb_project_id
        ce_baseline_id = self.project.ce_baseline_id
        self.project = Project.ByKeys(
            cdb_project_id=prj_id, ce_baseline_id=ce_baseline_id
        )
        self.tasks = Task.KeywordQuery(
            cdb_project_id=prj_id, ce_baseline_id=ce_baseline_id
        ).Execute()
        self.internal_relations = TaskRelation.KeywordQuery(
            cdb_project_id=prj_id, cdb_project_id2=prj_id
        ).Execute()
        self.external_relations = TaskRelation.Query(
            "cdb_project_id='{pid}' AND cdb_project_id2!='{pid}' OR "
            "cdb_project_id!='{pid}' AND cdb_project_id2='{pid}'".format(pid=prj_id)
        )
        self.initData()

    def initData(self):
        OBJECTS.clear()
        SUBTASKS.clear()
        TASKRELATION.clear()
        TASKRELATIONS_EXTERNAL.clear()

        self.addItem(self.project)
        for task in self.tasks:
            self.addItem(task)
            self.addSubItem(task)

        for tr in self.internal_relations:
            TASKRELATION[tr.task_id].append(tr)
            TASKRELATION[tr.task_id2].append(tr)

        for tr in self.external_relations:
            if tr.cdb_project_id != tr.cdb_project_id2:
                TASKRELATIONS_EXTERNAL.add(tr)

        self.initFinalized(
            prj_id=self.project.cdb_project_id,
            ce_baseline_id=self.project.ce_baseline_id,
        )
        self.initModifiable(
            prj_id=self.project.cdb_project_id,
            ce_baseline_id=self.project.ce_baseline_id,
        )
        self.initDeletable(
            prj_id=self.project.cdb_project_id,
            ce_baseline_id=self.project.ce_baseline_id,
        )

    def init_consistency_checks(self):
        CHECKS.clear()
        self.addCheck(PRE_PROJECT, "checkStructureLock")
        self.addCheck(PRE_PROJECT, "checkScheduleLock")
        self.addCheck(PRE_PROJECT, "checkProjectStatus")

        self.addCheck(PRE_TASK_CREATE, "checkDatesJointlyFilled")
        self.addCheck(PRE_TASK_CREATE, "checkMilestoneDuration")
        self.addCheck(PRE_TASK_CREATE, "checkMilestoneEfforts")
        self.addCheck(PRE_TASK_CREATE, "checkParentMilestone")
        self.addCheck(PRE_TASK_CREATE, "checkParentFinalized")
        self.addCheck(PRE_TASK_CREATE, "check_parent_task_status")
        self.addCheck(PRE_TASK_CREATE, "check_project_status")

        self.addCheck(PRE_TASK_MODIFY, "checkDatesJointlyFilled")
        self.addCheck(PRE_TASK_MODIFY, "checkMilestoneDuration")
        self.addCheck(PRE_TASK_MODIFY, "checkMilestoneEfforts")
        self.addCheck(PRE_TASK_MODIFY, "checkTaskModifiable")
        self.addCheck(PRE_TASK_MODIFY, "checkParentMilestone")
        self.addCheck(PRE_TASK_MODIFY, "checkParentReassign")
        self.addCheck(PRE_TASK_MODIFY, "checkParentFinalized")

        self.addCheck(PRE_TASK_DELETE, "checkEffortsFound")
        self.addCheck(PRE_TASK_DELETE, "checkParentFinalized")
        self.addCheck(PRE_TASK_DELETE, "checkTaskDeletable")
        self.addCheck(PRE_TASK_DELETE, "checkTaskDeepDelete")
        sig.emit(ProjectConsistency, "init_consistency_checks")(self)

    @classmethod
    def _get_tasks_by_access(cls, access, prj_id, ce_baseline_id):
        return sqlapi.RecordSet2(
            "cdbpcs_task",
            access=access,
            condition=(
                f"cdb_project_id = '{prj_id}'"
                f" AND ce_baseline_id = '{ce_baseline_id}'"
            ),
        )

    @classmethod
    def initModifiable(cls, prj_id, ce_baseline_id):
        MODIFIABLE.clear()
        for task in cls._get_tasks_by_access("save", prj_id, ce_baseline_id):
            MODIFIABLE.add(task["task_id"])

    @classmethod
    def initDeletable(cls, prj_id, ce_baseline_id):
        DELETABLE.clear()
        for task in cls._get_tasks_by_access("delete", prj_id, ce_baseline_id):
            DELETABLE.add(task["task_id"])

    @classmethod
    def initFinalized(cls, prj_id, ce_baseline_id):
        FINALIZED.clear()
        rule = Rule.ByKeys(name="cdbpcs: Finalized Task")
        for task in rule.getObjects(
            cls=Task,
            add_expr=(
                f"cdb_project_id = '{prj_id}' AND ce_baseline_id = '{ce_baseline_id}'"
            ),
        ):
            FINALIZED.add(task)

    @classmethod
    def addCheck(cls, action, check_name):
        CHECKS[action].add(check_name)

    @classmethod
    def isFinalized(cls, obj):
        return obj in FINALIZED

    @classmethod
    def isModifiable(cls, obj):
        return obj in MODIFIABLE

    @classmethod
    def isDeletable(cls, obj):
        return obj in DELETABLE

    @classmethod
    def getID(cls, obj):
        oid = get_attr(obj, "task_id")
        if not oid:
            oid = get_attr(obj, "cdb_project_id")
        return oid

    @classmethod
    def getParentID(cls, obj):
        return get_attr(obj, "parent_task", "")

    @classmethod
    def addItem(cls, obj):
        OBJECTS[cls.getID(obj)] = obj

    @classmethod
    def getItem(cls, oid):
        return OBJECTS.get(oid)

    @classmethod
    def getParentItem(cls, obj):
        return OBJECTS.get(cls.getParentID(obj))

    @classmethod
    def addSubItem(cls, obj):
        SUBTASKS[cls.getParentID(obj)].append(obj)

    @classmethod
    def getSubItems(cls, obj):
        return SUBTASKS.get(cls.getID(obj))

    @classmethod
    def getAllParents(cls, obj):
        parent = cls.getParentItem(obj)
        return [parent] + cls.getAllParents(parent)

    # PRE CHECKS

    @classmethod
    def pre_project(cls, result):
        obj = result.project.pcs_object
        for check in CHECKS.get(PRE_PROJECT):
            getattr(cls, check)(obj)

    @classmethod
    def pre_tasks(cls, result):
        cls_name = "cdbpcs_task"

        for diff_obj in result.tasks.added:
            obj = diff_obj.pcs_object
            # setInitValues

            for check in CHECKS.get(PRE_TASK_CREATE):
                try:
                    getattr(cls, check)(obj)
                except Exception as ex:
                    logging.exception("pre_tasks/added/%s/%s", obj["task_name"], check)
                    result.add_exception(obj, cls_name, ex)

        for diff_obj in result.tasks.modified:
            old_obj = diff_obj.pcs_object
            obj = joined(old_obj, diff_obj)

            for check in CHECKS.get(PRE_TASK_MODIFY):
                try:
                    getattr(cls, check)(obj)
                except Exception as ex:
                    logging.exception(
                        "pre_tasks/modified/%s/%s", obj["task_name"], check
                    )
                    result.add_exception(obj, cls_name, ex)

        for diff_obj in result.tasks.deleted:
            old_obj = diff_obj.pcs_object
            obj = joined(old_obj, diff_obj)

            for check in CHECKS.get(PRE_TASK_DELETE):
                try:
                    getattr(cls, check)(obj)
                except Exception as ex:
                    logging.exception(
                        "pre_tasks/deleted/%s/%s", obj["task_name"], check
                    )
                    result.add_exception(obj, cls_name, ex)

    # POST ADJUSTMENTS

    @classmethod
    def post_tasks(cls, result, split_count):
        prj = result.project.pcs_object
        with transactions.Transaction():
            added = []
            for diff_obj in result.tasks.modified:
                added.append(diff_obj.pcs_object)
            modified = []
            for diff_obj in result.tasks.modified:
                old_obj = diff_obj.pcs_object
                modified.append(joined(old_obj, diff_obj))
            deleted = []
            for diff_obj in result.tasks.deleted:
                old_obj = diff_obj.pcs_object
                obj = joined(old_obj, diff_obj)
                if obj:
                    deleted.append(obj)

            prj.tasks_added(added)
            prj.tasks_modified(modified)
            prj.tasks_deleted(deleted)
            for tasks in partition(added + modified + deleted, split_count):
                prj.tasks_all(tasks, split_count)

    @classmethod
    def post_project(cls, result, split_count):
        prj = result.project.pcs_object
        with transactions.Transaction():
            prj.project_modified(result.project.diffs, result.tasks.all, split_count)

    # PROJECT

    @classmethod
    def checkStructureLock(cls, obj):
        if not obj.msp_active:
            raise ue.Exception("cdbpcs_msp_structure_lock")

    @classmethod
    def checkScheduleLock(cls, obj):
        obj.checkScheduleLock()

    @classmethod
    def checkProjectStatus(cls, obj):
        obj.isFinalized()

    # TASK

    @classmethod
    def checkDatesJointlyFilled(cls, obj):
        # start/end must be filled jointly
        sd = obj["start_time_fcast"]
        ed = obj["end_time_fcast"]
        if (sd and not ed) or (not sd and ed):
            raise ue.Exception("pcs_capa_err_025")

    @classmethod
    def checkEffortsFound(cls, obj):
        if obj and obj["effort_act"]:
            raise ue.Exception("pcs_err_effort8", obj["task_name"])

    @classmethod
    def checkMilestoneDuration(cls, obj):
        if bool(obj["milestone"]) and bool(obj["days_fcast"]):
            raise ue.Exception("cdbpcs_err_milestone_duration")

    @classmethod
    def checkMilestoneEfforts(cls, obj):
        if not obj["milestone"]:
            return
        if (
            obj["effort_fcast"]
            or obj["effort_plan"]
            or obj["effort_act"]
            or obj["effort_fcast_d"]
            or obj["effort_fcast_a"]
        ):
            raise ue.Exception("pcs_err_effort4", obj["task_name"])

    @classmethod
    def checkParentMilestone(cls, obj):
        parent = cls.getParentItem(obj)
        if parent and parent["milestone"]:
            raise ue.Exception("cdbpcs_err_task_milestone")

    @classmethod
    def checkParentReassign(cls, obj):
        old_obj = cls.getItem(cls.getID(obj))
        new_parent = cls.getParentItem(obj)
        old_parent = cls.getParentItem(old_obj)
        if cls.getID(old_parent) != cls.getID(new_parent):
            if old_obj and old_obj["status"] != Task.NEW.status:
                raise ue.Exception("pcs_err_task_move")

    @classmethod
    def checkParentFinalized(cls, obj):
        old_obj = cls.getItem(cls.getID(obj))
        new_parent = cls.getParentItem(obj)
        old_parent = cls.getParentItem(old_obj)
        if new_parent != old_parent:
            if cls.isFinalized(old_parent):
                raise ue.Exception("pcs_err_new_task2", old_parent["task_name"])
            if cls.isFinalized(new_parent):
                raise ue.Exception("pcs_err_new_task2", new_parent["task_name"])

    @classmethod
    def check_parent_task_status(cls, obj):
        cls._check_status(
            obj, cls.getParentItem(obj), "cdbpcs_parenttask_completion_invalid"
        )

    @classmethod
    def check_project_status(cls, obj):
        cls._check_status(
            obj, cls.getItem(obj["cdb_project_id"]), "cdbpcs_project_completion_invalid"
        )

    @classmethod
    def _check_status(cls, obj, parent, error_msg):
        if not parent:
            return
        valid = defaultdict(list)
        valid.update(
            {
                # <parent status>: [<task status>]
                0: [0, 180],
                20: [0, 20, 180],
                50: [0, 20, 50, 180, 200],
                60: [0, 20, 50, 180, 200],
                180: [180, 200],
            }
        )
        if obj["status"] not in valid[parent["status"]]:
            raise ue.Exception(error_msg)

    @classmethod
    def checkTaskModifiable(cls, obj):
        old_obj = cls.getItem(cls.getID(obj))
        if old_obj and not cls.isModifiable(cls.getID(obj)):
            raise ue.Exception("pcs_err_mod_task")

    @classmethod
    def checkTaskDeletable(cls, obj):
        old_obj = cls.getItem(cls.getID(obj))
        if old_obj and not cls.isDeletable(cls.getID(obj)):
            raise ue.Exception("pcs_err_del_task0")

    @classmethod
    def checkTaskDeepDelete(cls, obj):
        old_obj = cls.getItem(cls.getID(obj))
        if old_obj:
            dependancies = old_obj.check_deepdelete(reason=True)
            if dependancies:
                message = "\n".join(dependancies)
                raise ue.Exception("cdbpcs_delete_deny", message)
