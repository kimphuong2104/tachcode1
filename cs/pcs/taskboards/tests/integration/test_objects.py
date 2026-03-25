#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest
from collections import defaultdict

import pytest
from cdb import sig, testcase
from cs.actions import Action

from cs.pcs.issues import Issue
from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task

BASE = "cs.pcs.taskboards"


def add(module_name, slot):
    check_sig_entries[module_name].add(slot)


def method_is_connected(module, name, *slot):
    slot_names = [(x.__module__, x.__name__) for x in sig.find_slots(*slot)]
    return (module, name) in slot_names


def setUpModule():
    testcase.run_level_setup()


# Method is connected to several signals...
# ('module', '<method>'): set([ (<signal 1>), (<signal 2>), ... ])
check_sig_entries = defaultdict(set)


@pytest.mark.dependency(depends=["cs.pcs.taskboards"])
@pytest.mark.integration
class TestObjects(testcase.RollbackTestCase):
    def check_signals_for_module(self):
        for mod_name, slots in list(check_sig_entries.items()):
            for slot in slots:
                self.assertTrue(
                    method_is_connected(mod_name[0], mod_name[1], *slot),
                    f"\n --- method ------------------ {mod_name[0]}.{mod_name[1]}"
                    f"\n --- not connected to slot --- {str(slot)}",
                )
        check_sig_entries.clear()

    def test_signals_connected_to_tasks_objects(self):
        "Check signal connections for file tasks.objects.py"
        module = BASE + "." + "tasks.objects"

        name = "_refresh_taskboards_pre"
        add((module, name), (Project, "delete", "pre"))
        add((module, name), (Project, "state_change", "pre"))
        add((module, name), (Task, "state_change", "pre"))

        name = "_refresh_taskboards_post"
        add((module, name), (Project, "delete", "post"))
        add((module, name), (Project, "state_change", "post"))
        add((module, name), (Task, "state_change", "post"))

        self.check_signals_for_module()

    def test_signals_connected_to_issues_objects(self):
        "Check signal connections for file issues.objects.py"
        module = BASE + "." + "issues.objects"

        name = "_refresh_taskboards_post"
        add((module, name), (Issue, "state_change", "post"))

        name = "refresh_taskboards"
        add((module, name), (Issue, "adjust_dates_on_taskboard"))
        add((module, name), (Issue, "create", "post"))
        add((module, name), (Issue, "copy", "post"))
        add((module, name), (Issue, "delete", "post"))

        self.check_signals_for_module()

    def test_signals_connected_to_actions_objects(self):
        "Check signal connections for file actions.objects.py"
        module = BASE + "." + "actions.objects"

        name = "_refresh_taskboards_post"
        add((module, name), (Action, "state_change", "post"))

        name = "refresh_taskboards"
        add((module, name), (Action, "adjust_dates_on_taskboard"))
        add((module, name), (Action, "create", "post"))
        add((module, name), (Action, "copy", "post"))
        add((module, name), (Action, "delete", "post"))

        self.check_signals_for_module()


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
