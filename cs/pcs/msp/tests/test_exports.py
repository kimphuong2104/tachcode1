#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import mock
import pytest

from cs.pcs.msp import exports


@pytest.mark.unit
class TestXmlMergeImport(unittest.TestCase):
    @mock.patch.object(exports, "emit")
    def test_check_export_right_can_update_signal(self, emit):
        proj = mock.MagicMock(msp_active=1, locked_by="")
        proj.CheckAccess.return_value = True
        emit.return_value = lambda x: [False]

        self.assertEqual(exports.XmlExport.check_export_right(proj), False)

    @mock.patch.object(exports, "emit")
    def test_check_export_right_can_update_signal_true(self, emit):
        proj = mock.MagicMock(msp_active=1, locked_by="")
        proj.CheckAccess.return_value = True
        emit.return_value = lambda x: []

        self.assertEqual(exports.XmlExport.check_export_right(proj), True)


if __name__ == "__main__":
    unittest.main()
