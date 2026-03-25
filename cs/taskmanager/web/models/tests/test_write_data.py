#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest

import mock
import pytest

from cdb import testcase
from cs.taskmanager.web.models import write_data


def setUpModule():
    testcase.run_level_setup()


@pytest.mark.unit
class WriteDataBaseModel(unittest.TestCase):
    @mock.patch.object(
        write_data.sqlapi,
        "RecordSet2",
        return_value=[
            mock.MagicMock(cdb_object_id="b"),
            mock.MagicMock(cdb_object_id="a"),
        ],
    )
    @mock.patch.object(
        write_data, "get_grouped_data", return_value={"tableA": ["a"], "tableB": ["b"]}
    )
    def test_check_read(self, get_grouped_data, RecordSet2):
        model = mock.MagicMock(spec=write_data.WriteDataBaseModel)
        self.assertIsNone(write_data.WriteDataBaseModel.check_read(model, "a", "b"))
        RecordSet2.assert_has_calls(
            [
                mock.call("tableA", "cdb_object_id IN ('a')", access="read"),
                mock.call("tableB", "cdb_object_id IN ('b')", access="read"),
            ],
            any_order=True,
        )

    @mock.patch.object(write_data.logging, "error")
    @mock.patch.object(
        write_data, "get_grouped_data", return_value={"tableA": ["a", "B"]}
    )
    def test_check_read_missing(self, get_grouped_data, error):
        model = mock.MagicMock(spec=write_data.WriteDataBaseModel)
        with self.assertRaises(write_data.HTTPNotFound):
            write_data.WriteDataBaseModel.check_read(model, "a", "b")
        error.assert_called_once_with("IDs missing in cdb_object: %s", {"b"})

    @mock.patch.object(write_data.logging, "error")
    @mock.patch.object(
        write_data.sqlapi,
        "RecordSet2",
        return_value=[
            mock.MagicMock(cdb_object_id="a"),
        ],
    )
    @mock.patch.object(
        write_data, "get_grouped_data", return_value={"tableA": ["a"], "tableB": ["b"]}
    )
    def test_check_read_missing2(self, get_grouped_data, RecordSet2, error):
        model = mock.MagicMock(spec=write_data.WriteDataBaseModel)
        with self.assertRaises(write_data.HTTPNotFound):
            write_data.WriteDataBaseModel.check_read(model, "a", "b")
        error.assert_called_once_with("IDs missing in %s: %s", "tableB", {"b"})


@pytest.mark.unit
class WriteReadStatus(unittest.TestCase):
    @mock.patch.object(write_data.ReadStatus, "SetTasksUnread")
    @mock.patch.object(write_data.ReadStatus, "SetTasksRead")
    def test_set_read_status(self, SetTasksRead, SetTasksUnread):
        model = mock.MagicMock(spec=write_data.WriteReadStatus)
        self.assertIsNone(
            write_data.WriteReadStatus.set_read_status(
                model, ["r1", "r2"], ["u1", "u2"]
            )
        )
        model.check_read.assert_called_once_with("r1", "r2", "u1", "u2")
        SetTasksRead.assert_called_once_with("r1", "r2")
        SetTasksUnread.assert_called_once_with("u1", "u2")


@pytest.mark.unit
class WriteTags(unittest.TestCase):
    @mock.patch.object(write_data.Tags, "GetTaskTags")
    @mock.patch.object(write_data.Tags, "SetTaskTags")
    def test_set_tags(self, SetTaskTags, GetTaskTags):
        model = mock.MagicMock(spec=write_data.WriteTags)
        self.assertEqual(
            write_data.WriteTags.set_tags(model, {"a": "A", "b": "B"}),
            {
                "a": GetTaskTags.return_value,
                "b": GetTaskTags.return_value,
            },
        )
        model.check_read.assert_called_once_with("a", "b")
        SetTaskTags.assert_has_calls(
            [
                mock.call(write_data.auth.persno, "a", "A"),
                mock.call(write_data.auth.persno, "b", "B"),
            ],
            any_order=True,
        )


if __name__ == "__main__":
    unittest.main()
