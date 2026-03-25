#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import mock
import unittest
import pytest
from cs.workflow.webforms import main


class FormsApp(unittest.TestCase):
    @mock.patch.object(main.sig, "emit")
    @mock.patch.object(main, "REGISTER_LIBRARY", "REGISTER_LIBRARY")
    @mock.patch.object(main, "PLUGIN", "PLUGIN")
    def test__setup(self, emit):
        emit.return_value.return_value = [
            ("one", 1),
            ("two", 2),
        ]
        request = mock.MagicMock()
        self.assertEqual(
            main._setup(None, request),
            "PLUGIN-App",
        )
        emit.assert_called_once_with("REGISTER_LIBRARY")
        emit.return_value.assert_called_once_with()
        request.app.include.assert_has_calls([
            mock.call("one", 1),
            mock.call("two", 2),
        ])
