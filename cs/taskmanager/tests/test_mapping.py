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

from cdb import auth, testcase
from cdb.objects import ByID, Object
from cdb.platform.mom import getObjectHandleFromObjectID
from cs.taskmanager import conditions, mapping
from cs.taskmanager.userdata import ReadStatus, Tags
from cs.taskmanagertest import TestTaskOLC as TaskOLC


def setUpModule():
    testcase.run_level_setup()


@pytest.mark.unit
class MappingUnit(unittest.TestCase):
    @mock.patch.object(mapping.logging, "error")
    @mock.patch.object(mapping, "get_cache")
    def test__get_task_object_no_task_class(self, get_cache, error):
        get_cache.return_value.classes = {}
        self.assertIsNone(mapping._get_task_object("foo", "bar", "contexts"))
        error.assert_called_once_with("unknown task class: '%s'", "bar")

    @mock.patch.object(mapping.logging, "error")
    @mock.patch.object(mapping, "get_cache")
    def test__get_task_object_no_object_class(self, get_cache, error):
        get_cache.return_value.classes = {
            "bar": mock.MagicMock(ObjectsClass=None, classname="BAR"),
        }
        self.assertIsNone(mapping._get_task_object("foo", "bar", "contexts"))
        error.assert_called_once_with("unknown objects class: '%s'", "BAR")

    @mock.patch.object(mapping.logging, "error")
    @mock.patch.object(mapping, "apply_post_select_conditions", return_value=None)
    @mock.patch.object(mapping, "get_cache")
    def test__get_task_object_no_post_match(self, get_cache, post, error):
        objects_class = mock.MagicMock()
        get_cache.return_value.classes = {
            "bar": mock.MagicMock(ObjectsClass=objects_class),
        }
        self.assertIsNone(mapping._get_task_object("foo", "bar", "contexts"))
        post.assert_called_once_with(
            objects_class._FromObjectHandle.return_value,
            "contexts",
        )
        error.assert_not_called()

    @mock.patch.object(mapping, "apply_post_select_conditions")
    @mock.patch.object(mapping, "get_cache")
    def test__get_task_object(self, get_cache, _):
        objects_class = mock.MagicMock()
        get_cache.return_value.classes = {
            "bar": mock.MagicMock(ObjectsClass=objects_class),
        }
        self.assertEqual(
            mapping._get_task_object("foo", "bar", "contexts"),
            objects_class._FromObjectHandle.return_value,
        )


@pytest.mark.integration
class MappingIntegration(testcase.RollbackTestCase):
    @classmethod
    def setUpClass(cls):
        cls.custom_uuid = "bf529417-9ee6-11ec-93ed-334b6053520d"
        cls.root_uuid = "38b7b6d1-9ee5-11ec-872a-334b6053520d"
        cls.parent_uuid = "337706ca-9ee5-11ec-a336-334b6053520d"

        for oid in [cls.custom_uuid, cls.parent_uuid, cls.root_uuid]:
            Tags.SetTaskTags(auth.persno, oid, [])

        ReadStatus.SetTasksUnread(cls.custom_uuid, cls.parent_uuid, cls.root_uuid)

        cls.custom = getObjectHandleFromObjectID(cls.custom_uuid)
        cls.root = getObjectHandleFromObjectID(cls.root_uuid)
        cls.parent = getObjectHandleFromObjectID(cls.parent_uuid)

    @testcase.without_error_logging
    def test__get_task_object_classname_mismatch(self):
        with self.assertRaises(RuntimeError):
            mapping._get_task_object(self.custom, "Test Tasks (OLC)", [])

    def test__get_task_object_without_context_match(self):
        result = mapping._get_task_object(
            self.custom, "Test Task (Custom Status Op)", [self.root_uuid]
        )
        self.assertIsNone(result)

    def test__get_task_object_with_context_match(self):
        ctx = {
            "cs_tasks_test_olc": [
                {"cdb_object_id": self.root.getValue("cdb_object_id", False)},
            ],
        }
        result = mapping._get_task_object(self.parent, "Test Tasks (OLC)", ctx)
        self.assertIsInstance(result, Object)
        self.assertEqual(result.cdb_object_id, self.parent_uuid)

    def test__get_task_object(self):
        result = mapping._get_task_object(
            self.custom, "Test Task (Custom Status Op)", []
        )
        self.assertIsInstance(result, Object)
        self.assertEqual(result.cdb_object_id, self.custom_uuid)

    def test_get_tasks(self):
        olc_task = ByID(self.parent_uuid)
        olc_task.Update(subject_id="caddok", subject_type="Person")
        TaskOLC.Query("subject_id != 'caddok'").Delete()
        condition = conditions.get_conditions(
            types=["cs_tasks_test_custom", "cs_tasks_test_olc"],
            contexts=[],
            my_personal=True,
            my_roles=True,
            substitutes=False,
            users=["caddok"],
        )
        result = mapping.get_tasks(condition)
        self.assertEqual(
            {x.cdb_object_id for x in result},
            {
                self.custom_uuid,
                self.parent_uuid,
                "5bffc5b3-9ee5-11ec-a17e-334b6053520d",  # Early Deadline (截止日期)
                "8437b063-9ee5-11ec-b71f-334b6053520d",  # Läte Deadline (截止日期)
                "7bec50cc-a45b-11ec-82c1-a91c965b8feb",  # Custom 2
            },
        )

    def test_get_tasks_contexts(self):
        olc_task = ByID(self.parent_uuid)
        olc_task.Update(subject_id="caddok", subject_type="Person")
        condition = conditions.get_conditions(
            types=["cs_tasks_test_custom", "cs_tasks_test_olc"],
            contexts=[self.root_uuid],
            my_personal=True,
            my_roles=True,
            substitutes=False,
            users=["caddok"],
            user_personal=True,
            user_roles=True,
        )
        result = mapping.get_tasks(condition)
        self.assertEqual(
            [x.cdb_object_id for x in result],
            [self.parent_uuid],
        )


if __name__ == "__main__":
    unittest.main()
