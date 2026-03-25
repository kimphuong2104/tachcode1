#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access


import datetime

import pytest
from cdb import sqlapi, testcase

from cs.pcs.projects import helpers
from cs.pcs.projects.tasks import Task

DATE = datetime.date(2022, 8, 5)


@pytest.mark.unit
class Helpers(testcase.RollbackTestCase):
    def test__filter_hook_vals(self):
        "given prefix is removed from values and value without prefix is dropped"

        vals = {"prefix.foo": "foo", "not_prefix.bar": "bar"}
        self.assertDictEqual({"foo": "foo"}, helpers._filter_hook_vals(vals, "prefix."))

    def test_ensure_date_invalid_str(self):
        self.assertIsNone(helpers.ensure_date("x"))

    def test_ensure_date_legacy_date_str(self):
        self.assertEqual(helpers.ensure_date("05.08.2022"), DATE)

    def test_ensure_date_legacy_datetime_str(self):
        self.assertEqual(helpers.ensure_date("05.08.2022 11:12:13"), DATE)

    def test_ensure_date_iso_date_str(self):
        self.assertEqual(helpers.ensure_date("2022-08-05"), DATE)

    def test_ensure_date_iso_datetime_str(self):
        self.assertEqual(helpers.ensure_date("2022-08-05T11:12:13"), DATE)

    def test_ensure_date_iso_datetimezone_str(self):
        self.assertEqual(helpers.ensure_date("2022-08-05T11:12:13Z"), DATE)

    def test_ensure_date_date(self):
        self.assertEqual(helpers.ensure_date(DATE), DATE)

    def test_ensure_date_datetime(self):
        self.assertEqual(
            helpers.ensure_date(datetime.datetime(2022, 8, 5, 8, 5, 3, 121)), DATE
        )


def get_tasks():
    return [
        Task(cdb_project_id="proj_id", task_id="1", parent_task=""),
        {"cdb_project_id": "proj_id", "task_id": "2", "parent_task": ""},
        Task(cdb_project_id="proj_id", task_id="1.1", parent_task="1"),
        sqlapi.Record(
            "cdbpcs_task", cdb_project_id="proj_id", task_id="1.2", parent_task="1"
        ),
        Task(cdb_project_id="proj_id", task_id="2.1", parent_task="2"),
    ]


def test_index_tasks_by_parent_and_id():
    tasks = get_tasks()

    res_dict, mapped = helpers.index_tasks_by_parent_and_id(tasks)
    res_dict_expected = {"": ["1", "2"], "1": ["1.1", "1.2"], "2": ["2.1"]}
    mapped_expected = {
        "1": Task(cdb_project_id="proj_id", task_id="1", parent_task=""),
        "2": {"cdb_project_id": "proj_id", "task_id": "2", "parent_task": ""},
        "1.1": Task(cdb_project_id="proj_id", task_id="1.1", parent_task="1"),
        "1.2": sqlapi.Record(
            "cdbpcs_task", cdb_project_id="proj_id", task_id="1.2", parent_task="1"
        ),
        "2.1": Task(cdb_project_id="proj_id", task_id="2.1", parent_task="2"),
    }
    assert res_dict_expected == res_dict
    assert [task["task_id"] for task in mapped_expected.values()] == [
        task["task_id"] for task in mapped.values()
    ]


def test_sort_tasks_bottom_up():
    tasks = [
        Task(cdb_project_id="proj_id", task_id="1.1", parent_task="1"),
        Task(cdb_project_id="proj_id", task_id="1", parent_task=""),
        Task(cdb_project_id="proj_id", task_id="2.1", parent_task="2"),
        {"cdb_project_id": "proj_id", "task_id": "2", "parent_task": ""},
        sqlapi.Record(
            "cdbpcs_task", cdb_project_id="proj_id", task_id="1.2", parent_task="1"
        ),
    ]
    expected = get_tasks()[::-1]
    actual = helpers.sort_tasks_bottom_up(tasks)
    assert [t["task_id"] for t in expected] == [t["task_id"] for t in actual]
