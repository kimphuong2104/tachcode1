#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


import unittest

import mock
import pytest

from cs.pcs.projects.tasks_efforts import helpers


@pytest.mark.unit
class TasksEfforts(unittest.TestCase):
    def test_norm_val_none(self):
        """Test norm_val: val is None, default is returned"""
        self.assertEqual(None, helpers.norm_val(None, None))

    def test_norm_val_empty(self):
        """Test norm_val: val is "", default is returned"""
        self.assertEqual("default", helpers.norm_val("", "default"))

    def test_norm_val(self):
        """Test norm_val: val is neither None nor "", default is returned"""
        self.assertEqual(False, helpers.norm_val(False, "default"))

    def test_find_min_x_none(self):
        """Test find_min: x is None, y is returned"""
        self.assertEqual(False, helpers.find_min(None, False))

    def test_find_min_x_empty(self):
        """Test find_min: x is "", y is returned"""
        self.assertEqual(0, helpers.find_min("", 0))

    def test_find_min_y_none(self):
        """Test find_min: y is None, x is returned"""
        self.assertEqual(False, helpers.find_min(False, None))

    def test_find_min_y_empty(self):
        """Test find_min: y is "", x is returned"""
        self.assertEqual(0, helpers.find_min(0, ""))

    @mock.patch.object(helpers, "min")
    def test_find_min_both_invalid(self, mocked_min):
        """Test find_min: x and y are both False"""
        helpers.find_min(False, False)
        mocked_min.assert_called_once_with(False, False)

    def test_find_min(self):
        """Test find_min"""
        self.assertEqual(0, helpers.find_min(0, 0))

    def test_find_max_x_none(self):
        """Test find_max: x is None, None is returned"""
        self.assertEqual(False, helpers.find_max(None, False))

    def test_find_max_x_empty(self):
        """Test find_max: x is "", None is returned"""
        self.assertEqual(0, helpers.find_max("", 0))

    def test_find_max_y_none(self):
        """Test find_max: y is None, None is returned"""
        self.assertEqual(False, helpers.find_max(False, None))

    def test_find_max_y_empty(self):
        """Test find_max: y is "", None is returned"""
        self.assertEqual(0, helpers.find_max(0, ""))

    @mock.patch.object(helpers, "max")
    def test_find_max_both_invalid(self, mocked_max):
        """Test find_max: x and y are both False"""
        helpers.find_max(False, False)
        mocked_max.assert_called_once_with(False, False)

    def test_find_max(self):
        """Test find_max"""
        self.assertEqual(0, helpers.find_max(0, 0))

    def test_find_max_all_x_none(self):
        """Test find_max_all: x is None, None is returned"""
        self.assertEqual(None, helpers.find_max_all(None, False))

    def test_find_max_all_x_empty(self):
        """Test find_max_all: x is "", None is returned"""
        self.assertEqual(None, helpers.find_max_all("", 0))

    def test_find_max_all_y_none(self):
        """Test find_max_all: y is None, None is returned"""
        self.assertEqual(None, helpers.find_max_all(False, None))

    def test_find_max_all_y_empty(self):
        """Test find_max_all: y is "", None is returned"""
        self.assertEqual(None, helpers.find_max_all(0, ""))

    @mock.patch.object(helpers, "max")
    def test_find_max_all_both_invalid(self, mocked_max):
        """Test find_max_all: x and y are both False"""
        helpers.find_max_all(False, False)
        mocked_max.assert_called_once_with(False, False)

    def test_find_max_all(self):
        """Test find_max_all"""
        self.assertEqual(0, helpers.find_max_all(0, 0))

    def test_add_x_none(self):
        """Test add: x is None, y is returned"""
        self.assertEqual(False, helpers.add(None, False))

    def test_add_x_empty(self):
        """Test add: x is "", y is returned"""
        self.assertEqual(0, helpers.add("", 0))

    def test_add_y_none(self):
        """Test add: y is None, x is returned"""
        self.assertEqual(False, helpers.add(False, None))

    def test_add_y_empty(self):
        """Test add: y is "", x is returned"""
        self.assertEqual(0, helpers.add(0, ""))

    def test_find_add(self):
        """Test add"""
        self.assertEqual(0, helpers.add(0, 0))
