#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

from __future__ import absolute_import

import unittest

import mock

from cs.baselining import support


class BaselineTools(unittest.TestCase):
    @mock.patch.object(support.BaselineTools, "is_baseline", return_value=False)
    def test_create_baseline_check_pass(self, is_baseline):
        obj = mock.Mock()
        self.assertIsNone(support.BaselineTools.create_baseline_check(obj))
        is_baseline.assert_called_once_with(obj, readonly=False)

    @mock.patch.object(support.BaselineTools, "is_baseline", return_value=True)
    def test_create_baseline_check_fail(self, is_baseline):
        obj = mock.Mock()
        with self.assertRaises(ValueError):
            support.BaselineTools.create_baseline_check(obj)
        is_baseline.assert_called_once_with(obj, readonly=False)


if __name__ == "__main__":
    unittest.main()
