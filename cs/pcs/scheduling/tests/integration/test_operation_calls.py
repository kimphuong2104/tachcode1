#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from datetime import date

import pytest
from cdb import testcase
from cdb.constants import (
    kOperationCopy,
    kOperationDelete,
    kOperationModify,
    kOperationNew,
)
from cdb.validationkit import operation
from mock import MagicMock, patch

from cs.pcs.projects import Project, scheduling
from cs.pcs.projects.tasks import Task, TaskRelation
from cs.pcs.scheduling.tests.integration import ScheduleTestCase


def setup_module():
    testcase.run_level_setup()


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class OperationCalls(ScheduleTestCase):
    cdb_project_id = "OPERATIONS_CALLS_INTEG_PROJ"

    def call_operation_and_assert(
        self, schedule_calls, aggregate_calls, opName, target, **op_params
    ):
        dummy_return_value = (MagicMock(), MagicMock(), MagicMock(), MagicMock())
        with patch.object(
            scheduling, "schedule", return_value=dummy_return_value
        ) as schedule, patch.object(
            scheduling.tasks_efforts, "aggregate_changes"
        ) as aggregate_changes:
            operation(opName, target, **op_params)

        self.assertEqual(
            (schedule.call_count, aggregate_changes.call_count),
            (schedule_calls, aggregate_calls),
        )

    def test_new_project(self):
        self.call_operation_and_assert(
            1,
            1,
            kOperationNew,
            Project,
            preset={"cdb_project_id": self.cdb_project_id},
            user_input={"project_name": self.cdb_project_id, "template": 0},
        )

    def test_modify_project(self):
        self.call_operation_and_assert(
            1, 1, kOperationModify, self.project, user_input={"auto_update_time": 2}
        )
        self.call_operation_and_assert(
            0,
            0,
            kOperationModify,
            self.project,
            user_input={"project_name": "new_name"},
        )

    def test_delete_project(self):
        self.call_operation_and_assert(0, 0, kOperationDelete, self.project)

    def test_copy_project(self):
        self.call_operation_and_assert(1, 1, kOperationCopy, self.project)

    def test_create_task(self):
        self.project.setProjectManager(MagicMock(error=0))
        self.call_operation_and_assert(
            1,
            1,
            kOperationNew,
            Task,
            preset={
                "cdb_project_id": self.project.cdb_project_id,
                "subject_id": "caddok",
                "subject_type": "Person",
            },
            user_input={
                "task_name": "TEMP_TASK_OPERATIONS_CALL",
            },
        )

    def test_modify_task_scheduling(self):
        self.call_operation_and_assert(
            1,
            1,
            kOperationModify,
            self.a,
            user_input={"start_time_fcast": date(2016, 9, 8)},
        )

    def test_modify_task_no_scheduling(self):
        self.call_operation_and_assert(
            0, 0, kOperationModify, self.a, user_input={"task_name": "new_name"}
        )

    def test_modify_task_only_aggregation(self):
        self.call_operation_and_assert(
            0, 1, kOperationModify, self.a, user_input={"days": 2}
        )

    def test_delete_task(self):
        self.call_operation_and_assert(1, 1, kOperationDelete, self.a)

    def test_copy_task(self):
        self.project.setProjectManager(MagicMock(error=0))
        self.call_operation_and_assert(1, 1, kOperationCopy, self.b)

    def test_task_relship_new(self):
        self.call_operation_and_assert(
            1,
            1,
            kOperationNew,
            TaskRelation,
            preset={
                "cdb_project_id": self.project.cdb_project_id,
                "task_id": self.a.task_id,
                "cdb_project_id2": self.project.cdb_project_id,
                "task_id2": self.b.task_id,
                "succ_project_oid": self.project.cdb_object_id,
                "succ_task_oid": self.a.task_id,
                "pred_project_oid": self.project.cdb_object_id,
                "pred_task_oid": self.b.task_id,
                "rel_type": "EA",
                "violation": 0,
            },
        )

    def create_task_rel(self):
        return TaskRelation.Create(
            cdb_project_id=self.project.cdb_project_id,
            task_id=self.a.task_id,
            cdb_project_id2=self.project.cdb_project_id,
            task_id2=self.b.task_id,
            succ_project_oid=self.project.cdb_object_id,
            succ_task_oid=self.a.task_id,
            pred_project_oid=self.project.cdb_object_id,
            pred_task_oid=self.b.task_id,
            rel_type="EA",
        )

    def test_task_relship_delete(self):
        task_rel = self.create_task_rel()
        self.call_operation_and_assert(1, 1, kOperationDelete, task_rel)

    def test_task_relship_modify(self):
        task_rel = self.create_task_rel()
        self.call_operation_and_assert(
            1, 1, kOperationModify, task_rel, user_input={"rel_type": "AE"}
        )
