#!usr/bin/env/powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import mock
import pytest
from cdb import testcase
from cdb.objects import Rule
from cs.platform.web.root.main import _get_dummy_request

from cs.pcs.checklists import RuleReference
from cs.pcs.checklists.tests.integration import util as test_util
from cs.pcs.checklists.web.related import models
from cs.pcs.projects.tasks import Task


@pytest.mark.dependency(name="integration", depends=["cs.pcs.checklists"])
class RelatedChecklistsModelIntegration(testcase.RollbackTestCase):
    PID = "Ptest.rel_cls"
    BID = ""
    EMPTY = {
        "labels": {
            "items": "Prüfpunkte",
            "workobjects": "Zu erstellende Arbeitsgegenstände",
        },
        "checklists": {},
        "objects": [],
    }

    def _create_project(self):
        return test_util.create_project(self.PID, self.BID)

    def _create_task(self):
        return Task.Create(
            cdb_project_id=self.PID,
            ce_baseline_id=self.BID,
            task_id=self.PID,
        )

    def _get_keys(self):
        return mock.Mock(cdb_project_id=self.PID, task_id=self.PID)

    def _create_checklist(self):
        user = test_util.get_user("caddok")
        keys = self._get_keys()
        checklist = test_util.create_checklist(
            keys,
            task_id=self.PID,
            checklist_id=0,
        )
        test_util.create_checklist_item(
            user, keys, checklist, cl_item_id=0, position=10, ko_criterion=0
        )
        return checklist

    def _create_deliverable(self):
        deliverable = test_util.create_checklist(
            self._get_keys(),
            task_id=self.PID,
            checklist_id=1,
            type="Deliverable",
        )
        rule = Rule.Create(name="myRule")
        RuleReference.Create(
            cdb_project_id=deliverable.cdb_project_id,
            checklist_id=deliverable.checklist_id,
            rule_id=rule.name,
        )
        return deliverable

    def _resolve_structure(self, uuid):
        self.maxDiff = None
        request = _get_dummy_request()
        model = models.RelatedChecklistsStructureModel(uuid)
        return model.resolve_structure(request)

    def _resolve_content(self, uuid):
        self.maxDiff = None
        request = _get_dummy_request()
        model = models.RelatedChecklistsContentModel()
        return model.resolve(request, uuid)

    def _resolve_refresh(self, uuid, expanded_checklists):
        self.maxDiff = None
        request = _get_dummy_request()
        model = models.RelatedChecklistsRefreshModel(uuid)
        return model.resolve(request, expanded_checklists=expanded_checklists)

    ####################################
    #
    # RelatedChecklistsStructureModel
    #
    ####################################

    def test_resolve_structure_empty_project(self):
        project = self._create_project()
        self.EMPTY["tasks_checklists_list"] = {project.cdb_object_id: []}
        self.assertEqual(
            self._resolve_structure(project.cdb_object_id),
            self.EMPTY,
        )

    def test_resolve_structure_empty_task(self):
        task = self._create_task()
        self.EMPTY["tasks_checklists_list"] = {task.cdb_object_id: []}
        self.assertEqual(
            self._resolve_structure(task.cdb_object_id),
            self.EMPTY,
        )

    def test_resolve_structure_on_project(self):
        self._create_checklist()
        self._create_deliverable()
        project = self._create_project()
        result = self._resolve_structure(project.cdb_object_id)

        self.assertCountEqual(
            list(result.keys()),
            ["labels", "checklists", "objects", "tasks_checklists_list"],
        )
        self.assertEqual(result["labels"], self.EMPTY["labels"])
        self.assertEqual(len(result["checklists"]), 2)
        self.assertEqual(len(result["objects"]), 2)

    def test_resolve_structure_on_task(self):
        self._create_checklist()
        self._create_deliverable()
        task = self._create_task()
        result = self._resolve_structure(task.cdb_object_id)

        self.assertCountEqual(
            list(result.keys()),
            ["labels", "checklists", "objects", "tasks_checklists_list"],
        )
        self.assertEqual(result["labels"], self.EMPTY["labels"])
        self.assertEqual(len(result["checklists"]), 2)
        self.assertEqual(len(result["objects"]), 2)

    ####################################
    #
    # RelatedChecklistsContentModel
    #
    ####################################

    def test_resolve_content_on_checklist(self):
        cl = self._create_checklist()
        self._create_deliverable()
        self._create_task()
        result = self._resolve_content([f"{cl['cdb_project_id']}@{cl['checklist_id']}"])
        self.assertEqual(
            list(result.keys()),
            ["checklists", "objects"],
        )
        self.assertEqual(len(result["checklists"]), 1)
        self.assertEqual(len(result["objects"]), 1)

    def test_resolve_content_on_deliverable(self):
        self._create_checklist()
        deliverable = self._create_deliverable()
        self._create_task()
        result = self._resolve_content(
            [f"{deliverable['cdb_project_id']}@{deliverable['checklist_id']}"]
        )

        self.assertEqual(
            list(result.keys()),
            ["checklists", "objects"],
        )
        self.assertEqual(len(result["checklists"]), 1)
        self.assertEqual(len(result["objects"]), 1)

    ####################################
    #
    # RelatedChecklistsRefreshModel
    #
    ####################################

    def test_resolve_refresh_no_expanded(self):
        self._create_checklist()
        self._create_deliverable()
        task = self._create_task()
        result = self._resolve_refresh(task["cdb_object_id"], [])

        self.assertCountEqual(
            list(result.keys()),
            ["labels", "checklists", "objects", "tasks_checklists_list"],
        )
        self.assertEqual(len(result["checklists"]), 2)
        self.assertEqual(len(result["objects"]), 2)

    def test_resolve_refresh_cl_expanded(self):
        cl = self._create_checklist()
        self._create_deliverable()
        task = self._create_task()
        result = self._resolve_refresh(task["cdb_object_id"], [cl["checklist_id"]])

        self.assertCountEqual(
            list(result.keys()),
            ["labels", "checklists", "objects", "tasks_checklists_list"],
        )
        self.assertEqual(len(result["checklists"]), 2)
        self.assertEqual(len(result["objects"]), 3)


if __name__ == "__main__":
    unittest.main()
