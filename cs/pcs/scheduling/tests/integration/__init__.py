#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging
from datetime import date

from cdb import testcase, transactions
from cdb.typeconversion import to_user_repr_date_format
from cdb.validationkit import operation

from cs.pcs.projects import tasks
from cs.pcs.scheduling import schedule
from cs.pcs.scheduling.calendar import IndexedCalendar, add_duration
from cs.pcs.scheduling.pretty_print import pretty_print

ASAP = "0"


def setupModule():
    testcase.run_level_setup()


class ScheduleTestCase(testcase.RollbackTestCase):
    original_start_a = date(2016, 9, 7)
    original_end_a = date(2016, 9, 9)
    original_start_b = date(2016, 9, 1)
    original_end_b = date(2016, 9, 5)

    @staticmethod
    def create_task(pid, bid, tid, start, end, workdays, automatic=0):
        return tasks.Task.Create(
            cdb_project_id=pid,
            ce_baseline_id=bid,
            cdb_object_id=tid,
            task_id=tid,
            task_name=f"Task {tid}",
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            start_time_fcast=start,
            end_time_fcast=end,
            days_fcast=workdays,
            parent_task="",
            position=10,
            start_is_early=1,
            end_is_early=0,
            auto_update_time=0,
            status=0,
            cdb_objektart="cdbpcs_task",
            is_group=0,
            milestone=0,
            automatic=automatic,
            constraint_type=ASAP,
            constraint_date=None,
        )

    def create_data(self):
        """
        Setup:
            The year is 2016

            Project X (08/26-09/26)
                └ Task A (09/07-09/09)
                └ Task B (09/01-09/05)

        Initial schedule:
            . 00 02 04 06 08 10 12 14 16 18 20 22 24 26 28 30 32 34 36 38 40 42
            A                         █████████                                  A
            B             █████████                                              B
            . 26 29 30 31 01 02 05 06 07 08 09 12 13 14 15 16 19 20 21 22 23 26  Sep 2016
        """
        with transactions.Transaction():
            pid = "INTEGRATION_TEST_X"
            bid = ""
            self.a = ScheduleTestCase.create_task(
                pid, bid, "A", self.original_start_a, self.original_end_a, 3
            )
            self.b = ScheduleTestCase.create_task(
                pid, bid, "B", self.original_start_b, self.original_end_b, 3
            )
            # create project last to save a Reload call
            self.project = tasks.Project.Create(
                cdb_project_id=pid,
                ce_baseline_id=bid,
                project_name="X",
                category="Forschung",
                project_manager="caddok",
                template=0,
                start_time_fcast=date(2016, 8, 26),
                end_time_fcast=date(2016, 9, 26),
                days_fcast=22,
                auto_update_time=1,
                is_group=1,
                calendar_profile_id="1cb4cf41-0f40-11df-a6f9-9435b380e702",
            )

    def setUp(self):
        super().setUp()
        self.create_data()

    def move_start(self, obj, new_start):
        user_input = {
            "start_time_new": to_user_repr_date_format(new_start),
        }
        operation(
            "cdbpcs_prj_reset_start_time",
            obj,
            user_input=user_input,
        )

    def set_dates(self, obj, new_start, new_end):
        obj.Update(
            start_time_fcast=new_start,
            end_time_fcast=new_end,
        )

    def set_task_duration(self, task, new_duration):
        calendar = IndexedCalendar(
            self.project.calendar_profile_id, self.project.start_time_fcast
        )
        start = calendar.day2network(task.start_time_fcast, False, task.start_is_early)
        new_dr = 2 * new_duration - 1
        end = add_duration(start, new_dr, True, True)
        task.Update(
            start_time_fcast=calendar.network2day(start),
            end_time_fcast=calendar.network2day(end),
            days_fcast=new_duration,
        )

    def calculate_manually(self, obj):
        obj.Update(auto_update_time=0)

    def schedule_manually(self, task):
        task.Update(automatic=0, auto_update_time=0)

    def schedule_automatically(self, obj, mode, constraint_date=None):
        obj.Update(
            automatic=1,
            auto_update_time=1,
            constraint_type=mode,
            constraint_date=constraint_date,
        )

    def is_milestone(self, obj, start_is_early=None):
        obj.Update(
            milestone=1,
            start_is_early=start_is_early,
            end_is_early=start_is_early,
            days_fcast=0,
            start_time_fcast=obj.end_time_fcast,
        )
        obj.Reload()
        self.assertEqual(obj.milestone, 1)
        self.assertEqual(obj.start_is_early, start_is_early)
        self.assertEqual(obj.end_is_early, start_is_early)

    def link_tasks(self, link_type, source, target, gap=0):
        vals = {
            "rel_type": link_type,
            "minimal_gap": gap,
            # predecessor/source
            "pred_project_oid": source.Project.cdb_object_id,
            "cdb_project_id2": source.cdb_project_id,
            "ce_baseline_id2": source.ce_baseline_id,
            "pred_task_oid": source.cdb_object_id,
            "task_id2": source.task_id,
            # successor/target
            "succ_project_oid": target.Project.cdb_object_id,
            "cdb_project_id": target.cdb_project_id,
            "ce_baseline_id": target.ce_baseline_id,
            "succ_task_oid": target.cdb_object_id,
            "task_id": target.task_id,
        }
        return tasks.TaskRelation.Create(**vals)

    def add_child(self, parent, title, start, end, workdays, automatic=0):
        with transactions.Transaction():
            child = ScheduleTestCase.create_task(
                parent.cdb_project_id,
                parent.ce_baseline_id,
                title,
                start,
                end,
                workdays,
                automatic,
            )
            child.Update(parent_task=parent.task_id)
            parent.Update(is_group=1)

        return child

    def schedule_project(self):
        _, __, self.calendar, self.network = schedule(self.project["cdb_project_id"])

    # TODO implement assertPersistentNetworkIs
    # TODO implement combined assertion that calls assertNetworkEqual,
    # assert_dates, assertPersistentNetworkIs and use that everywhere

    def assertNetworkEqual(self, expected_network):
        def _safe_pretty_print():
            try:
                return pretty_print(self.calendar, self.network, expected_network)
            except Exception:
                logging.exception("cannot pretty-print task network")
                return None

        self.assertEqual(
            self.network,
            expected_network,
            _safe_pretty_print(),
        )

    def assert_dates(self, dates):
        messages = []

        for obj, start, end in dates:
            obj.Reload()
            obj_dates = [obj.start_time_fcast, obj.end_time_fcast]
            expected = [start, end]

            if obj_dates != expected:
                expected_str = [f"{repr(x):27}" for x in expected]
                obj_dates_str = [f"{repr(x):27}" for x in obj_dates]
                messages.append(
                    f"[{obj.GetDescription()}]\n"
                    f"  expected: {expected_str}\n"
                    f"  is:       {obj_dates_str}"
                )

        msg_str = "\n".join(messages)
        self.assertEqual(messages, [], msg=(f"Unexpected dates:\n{msg_str}"))
