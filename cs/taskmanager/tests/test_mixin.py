#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

import unittest

import mock
import pytest

from cdb import testcase
from cs.taskmanager import mixin
from cs.taskmanagertest import TestTaskOLC as TaskOLC


def setUpModule():
    testcase.run_level_setup()


@pytest.mark.unit
class Utility(unittest.TestCase):
    def test_get_status_data(self):
        mixin.get_status_data.cache_clear()
        self.assertEqual(
            mixin.get_status_data("cs_tasks_test_olc", 0),
            {
                "status": 0,
                "label": "Neu",
                "dialog": {
                    "zielstatus": "Neu",
                },
                "color": "#F8F8F8",
            },
        )

    def test_get_target_status_data(self):
        self.assertEqual(
            mixin.get_target_status_data("cs_tasks_test_olc", 0, 20),
            {
                "status": 20,
                "label": "Erledigt",
                "dialog": {
                    "zielstatus": "Erledigt",
                },
                "color": "#009600",
                "priority": 1,
            },
        )


@pytest.mark.unit
class WithTasksIntegration(testcase.RollbackTestCase):
    maxDiff = None

    def test_getCsTasksResponsible(self):
        task = TaskOLC(subject_id="caddok", subject_type="Person")
        self.assertEqual(
            mixin.WithTasksIntegration.getCsTasksResponsible(task).personalnummer,
            "caddok",
        )

    def test_getCsTasksStatusData_no_olc(self):
        task = mock.MagicMock(spec=TaskOLC)
        task.GetObjectKind.return_value = None
        self.assertEqual(
            mixin.WithTasksIntegration.getCsTasksStatusData(task),
            None,
        )

    def test_getCsTasksStatusData(self):
        task = TaskOLC(status=0)
        self.assertEqual(
            mixin.WithTasksIntegration.getCsTasksStatusData(task),
            {
                "status": 0,
                "label": "Neu",
                "dialog": {
                    "zielstatus": "Neu",
                },
                "color": "#F8F8F8",
            },
        )

    def test_getCsTasksNextStatuses(self):
        task = TaskOLC.Query()[0]
        task.Update(status=0)
        self.assertEqual(
            mixin.WithTasksIntegration.getCsTasksNextStatuses(task),
            [
                {
                    "color": "#009600",
                    "dialog": {
                        "zielstatus": "Erledigt",
                    },
                    "label": "Erledigt",
                    "priority": 1,
                    "status": 20,
                },
                {
                    "color": "#505050",
                    "dialog": {
                        "zielstatus": "Abgebrochen",
                    },
                    "label": "Abgebrochen",
                    "priority": 2,
                    "status": 30,
                },
            ],
        )

    def test___csTasksSysPostingVals(self):
        task = TaskOLC.Query()[0]
        old = {
            "subject_id": "vendorsupport",
            "subject_type": "Person",
        }
        new = {
            "subject_id": "Documentation",
            "subject_type": "Common Role",
        }
        self.assertEqual(
            mixin.WithTasksIntegration._csTasksSysPostingVals(task, old, new),
            {
                "context_object_id": task.cdb_object_id,
                "title_de": (
                    '" Administrator  (caddok)" hat die Verantwortlichkeit '
                    'auf "Allgemeine Rolle "Dokumentation" (Documentation)" geändert '
                    '(bisher verantwortlich: " Vendorsupport  (vendorsupport)")'
                ),
                "title_en": (
                    '" Administrator  (caddok)" has changed responsibility '
                    'to "Common Role "Documentation" (Documentation)" '
                    '(previously responsible: " Vendorsupport  (vendorsupport)").'
                ),
                "type": "update",
            },
        )


if __name__ == "__main__":
    unittest.main()
