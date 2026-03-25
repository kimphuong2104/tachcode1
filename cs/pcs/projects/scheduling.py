#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable-msg=E0213,E1103,E0102,E0203,W0212,W0621,W0201

import logging

from cdb import sig, sqlapi, util
from cdb.classbody import classbody
from cdb.typeconversion import to_python_rep

from cs.pcs.projects import Project, tasks_efforts
from cs.pcs.projects.tasks import Task, TaskRelation
from cs.pcs.scheduling import schedule
from cs.pcs.scheduling.constants import (
    ASAP,
    VALID_CONSTRAINTS_FOR_TASK_GROUPS,
    VALID_CONSTRAINTS_WITHOUT_DATES,
)

CALCULATION_ATTRIBUTES = [
    "start_time_fcast",
    "end_time_fcast",
    "days_fcast",
    "calendar_profile_id",
    "automatic",
    "auto_update_time",
    "constraint_type",
    "constraint_date",
    "milestone",
    "start_is_early",
    "end_is_early",
    "parent_task",
    "daytime",
    "auto_update_effort",
]

AGGREGATE_ATTRIBUTES = [
    "start_time_plan",
    "end_time_plan",
    "start_time_act",
    "end_time_act",
    "effort_plan",
    "effort_fcast",
    "effort_act",
    "effort_fcast_d",
    "effort_fcast_a",
    "percent_complet",
    "days",
]


def check_if_attr_changed(attributes, obj, ctx):
    for attr in [
        attr for attr in attributes if hasattr(obj, attr) and hasattr(ctx.object, attr)
    ]:
        field_type = obj.__table_info__.column(attr).type()
        value_ctx = to_python_rep(field_type, ctx.object[attr])
        if value_ctx and field_type == sqlapi.SQL_DATE:
            value_ctx = value_ctx.date()

        if obj[attr] != value_ctx:
            return True
    return False


def is_calc_attr_set_in_args(attr, ctx):
    return attr in ctx.ue_args.get_attribute_names() and int(ctx.ue_args[attr])


def recalculate_preparation(self, ctx=None):
    if check_if_attr_changed(CALCULATION_ATTRIBUTES, self, ctx):
        ctx.keep("do_recalculation", 1)
    if check_if_attr_changed(AGGREGATE_ATTRIBUTES, self, ctx):
        ctx.keep("do_aggregation", 1)


def is_recalculate_necessary(self, ctx, actions):
    no_context = not ctx
    relevant_action = ctx and ctx.action in actions
    do_recalculation_set = ctx and is_calc_attr_set_in_args("do_recalculation", ctx)
    return no_context or relevant_action or do_recalculation_set


def is_aggregation_necessary(ctx):
    return ctx and is_calc_attr_set_in_args("do_aggregation", ctx)


