#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import unittest

import mock
import pytest

from cdb import testcase
from cs.taskmanager import userdata
from cs.taskmanager.web.models import data
from cs.taskmanagertest import TestTaskOLC as TaskOLC


def setUpModule():
    testcase.run_level_setup()


@pytest.mark.unit
class Utility(unittest.TestCase):
    @mock.patch.object(data.PersonalSettings, "getValue", return_value=None)
    def get_max_tasks_default(self, _):
        "return default max_tasks if no setting exists"
        self.assertEqual(
            data.get_max_tasks(),
            5000,
        )

    @mock.patch.object(data.PersonalSettings, "getValue", return_value="foo")
    def get_max_tasks_broken(self, _):
        "return default max_tasks if setting is broken"
        self.assertEqual(
            data.get_max_tasks(),
            5000,
        )

    @mock.patch.object(data.PersonalSettings, "getValue", return_value="42")
    def get_max_tasks(self, _):
        "return max_tasks from setting"
        self.assertEqual(
            data.get_max_tasks(),
            42,
        )

    @mock.patch.object(data.User, "ByKeys")
    def test_check_show_tasks(self, ByKeys):
        self.assertIsNone(
            data.check_show_tasks(["foo", "bar"]),
        )

    @mock.patch.object(data.User, "ByKeys", return_value=None)
    def test_check_show_tasks_missing_user(self, ByKeys):
        with self.assertRaises(data.HTTPForbidden) as error:
            data.check_show_tasks(["foo", "bar"])

        self.assertEqual(
            str(error.exception),
            "Die Aufgaben des Anwenders sind für Sie nicht einsehbar: 'foo, bar'",
        )

    @mock.patch.object(data.User, "ByKeys")
    def test_check_show_tasks_access_denied(self, ByKeys):
        ByKeys.return_value.CheckAccess.return_value = None
        with self.assertRaises(data.HTTPForbidden) as error:
            data.check_show_tasks(["foo", "bar"])

        self.assertEqual(
            str(error.exception),
            "Die Aufgaben des Anwenders sind für Sie nicht einsehbar: 'foo, bar'",
        )

    def test__get_tasks_condition_deadline_missing(self):
        with self.assertRaises(KeyError):
            data._get_tasks_condition({})

    def test__get_tasks_condition_deadline_active_missing(self):
        with self.assertRaises(TypeError):
            data._get_tasks_condition({"deadline": "?", "responsible": "?"})

    @mock.patch.object(data, "get_conditions")
    @mock.patch.object(data, "get_backend_condition", return_value={"foo": "bar"})
    def test__get_tasks_condition_empty(self, get_backend_condition, get_conditions):
        self.assertEqual(
            data._get_tasks_condition(
                {
                    "deadline": {
                        "active": None,
                    },
                    "responsible": {},
                }
            ),
            get_conditions.return_value,
        )
        get_conditions.assert_called_once_with(foo="bar")
        get_backend_condition.assert_called_once_with(
            {
                "users": set(),
                "my_personal": False,
                "my_roles": False,
                "substitutes": False,
                "absence": False,
                "user_personal": False,
                "user_roles": False,
                "types": set(),
                "contexts": set(),
            }
        )

    @mock.patch.object(data, "get_conditions")
    @mock.patch.object(data, "get_backend_condition", return_value={"foo": "bar"})
    def test__get_tasks_condition_all_but_deadline(
        self, get_backend_condition, get_conditions
    ):
        self.assertEqual(
            data._get_tasks_condition(
                {
                    "deadline": {
                        "active": None,
                    },
                    "users": ["u", "s", "s"],
                    "responsible": {
                        "my_personal": True,
                        "my_roles": True,
                        "substitutes": True,
                        "absence": True,
                        "user_personal": True,
                        "user_roles": True,
                    },
                    "types": ["t", "y", "y"],
                    "contexts": [None, "c", "x", "x"],
                }
            ),
            get_conditions.return_value,
        )
        get_conditions.assert_called_once_with(foo="bar")
        get_backend_condition.assert_called_once_with(
            {
                "users": set(["u", "s"]),
                "my_personal": True,
                "my_roles": True,
                "substitutes": True,
                "absence": True,
                "user_personal": True,
                "user_roles": True,
                "types": {"t", "y"},
                "contexts": {"c", "x"},
            }
        )

    @mock.patch.object(data, "get_conditions")
    @mock.patch.object(data, "get_backend_condition", return_value={"foo": "bar"})
    def test__get_tasks_condition_range(self, get_backend_condition, get_conditions):
        self.assertEqual(
            data._get_tasks_condition(
                {
                    "deadline": {
                        "active": "range",
                        "range": {
                            "start": "S",
                            "end": "E",
                        },
                    },
                    "responsible": {},
                }
            ),
            get_conditions.return_value,
        )
        get_conditions.assert_called_once_with(foo="bar")
        get_backend_condition.assert_called_once_with(
            {
                "start": "S",
                "end": "E",
                "users": set(),
                "my_personal": False,
                "my_roles": False,
                "substitutes": False,
                "absence": False,
                "user_personal": False,
                "user_roles": False,
                "types": set(),
                "contexts": set(),
            }
        )

    @mock.patch.object(data, "get_conditions")
    @mock.patch.object(data, "get_backend_condition", return_value={"foo": "bar"})
    def test__get_tasks_condition_days(self, get_backend_condition, get_conditions):
        self.assertEqual(
            data._get_tasks_condition(
                {
                    "deadline": {
                        "active": "days",
                        "days": -5,
                    },
                    "responsible": {},
                }
            ),
            get_conditions.return_value,
        )
        get_conditions.assert_called_once_with(foo="bar")
        get_backend_condition.assert_called_once_with(
            {
                "days": -5,
                "users": set(),
                "my_personal": False,
                "my_roles": False,
                "substitutes": False,
                "absence": False,
                "user_personal": False,
                "user_roles": False,
                "types": set(),
                "contexts": set(),
            }
        )


