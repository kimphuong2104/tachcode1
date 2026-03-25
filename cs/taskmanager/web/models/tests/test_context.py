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
from cs.taskmanager.web.models import context


def setUpModule():
    testcase.run_level_setup()


@pytest.mark.unit
class TaskContextModel(unittest.TestCase):
    @mock.patch.object(context, "ByID")
    @mock.patch.object(context.TaskClass, "ByClassname")
    def test___init__(self, ByClassname, ByID):
        model = mock.MagicMock(spec=context.TaskContextModel)
        self.assertIsNone(context.TaskContextModel.__init__(model, "classname", "uuid"))
        self.assertEqual(model.task_class, ByClassname.return_value)
        self.assertEqual(model.task, ByID.return_value)

        ByClassname.assert_called_once_with("classname")
        ByClassname.return_value.is_task_object.assert_called_once_with(
            ByID.return_value
        )
        ByID.assert_called_once_with("uuid")
        ByID.return_value.CheckAccess.assert_called_once_with("read")

    @mock.patch.object(context.logging, "error")
    @mock.patch.object(context.TaskClass, "ByClassname", return_value=None)
    def test___init__no_class(self, ByClassname, error):
        model = mock.MagicMock(spec=context.TaskContextModel)
        with self.assertRaises(context.HTTPNotFound):
            context.TaskContextModel.__init__(model, "classname", "uuid")
        error.assert_called_once()

    @mock.patch.object(context.logging, "error")
    @mock.patch.object(context, "ByID", return_value=None)
    @mock.patch.object(context.TaskClass, "ByClassname")
    def test___init__no_task(self, ByClassname, ByID, error):
        model = mock.MagicMock(spec=context.TaskContextModel)
        with self.assertRaises(context.HTTPNotFound):
            context.TaskContextModel.__init__(model, "classname", "uuid")
        error.assert_called_once()

    @mock.patch.object(context.logging, "error")
    @mock.patch.object(context, "ByID")
    @mock.patch.object(context.TaskClass, "ByClassname")
    def test___init__task_unreadable(self, ByClassname, ByID, error):
        ByID.return_value.CheckAccess.return_value = False
        model = mock.MagicMock(spec=context.TaskContextModel)
        with self.assertRaises(context.HTTPNotFound):
            context.TaskContextModel.__init__(model, "classname", "uuid")
        error.assert_called_once()

    @mock.patch.object(context.logging, "error")
    @mock.patch.object(context, "ByID")
    @mock.patch.object(context.TaskClass, "ByClassname")
    def test___init__wrong_task_class(self, ByClassname, ByID, error):
        ByClassname.return_value.is_task_object.return_value = False
        model = mock.MagicMock(spec=context.TaskContextModel)
        with self.assertRaises(context.HTTPNotFound):
            context.TaskContextModel.__init__(model, "classname", "uuid")
        error.assert_called_once()

    @mock.patch.object(context.TaskClass, "ByClassname")
    @mock.patch.object(context, "ByID")
    def test_remove_duplicates(self, ByID, ByClassname):
        t_class = mock.MagicMock()
        t_class.is_task_object = mock.MagicMock(return_value=True)

        ByClassname.return_value = t_class

        ByID.return_value = mock.MagicMock(
            CheckAccess=mock.MagicMock(return_value=True)
        )

        result = [["1", "2", "3"], ["4", "5", "6"]]
        self.assertEqual(
            context.TaskContextModel("task_classname", "oid")._remove_duplicates(
                [["1", "2", "3"], ["4", "5", "6"], ["1", "2", "3"]]
            ),
            result,
        )


if __name__ == "__main__":
    unittest.main()