@classbody
class Project:
    def recalculate_preparation(self, ctx=None):
        recalculate_preparation(self, ctx)

    def is_recalculate_necessary(self, ctx):
        if self.msp_active:
            return False
        return is_recalculate_necessary(self, ctx, {"create", "copy", "delete"})

    def is_aggregation_necessary(self, ctx):
        return is_aggregation_necessary(ctx)

    def aggregate(self):
        try:
            tasks_efforts.aggregate_changes(self)
        except Exception as exc:
            logging.exception("Project.aggregate: '%s'", self.cdb_project_id)
            raise util.ErrorMessage("cdbpcs_aggregation_failed") from exc

    def _adjust_cross_project_taskrels(self):
        # Adjust all Task Relships from this Project to other Projects
        # by determining values for gap and violation
        relations = TaskRelation.Query(
            """(cdb_project_id='{pid}' and cdb_project_id2!='{pid}')
                OR (cdb_project_id!='{pid}' and (cdb_project_id2='{pid}'))
            """.format(
                pid=self.cdb_project_id
            )
        )
        if not relations:
            return

        from cs.pcs.scheduling.relships import calculate_relship_gap

        changes = []
        for relation in relations:
            gap = calculate_relship_gap(
                relation.SuccessorProject.calendar_profile_id,
                relation.PredecessorTask,
                relation.SuccessorTask,
                relation.rel_type,
            )
            violation = int((relation.minimal_gap or 0) > gap)

            if violation != relation.violation:
                changes.append(
                    {
                        "pid1": relation.cdb_project_id,
                        "pid2": relation.cdb_project_id2,
                        "tid1": relation.task_id,
                        "tid2": relation.task_id2,
                        "violation": violation,
                    }
                )

        if not changes:
            return

        if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
            # SQL Statement Parts for MSSQL
            __update_stmt_template__ = """
                UPDATE cdbpcs_taskrel SET
                    violation = updated.violation
                FROM cdbpcs_taskrel
                JOIN (
                    {values}
                ) updated
                    ON cdbpcs_taskrel.cdb_project_id = updated.cdb_project_id
                        AND cdbpcs_taskrel.task_id = updated.task_id
                        AND cdbpcs_taskrel.cdb_project_id2 = updated.cdb_project_id2
                        AND cdbpcS_taskrel.task_id2 = updated.task_id2
                WHERE {where}
                """
            __value_stmt_template__ = """
                SELECT
                    '{pid1}' AS cdb_project_id,
                    '{tid1}' AS task_id,
                    '{pid2}' AS cdb_project_id2,
                    '{tid2}' AS task_id2
                    '{violation}' AS violation
            """
            value_stmt_parts = [
                __value_stmt_template__.format(
                    pid1=c["pid1"],
                    pid2=c["pid2"],
                    tid1=c["tid1"],
                    tid2=c["tid2"],
                    violation=c["violation"],
                )
                for c in changes
            ]
            __value_join_fragment__ = " UNION ALL "
            value_stmt = __value_join_fragment__.join(value_stmt_parts)
        else:
            # SQL Statement Parts for other DBMS
            __update_stmt_template__ = """
                cdbpcs_taskrel
                SET {value}
                WHERE {where}
                """
            __case_stmt_template__ = """
                WHEN cdb_project_id='{pid1}'
                    AND cdb_project_id2='{pid2}'
                    AND task_id='{tid1}'
                    AND task_id2='{tid2}'
                THEN {val}
            """
            violation_cases = " ".join(
                [
                    __case_stmt_template__.format(
                        pid1=c["pid1"],
                        pid2=c["pid2"],
                        tid1=c["tid1"],
                        tid2=c["tid2"],
                        val=c["violation"],
                    )
                    for c in changes
                ]
            )
            value_stmt = f"""
                violation = CASE
                    {violation_cases}
                END
            """

        __where_stmt_template__ = """
            (cdb_project_id='{pid1}'
            AND cdb_project_id2='{pid2}'
            AND task_id='{tid1}'
            AND task_id2='{tid2}')
            """
        where_stmt_parts = [
            __where_stmt_template__.format(
                pid1=c["pid1"], pid2=c["pid2"], tid1=c["tid1"], tid2=c["tid2"]
            )
            for c in changes
        ]
        update_stmt = __update_stmt_template__.format(
            value=value_stmt, where=" OR ".join(where_stmt_parts)
        )

        sqlapi.SQLupdate(update_stmt)

    def recalculate(self, ctx=None, skip_followups=False):
        if ctx and getattr(ctx.sys_args, "batch_mode", False):
            return

        # TODO: Refactor check for existence in db
        if not Project.ByKeys(cdb_project_id=self.cdb_project_id, ce_baseline_id=""):
            return

        if self.is_recalculate_necessary(ctx):
            self.recalculate_now(skip_followups=skip_followups)
        elif self.is_aggregation_necessary(ctx):
            self.aggregate()

    def recalculate_now(self, skip_scheduling=False, skip_followups=False):
        """
        Force recalculating a single project and its tasks:

        1. Schedule (calculate new target dates)
        2. Aggregate (sum up efforts and forecast dates "bottom-up")

        The project and its tasks will be updated in the database directly.
        There is no return value.

        :param project_id: ID of the project to recalculate
        :type project_id: str

        :param skip_scheduling: If ``True``, the scheduling step is skipped.
            Defaults to ``False``.
        :type skip_scheduling: bool

        :param skip_followups: If ``True``, signals for followup actions are not emitted.
            These may be handled by ``cs.resources``, for example.
            Defaults to ``False``.
        :type skip_followups: bool
        """
        if not skip_scheduling:
            try:
                task_ids, task_ids_res_changes, _, __ = schedule(self.cdb_project_id)
                self._adjust_cross_project_taskrels()
            except Exception as exc:
                logging.exception("Project.recalculate_now: '%s'", self.cdb_project_id)
                raise util.ErrorMessage("cdbpcs_scheduling_failed") from exc

        self.aggregate()

        if skip_scheduling or skip_followups:
            logging.debug("  skipping followups (caller is responsible)")
        else:
            logging.debug("  followups\n    %s\n    %s", task_ids, task_ids_res_changes)
            sig.emit(Project, "adjustAllocationsOnly")(self, task_ids_res_changes)
            sig.emit(Project, "do_consistency_checks")(self, task_ids)


@classbody
class Task:
    def recalculate_preparation(self, ctx=None):
        recalculate_preparation(self, ctx)

    def is_recalculate_necessary(self, ctx):
        return is_recalculate_necessary(self, ctx, {"create", "copy"})

    def is_aggregation_necessary(self, ctx):
        return is_aggregation_necessary(ctx)

    def aggregate(self):
        self.Project.aggregate()

    def recalculate(self, ctx=None):
        if ctx and getattr(ctx.sys_args, "batch_mode", False):
            return

        # TODO: Refactor check for existence in db
        if (not ctx or ctx.action != "delete") and not Task.ByKeys(
            cdb_project_id=self.cdb_project_id,
            task_id=self.task_id,
            ce_baseline_id="",
        ):
            return

        if self.is_recalculate_necessary(ctx):
            self.Project.recalculate()

        elif self.is_aggregation_necessary(ctx):
            self.aggregate()

    def isASAP(self):
        return self.constraint_type == ASAP

    def getDaysFcast(self):
        return self.days_fcast if self.days_fcast else 0

    def checkConstraints(self, ctx=None):
        if not self.constraint_type:
            raise util.ErrorMessage("cdbpcs_task_constraints", self.task_name)
        if not self.constraint_date:
            if self.constraint_type not in VALID_CONSTRAINTS_WITHOUT_DATES:
                raise util.ErrorMessage("cdbpcs_task_constraints_with_dates")
        if (
            self.is_group
            and self.constraint_type not in VALID_CONSTRAINTS_FOR_TASK_GROUPS
        ):
            raise util.ErrorMessage("cdbpcs_task_group_constraint", self.task_name)

    def check_parent_constraints(self):
        if (
            self.ParentTask
            and self.ParentTask.constraint_type not in VALID_CONSTRAINTS_FOR_TASK_GROUPS
        ):
            raise util.ErrorMessage(
                "cdbpcs_task_group_constraint", self.ParentTask.task_name
            )
