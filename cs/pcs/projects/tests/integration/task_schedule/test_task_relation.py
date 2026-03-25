#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import pytest
from cdb import testcase

from cs.pcs.projects import tasks
from cs.pcs.projects.tests.common import generate_task_relation
from cs.pcs.scheduling.tests.integration import ScheduleTestCase


def setupModule():
    testcase.run_level_setup()


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class UpdatePredecessorAndSuccessor(ScheduleTestCase):
    @staticmethod
    def get_oids(
        pred_project_oid, pred_task_oid, succ_project_oid, succ_task_oid, **kwargs
    ):
        return {
            "pred_project_oid": pred_project_oid,
            "pred_task_oid": pred_task_oid,
            "succ_project_oid": succ_project_oid,
            "succ_task_oid": succ_task_oid,
        }

    def test__updateTaskRelations(self):
        "setting oids of linked tasks"
        correct_result = self.get_oids(
            pred_project_oid=self.a.Project.cdb_object_id,
            pred_task_oid=self.a.cdb_object_id,
            succ_project_oid=self.b.Project.cdb_object_id,
            succ_task_oid=self.b.cdb_object_id,
        )

        # first check for created task relation
        # (created by TaskRelation.Create)
        self.link = self.link_tasks("EA", self.a, self.b)
        result = self.get_oids(**self.link)
        self.assertEqual(result, correct_result)

        # remove task relation
        obj = tasks.TaskRelation.KeywordQuery(**result)
        obj.Delete()

        # second check for created task relation
        # (created by operation)
        obj = generate_task_relation(self.a, self.b)
        result = self.get_oids(**obj)
        self.assertEqual(result, correct_result)
