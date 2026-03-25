#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


import logging

from cdb import sig, sqlapi, ue
from cdb.classbody import classbody
from cdb.objects import Forward

from cs.pcs.projects import Project
from cs.pcs.projects import calendar as Calendar
from cs.pcs.projects import tasks_efforts
from cs.pcs.projects.common import partition
from cs.pcs.projects.tasks import Task

ProjectConsistency = Forward("cs.pcs.msp.internal.ProjectConsistency")


def apply_changes(cls, **kwargs):
    changes = kwargs.get("changes", [])
    if not changes:
        raise ue.Exception("just_a_replacement", "There are no changes to apply.")

    conditions = kwargs.pop("conditions", ["1=1"])
    add_keys_to_conditions(cls, conditions=conditions, **kwargs)

    upd = f"{cls.GetTableName()} SET {', '.join(changes)} WHERE {' AND '.join(conditions)}"
    return sqlapi.SQLupdate(upd.format(**kwargs))


def add_keys_to_conditions(cls, conditions, **kwargs):
    for key in cls.KeyNames():
        add_condition(key, kwargs.get(key, None), conditions)


def add_condition(key, values, conditions):
    if values:
        if not isinstance(values, list):
            values = [values]
        if isinstance(values[0], (str, str)):
            values = [f"'{sqlapi.quote(x)}'" for x in values]
        values = ", ".join(values)
        conditions.append(f"{key} IN ({values})")


@classbody
class Task:
    @classmethod
    def apply_changes(cls, **kwargs):
        return apply_changes(cls, **kwargs)


@classbody
class Project:
    @classmethod
    def apply_changes(cls, **kwargs):
        if "task_id" in kwargs:
            Task.apply_changes(**kwargs)
        return apply_changes(cls, **kwargs)

    def removeTemplateOID(self, tasks):
        changes = ["template_oid = ''"]
        conditions = []
        add_condition("template_oid", [t["cdb_object_id"] for t in tasks], conditions)
        Task.apply_changes(changes=changes, conditions=conditions)

    def updateTaskStatus(self, tasks):
        oids = [t["parent_task"] for t in tasks]
        objs = Task.KeywordQuery(
            cdb_project_id=self.cdb_project_id,
            task_id=oids,
            ce_baseline_id=self.ce_baseline_id,
        )
        for task in objs:
            # finish parent task if this was the last active subtask
            target_status = task.getFinalStatus()
            if target_status:
                try:
                    task.ChangeState(target_status, check_access=False)
                except Exception:
                    logging.exception(
                        """
                        task.ChangeState(%s, check_access=0)
                        failed for task with
                        cdb_project_id: '%s', task_id: '%s', ce_baseline_id: '%s'
                        """,
                        status=target_status,
                        pid=getattr(task, "cdb_project_id", "?"),
                        tid=getattr(task, "task_id", "?"),
                        bid=getattr(task, "ce_baseline_id", "?"),
                    )

    def tasks_added(self, tasks):
        pass

    def tasks_modified(self, tasks):
        pass

    def tasks_deleted(self, tasks):
        if len(tasks):
            self.removeTemplateOID(tasks)
            self.updateTaskStatus(tasks)

    def tasks_all(self, tasks, split_count):
        pass

    def project_modified(self, diffs=None, tasks=None, split_count=10, **kwargs):
        if not tasks:
            tasks = []
        task_ids = [t["task_id"] for t in tasks]

        # within MSP start/end time forecast has to be the same as planned value
        changes = {}
        if self.auto_update_time:
            changes.update(auto_update_time=0)
        if task_ids:
            changes.update(is_group=1)
        if changes:
            self.Update(**changes)

        self._save_project_dates(diffs)

        tasks_efforts.aggregate_changes(self)
        Calendar.adjustProjectWorkdays(self.cdb_project_id)

        self.updateNetworkValues()
        self.check_project_role_needed()
        self.initTaskRelationOIDs()

        for task_id in partition(task_ids, split_count):
            sig.emit(Project, "adjustAllocationsOnly")(self, task_id)
            sig.emit(Project, "do_consistency_checks")(self, task_id)

    def _save_project_dates(self, diffs):
        changes = {}
        if "start_time_fcast" in diffs:
            old_sd = diffs["start_time_fcast"]["old_value"]
            new_sd = diffs["start_time_fcast"]["new_value"]
            if new_sd != old_sd:
                changes.update(start_time_fcast=new_sd)
        if "end_time_fcast" in diffs:
            old_ed = diffs["end_time_fcast"]["old_value"]
            new_ed = diffs["end_time_fcast"]["new_value"]
            if new_ed != old_ed:
                changes.update(end_time_fcast=new_ed)
        if changes:
            cca = Project.MakeChangeControlAttributes()
            changes.update(cdb_mdate=cca["cdb_mdate"], cdb_mpersno=cca["cdb_mpersno"])
            self.Update(**changes)

    def updateNetworkValues(self):
        """
        persist schedule to database
        triggers multiple update statements which depend on the previous ones:

        1. task float (german "Puffer")
        2. task relationship violations
        """
        kwargs = {"cdb_project_id": self.cdb_project_id}

        updates = [
            """cdbpcs_taskrel SET violation = 0
                WHERE cdb_project_id = '{cdb_project_id}'
                    OR cdb_project_id2 = '{cdb_project_id}'""",
        ]
        for upd in updates:
            if upd:
                sqlapi.SQLupdate(upd.format(**kwargs))
