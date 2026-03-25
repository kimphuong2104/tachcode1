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

from cs.taskmanager.web import main


@pytest.mark.unit
class TasksApp(unittest.TestCase):
    @mock.patch.object(main.BaseApp, "update_app_setup")
    @mock.patch.object(main.fls, "is_available")
    def test_update_app_setup(self, is_available, update_app_setup):
        app = mock.MagicMock(spec=main.TasksApp)
        setup = {"appSettings": {"foo": "bar"}}
        self.assertIsNone(main.TasksApp.update_app_setup(app, setup, "m", "R"))
        self.assertEqual(
            setup,
            {
                "appSettings": {
                    "foo": "bar",
                    "useSubstitutes": is_available.return_value,
                },
            },
        )
        is_available.assert_called_once_with("ORG_010")
        app.include.assert_called_once_with("cs-tasks", "15.5.0")
        update_app_setup.assert_called_once_with(setup, "m", "R")


@pytest.mark.unit
class Utility(unittest.TestCase):
    @mock.patch.object(main.pathlib.Path, "resolve", return_value=42)
    @mock.patch.object(main.static, "Library")
    def test_register(self, Library, resolve):
        main.register()
        Library.assert_called_once_with("cs-tasks", "15.5.0", "42")
        self.assertEqual(Library.return_value.add_file.call_count, 2)
        Library.return_value.add_file.assert_has_calls(
            [
                mock.call("cs-tasks.js"),
                mock.call("cs-tasks.js.map"),
            ]
        )


if __name__ == "__main__":
    unittest.main()