@pytest.mark.unit
class Data(unittest.TestCase):
    @mock.patch.object(data, "check_show_tasks")
    @mock.patch.object(data, "get_tasks")
    def test_get_tasks(self, get_tasks, check_show_tasks):
        model = mock.MagicMock(spec=data.Data)
        self.assertEqual(
            data.Data.get_tasks(model, "C", "R"),
            model._get_rest_tasks.return_value,
        )
        model._get_rest_tasks.assert_called_once_with(get_tasks.return_value, "R")
        get_tasks.assert_called_once_with(model.get_tasks_condition.return_value, 5001)
        check_show_tasks.assert_called_once_with(
            model.get_tasks_condition.return_value.users
        )
        model.get_tasks_condition.assert_called_once_with("C")

    @mock.patch.object(data, "get_restlink")
    @mock.patch.object(data, "check_show_tasks")
    @mock.patch.object(data, "get_tasks", return_value=["A", "B"])
    def test_get_updates(self, get_tasks, check_show_tasks, get_restlink):
        model = mock.MagicMock(spec=data.Data)
        self.assertEqual(
            data.Data.get_updates(model, "C", "R"),
            {"updates": 2 * [get_restlink.return_value]},
        )
        get_tasks.assert_called_once_with(model.get_tasks_condition.return_value)
        check_show_tasks.assert_called_once_with(
            model.get_tasks_condition.return_value.users
        )
        model.get_tasks_condition.assert_called_once_with("C")

        self.assertEqual(get_restlink.call_count, 2)
        get_restlink.assert_has_calls(
            [
                mock.call("A", "R"),
                mock.call("B", "R"),
            ]
        )

    @mock.patch.object(data, "ByID")
    def test_get_target_statuses(self, ByID):
        ByID.return_value.getCsTasksNextStatuses.return_value = ["foo", "bar"]
        model = mock.MagicMock(spec=data.Data)
        self.assertEqual(
            data.Data.get_target_statuses(model, "uuid"),
            {"targets": ["foo", "bar"]},
        )

    @mock.patch.object(data, "ByID")
    def test_get_target_statuses_invalid_result(self, ByID):
        # result must be a list
        model = mock.MagicMock(spec=data.Data)
        with self.assertRaises(data.HTTPInternalServerError):
            data.Data.get_target_statuses(model, "uuid")


@pytest.mark.integration
class DataIntegration(testcase.RollbackTestCase):
    def test__get_rest_tasks(self):
        task1 = TaskOLC.Create(name="itest data1")
        task2 = TaskOLC.Create(name="itest data2")
        setattr(task1, "@cs_tasks_class", "foo")
        userdata.ReadStatus.SetTasksRead(task1.cdb_object_id)
        userdata.Tags.SetTaskTags(userdata.auth.persno, task2.cdb_object_id, ["a", "b"])
        userdata.Tags.SetTaskTags(userdata.auth.persno, "?", ["c"])
        result = data.Data()._get_rest_tasks([task1, task2], None)
        self.assertEqual(
            set(result.keys()),
            {"objects", "readStatus", "tags", "allTags"},
        )
        self.assertEqual(
            [x["@id"] for x in result["objects"]],
            [
                "http://localhost/api/v1/collection/test_task_olc/{}".format(
                    task1.cdb_object_id
                ),
                "http://localhost/api/v1/collection/test_task_olc/{}".format(
                    task2.cdb_object_id
                ),
            ],
        )
        self.assertEqual(
            {k: v for k, v in result.items() if k != "objects"},
            {
                "allTags": ["a", "b", "c"],
                "readStatus": [task1.cdb_object_id],
                "tags": {task2.cdb_object_id: ["a", "b"]},
            },
        )

    def test__is_task_object(self):
        task = TaskOLC.Create(name="itest data1")
        self.assertTrue(data.Data()._is_task_object(task))

    def test__is_task_object_fail(self):
        user = data.User.ByKeys("caddok")
        self.assertFalse(data.Data()._is_task_object(user))


if __name__ == "__main__":
    unittest.main()
