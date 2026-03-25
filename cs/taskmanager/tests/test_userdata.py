#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

import unittest

import pytest

from cdb import testcase
from cs.taskmanager import userdata
from cs.taskmanagertest import TestTaskOLC as TaskOLC


def setUpModule():
    testcase.run_level_setup()


@pytest.mark.integration
class Tags(testcase.RollbackTestCase):
    __persno__ = "foo"

    def test_GetTagObjects(self):
        task = TaskOLC.Create(name="integr_test tags")
        userdata.Tags.SetTaskTags(self.__persno__, task.cdb_object_id, ["B", "A"])
        tags = userdata.Tags.GetTagObjects(self.__persno__, task.cdb_object_id)
        self.assertEqual(tags.tag, ["A", "B"])

    def test_GetTaskTags(self):
        task = TaskOLC.Create(name="integr_test tags")
        userdata.Tags.SetTaskTags(self.__persno__, task.cdb_object_id, ["B", "A"])
        tags = userdata.Tags.GetTaskTags(self.__persno__, task.cdb_object_id)
        self.assertEqual(tags, ["A", "B"])

    def test_GetUserTags(self):
        userdata.Tags.SetTaskTags(userdata.auth.persno, "A", ["a", "A"])
        userdata.Tags.SetTaskTags(userdata.auth.persno, "B", ["b", "B"])
        tags = userdata.Tags.GetUserTags()
        # explicitly sorted, but MS SQL does it backwards compared to ORA and sqlite
        self.assertEqual(
            set(tags),
            {"A", "B", "a", "b"},
        )

    def test_GetIndexedTags(self):
        a = TaskOLC.Create(name="integr_test tags a")
        b = TaskOLC.Create(name="integr_test tags b")
        userdata.Tags.SetTaskTags(userdata.auth.persno, a.cdb_object_id, ["a", "A"])
        userdata.Tags.SetTaskTags(userdata.auth.persno, b.cdb_object_id, ["b", "B"])
        tags = userdata.Tags.GetIndexedTags([a.cdb_object_id, b.cdb_object_id])
        self.assertEqual(
            tags,
            {
                a.cdb_object_id: ["A", "a"],
                b.cdb_object_id: ["B", "b"],
            },
        )

    def test_SetTaskTags(self):
        persno = userdata.auth.persno
        userdata.Tags.SetTaskTags(persno, "uuid", ["xxx"])
        self.assertIsNone(userdata.Tags.SetTaskTags(persno, "uuid", ["a", "A"]))
        self.assertEqual(
            set(userdata.Tags.GetUserTags()),
            # explicitly sorted, but MS SQL does it backwards compared to ORA and sqlite
            {"A", "a"},
        )


@pytest.mark.unit
class ReadStatus(testcase.RollbackTestCase):
    def test_SetTasksRead(self):
        self.assertIsNone(userdata.ReadStatus.SetTasksRead("a", "b", "A"))
        self.assertEqual(
            set(userdata.ReadStatus.GetReadStatus(["b", "A", "a"])),
            {"A", "a", "b"},
        )

    def test_SetTasksUnread(self):
        self.assertIsNone(userdata.ReadStatus.SetTasksRead("a", "b", "A"))
        self.assertIsNone(userdata.ReadStatus.SetTasksUnread("b", "A"))
        self.assertEqual(
            userdata.ReadStatus.GetReadStatus(["b", "A", "a"]),
            ["a"],
        )


if __name__ == "__main__":
    unittest.main()
