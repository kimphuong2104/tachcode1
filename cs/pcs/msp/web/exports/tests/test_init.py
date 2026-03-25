#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest
from contextlib import contextmanager

import mock

from cs.pcs.msp.web import exports


class TestExportXMLAppModel(unittest.TestCase):
    def test__init__(self):
        model = exports.ExportXMLAppModel("proj1")

        self.assertEqual(model.cdb_project_id, "proj1")
        self.assertEqual(model.tmp_filename, "")

    @mock.patch.object(exports, "Project")
    def test_prepare(self, Project):
        project = mock.MagicMock()
        project.get_temp_export_xml_file = mock.MagicMock(return_value="tmp_file")

        Project.Query.return_value = [project]
        model = exports.ExportXMLAppModel("proj1")

        model.prepare()

        Project.Query.assert_called_once_with(
            "cdb_project_id='proj1' AND ce_baseline_id=''", access="read"
        )
        self.assertEqual(model.tmp_filename, "tmp_file")

    def test_get_file_name(self):
        model = exports.ExportXMLAppModel("proj1")
        self.assertEqual(model.get_file_name(), "proj1")

    def test__iter__(self):
        @contextmanager
        def file_context(tmp_filename):
            try:
                yield ["1", "2"]
            finally:
                pass

        with mock.patch("cs.pcs.msp.web.exports.file_context", file_context):
            model = exports.ExportXMLAppModel("proj1")

            it = iter(model)
            self.assertEqual(next(it), b"1")
            self.assertEqual(next(it), b"2")

            with self.assertRaises(StopIteration):
                next(it)


if __name__ == "__main__":
    unittest.main()
