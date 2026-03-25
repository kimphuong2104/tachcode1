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

from cs.taskmanager.web import models


@pytest.mark.unit
class ModelWithUserSettings(unittest.TestCase):
    @mock.patch.object(models, "PersonalSettings")
    def test__convert_rest_id(self, PersonalSettings):
        model = mock.MagicMock(spec=models.ModelWithUserSettings)
        self.assertIsNone(models.ModelWithUserSettings.__init__(model))
        self.assertEqual(model.settings, PersonalSettings.return_value)
        PersonalSettings.return_value.invalidate.assert_called_once()

    def test__get_setting(self):
        model = mock.MagicMock(
            spec=models.ModelWithUserSettings,
            __id1__=models.ModelWithUserSettings.__id1__,
        )
        model.settings = mock.MagicMock()
        self.assertEqual(
            models.ModelWithUserSettings._get_setting(model, "foo"),
            model.settings.getValueOrDefault.return_value,
        )
        model.settings.getValueOrDefault.assert_called_once_with(
            "cs.taskmanager", "foo", None
        )

    def test__set_setting(self):
        model = mock.MagicMock(
            spec=models.ModelWithUserSettings,
            __id1__=models.ModelWithUserSettings.__id1__,
        )
        model.settings = mock.MagicMock()
        self.assertIsNone(
            models.ModelWithUserSettings._set_setting(model, "foo", "bar")
        )
        model.settings.setValue.assert_called_once_with("cs.taskmanager", "foo", "bar")


if __name__ == "__main__":
    unittest.main()
