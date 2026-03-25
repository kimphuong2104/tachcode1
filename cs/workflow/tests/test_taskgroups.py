#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import mock
from cdb import testcase
from cs.workflow import taskgroups


def setup_module():
    testcase.run_level_setup()


class ProcessCompletionTaskGroup(testcase.RollbackTestCase):
    maxDiff = None

    def test_Create(self):
        "Create presets empty extension class"
        new = taskgroups.ProcessCompletionTaskGroup.Create(
            cdb_process_id="foo",
            task_id="bar",
        )
        assert set({
            "cdb_classname": "cdbwf_aggregate_proc_completion",
            "cdb_extension_class": "",
            "cdb_process_id": "foo",
            "task_id": "bar",
        }.items()).issubset(set(dict(new).items()))

    def test_create_for_process(self):
        "Create presets empty extension class"
        p = mock.MagicMock(cdb_process_id="foo")
        new = taskgroups.ProcessCompletionTaskGroup.create_for_process(p)
        assert set({
            "cdb_extension_class": "",
            "cdb_process_id": "foo",
            "cdb_classname": "cdbwf_aggregate_proc_completion",
            "cdb_objektart": "cdbwf_aggregate",
            "title": "Process completion",
        }.items()).issubset(set(dict(new).items()))
