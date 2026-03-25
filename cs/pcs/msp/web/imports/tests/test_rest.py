#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=no-value-for-parameter

import unittest
from datetime import datetime

import mock
import pytest
from webob.exc import HTTPNotFound

from cs.pcs.msp.web.imports import rest


@pytest.mark.unit
class TestRestApp(unittest.TestCase):
    def test__is_date(self):
        self.assertEqual(rest.is_date("12-01-2022"), False)
        self.assertEqual(rest.is_date(datetime.now()), True)
        self.assertEqual(rest.is_date(datetime.now().date()), True)
        self.assertEqual(rest.is_date(None), False)

    @mock.patch.object(rest, "to_user_repr_date_format")
    def test__to_locale_date(self, to_usr_format):
        now = datetime.now()
        self.assertEqual(rest.to_locale_date(None), to_usr_format.return_value)
        self.assertEqual(rest.to_locale_date(now), to_usr_format.return_value)
        self.assertEqual(rest.to_locale_date("12-01-2022"), to_usr_format.return_value)

    @mock.patch.object(rest, "to_locale_date")
    def test__format_date_time(self, to_locale_date):
        to_locale_date.side_effect = lambda x: x.strftime("%d-%m-%Y")
        date1 = datetime(2022, 3, 17)
        date2 = datetime(2022, 4, 1)
        diff = {
            "start": date1,
            "end": date2,
            "sth_else": {"start": date2, "end": date1},
        }
        rest.format_date_time(diff)
        expected = {
            "start": "17-03-2022",
            "end": "01-04-2022",
            "sth_else": {"start": "01-04-2022", "end": "17-03-2022"},
        }
        self.assertDictEqual(diff, expected)

    @mock.patch.object(rest, "format_date_time")
    def test__copy_diffs(self, format_date_time):
        format_date_time.side_effect = lambda x: x
        diff = {1: 2}
        copied_diff = rest.copy_diffs(diff)
        self.assertDictEqual(diff, copied_diff)
        assert diff is not copied_diff


@pytest.mark.unit
class TestImportResultModel(unittest.TestCase):
    maxDiff = None

    @mock.patch.object(rest, "get_and_check_object")
    def test__init_no_project(self, get_and_check_object):
        def mocked_get_and_check_obj(_type, *args, **kwargs):
            if _type is rest.Project:
                return None
            else:
                return mock.MagicMock()

        get_and_check_object.side_effect = mocked_get_and_check_obj
        extra_parameters = {"cdb_project_id": "A"}

        with self.assertRaises(HTTPNotFound):
            rest.ImportResultModel(extra_parameters)

        get_and_check_object.assert_called_once()

    @mock.patch.object(rest, "get_and_check_object")
    def test__init_no_document(self, get_and_check_object):
        def mocked_get_and_check_obj(_type, *args, **kwargs):
            if _type is rest.Project:
                return mock.MagicMock(cdb_project_id="A")

        get_and_check_object.side_effect = mocked_get_and_check_obj
        extra_parameters = {"cdb_project_id": "A", "z_nummer": "D1"}

        with self.assertRaises(HTTPNotFound):
            rest.ImportResultModel(extra_parameters)

        get_and_check_object.assert_has_calls(
            [
                mock.call(rest.Project, "read", cdb_project_id="A", ce_baseline_id=""),
                mock.call(rest.Document, "read", z_nummer="D1", z_index=""),
            ]
        )

    def test_get_hide_import_preview(self):
        tasks = mock.MagicMock(added=[], deleted=[])
        import_result = mock.MagicMock(tasks=tasks, only_system_attributes=[True])
        with mock.patch.object(rest.ImportResultModel, "__init__", lambda x: None):
            model = rest.ImportResultModel()
            self.assertEqual(model.get_hide_import_preview(import_result), True)

    def test_get_hide_import_preview_deleted(self):
        tasks = mock.MagicMock(added=[], deleted=["a"])
        import_result = mock.MagicMock(tasks=tasks, only_system_attributes=[True])
        with mock.patch.object(rest.ImportResultModel, "__init__", lambda x: None):
            model = rest.ImportResultModel()
            self.assertEqual(model.get_hide_import_preview(import_result), False)

    def test_get_hide_import_preview_added(self):
        tasks = mock.MagicMock(added=["a"], deleted=[])
        import_result = mock.MagicMock(tasks=tasks, only_system_attributes=[True])
        with mock.patch.object(rest.ImportResultModel, "__init__", lambda x: None):
            model = rest.ImportResultModel()
            self.assertEqual(model.get_hide_import_preview(import_result), False)

    def test_get_hide_import_preview_system_attr(self):
        tasks = mock.MagicMock(added=[], deleted=[])
        import_result = mock.MagicMock(tasks=tasks, only_system_attributes=[False])
        with mock.patch.object(rest.ImportResultModel, "__init__", lambda x: None):
            model = rest.ImportResultModel()
            self.assertEqual(model.get_hide_import_preview(import_result), False)

    @mock.patch.object(rest.ImportResultModel, "get_hide_import_preview")
    @mock.patch.object(rest.ImportResultModel, "jsonable_dict")
    @mock.patch.object(rest, "get_and_check_object")
    def test_get_result(
        self, get_and_check_object, jsonable_dict, get_hide_import_preview
    ):
        get_hide_import_preview.return_value = False
        jsonable_dict.side_effect = lambda x, y=None: x
        tasks = mock.MagicMock(
            all={"a": "A", "b": "B"}, added=["b"], excepted=[], modified=["a"]
        )
        import_result = mock.MagicMock(
            project=mock.MagicMock(exceptions=[], diff_type="modified"),
            tasks=tasks,
            num_old_tasks=1,
        )

        XML_IMPORT_CLASS = mock.MagicMock()
        XML_IMPORT_CLASS.import_project_from_xml.return_value = import_result

        def mocked_get_and_check_obj(_type, *args, **kwargs):
            if _type is rest.Project:
                return mock.MagicMock(
                    cdb_project_id="A", XML_IMPORT_CLASS=XML_IMPORT_CLASS
                )
            elif _type is rest.Document:
                return mock.MagicMock(z_nummer="D1", z_index="")

        extra_parameters = {"cdb_project_id": "A", "z_nummer": "D1"}

        get_and_check_object.side_effect = mocked_get_and_check_obj
        model = rest.ImportResultModel(extra_parameters)
        self.assertDictEqual(
            model.get_result(None, True),
            {
                "project": import_result.project,
                "tasks": list(tasks.all.values()),
                "info": {
                    "dryRun": 1,
                    "exceptedPercentage": 0.0,
                    "exceptedCount": 0,
                    "deletedPercentage": 0.0,
                    "deletedCount": 0,
                    "addedPercentage": 100.0 / 3,
                    "addedCount": 1,
                    "modifiedPercentage": 2 * 100.0 / 3,
                    "modifiedCount": 2,
                    "hideImportPreview": False,
                },
            },
        )


if __name__ == "__main__":
    unittest.main()
