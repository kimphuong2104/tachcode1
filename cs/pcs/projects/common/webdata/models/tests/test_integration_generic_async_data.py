#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import os
import unittest

import pytest
from cdb import testcase

from cs.pcs.projects.common.webdata.models import generic_async_data


@pytest.mark.dependency(name="integration", depends=["cs.pcs.projects"])
class GenericAsyncDataIntegration(testcase.RollbackTestCase):
    PROJECT_ID = "INTEGR_TEST"
    BASELINE_ID = ""

    @classmethod
    def _setup_data(cls):
        from datetime import datetime

        from cs.pcs.projects import Project
        from cs.pcs.projects.tasks import Task

        proj = Project.Create(
            cdb_project_id=cls.PROJECT_ID,
            ce_baseline_id=cls.BASELINE_ID,
            calendar_profile_id="Calendar",
        )
        Task.Create(
            cdb_cdate=datetime(2020, 8, 2),
            cdb_project_id=proj.cdb_project_id,
            ce_baseline_id=proj.ce_baseline_id,
            task_id="T1",
            task_name="Task One",
            subject_id="Projektmitglied",
            subject_type="PCS Role",
        )
        text_task = Task.Create(
            cdb_cdate=datetime(2020, 8, 3),
            cdb_project_id=proj.cdb_project_id,
            ce_baseline_id=proj.ce_baseline_id,
            task_id="T2",
            task_name="Task Two",
            subject_id="",
            subject_type="",
        )

        # read example long text from text file
        # and apply it to task
        textpath = os.path.join(os.path.dirname(__file__), "cdbpcs_task_txt.txt")

        with open(textpath, "r", encoding="utf8") as textfile:
            long_text = textfile.read()

        text_task.SetText("cdbpcs_task_txt", long_text)

        cls.long_text = long_text

    def setUp(self):
        super().setUp()
        self._setup_data()

    def _get_data(self):
        return generic_async_data.sqlapi.RecordSet2(
            "cdbpcs_task",
            f"cdb_project_id='{self.PROJECT_ID}'",
        )

    @testcase.without_error_logging
    def test_get_fields_unknown(self):
        "fails for unknown field"
        data = self._get_data()
        model = generic_async_data.GenericAsyncDataModel()
        model._resolve_class("cdbpcs_task")
        with self.assertRaises(AttributeError):
            model.get_fields("cdbpcs_task", data, ["foo"])

    def test_get_fields(self):
        "returns native attributes"
        model = generic_async_data.GenericAsyncDataModel()
        model._resolve_class("cdbpcs_task")
        data = self._get_data()
        self.maxDiff = None
        self.assertEqual(
            model.get_fields(
                "cdbpcs_task", data, ["subject_id", "subject_type", "cdb_cdate"]
            ),
            {
                "INTEGR_TEST@T1@": {
                    "subject_id": "Projektmitglied",
                    "subject_type": "PCS Role",
                    "cdb_cdate": "2020-08-02T00:00:00",
                },
                "INTEGR_TEST@T2@": {
                    "subject_id": "",
                    "subject_type": "",
                    "cdb_cdate": "2020-08-03T00:00:00",
                },
            },
        )

    @testcase.without_error_logging
    def test_get_mapped_unknown(self):
        "fails for unknown mapped attribute"
        model = generic_async_data.GenericAsyncDataModel()
        model._resolve_class("cdbpcs_task")
        data = self._get_data()
        with self.assertRaises(generic_async_data.HTTPBadRequest):
            model.get_mapped("cdbpcs_task", data, ["foo"])

    def test_get_mapped(self):
        "returns mapped attributes"
        model = generic_async_data.GenericAsyncDataModel()
        model._resolve_class("cdbpcs_task")
        data = self._get_data()
        mapped = [
            "mapped_subject_name_en",
            "mapped_calendar_profile_id",
        ]
        self.assertEqual(
            model.get_mapped("cdbpcs_task", data, mapped),
            {
                "INTEGR_TEST@T1@": {
                    "mapped_calendar_profile_id": "Calendar",
                    "mapped_subject_name_en": "Project Member",
                },
                "INTEGR_TEST@T2@": {
                    "mapped_calendar_profile_id": "Calendar",
                    "mapped_subject_name_en": "",
                },
            },
        )

    @testcase.without_error_logging
    def test_get_texts_unknown(self):
        "fails for unknown long text"
        model = generic_async_data.GenericAsyncDataModel()
        model._resolve_class("cdbpcs_task")
        data = self._get_data()
        with self.assertRaises(generic_async_data.HTTPBadRequest):
            model.get_texts("cdbpcs_task", data, ["foo"])

    def test_get_texts(self):
        "returns long texts"
        model = generic_async_data.GenericAsyncDataModel()
        model._resolve_class("cdbpcs_task")
        data = self._get_data()
        self.assertEqual(
            model.get_texts("cdbpcs_task", data, ["cdbpcs_task_txt"]),
            {
                "INTEGR_TEST@T2@": {
                    "cdbpcs_task_txt": self.long_text,
                },
            },
        )

    def test_simulate_request(self):
        "simulated request returns full data"

        # set up mock http server
        from cs.platform.web.root import Root
        from webtest import TestApp as Client

        client = Client(Root())

        url = "/internal/cs-pcs-webdata/object_data"
        requested_data = {
            "cdbpcs_task": {
                "keys": [
                    "INTEGR_TEST@T1@",
                    "INTEGR_TEST@T2@",
                ],
                "fields": [
                    "subject_id",
                    "subject_type",
                    "cdb_cdate",
                ],
                "mapped": [
                    "mapped_subject_name_de",
                    "mapped_subject_name_en",
                ],
                "texts": ["cdbpcs_task_txt"],
            },
        }
        response = client.post_json(url, requested_data)
        self.maxDiff = None
        self.assertEqual(
            response.json,
            {
                "cdbpcs_task": {
                    "INTEGR_TEST@T1@": {
                        "mapped_subject_name_de": "Projektmitglied",
                        "mapped_subject_name_en": "Project Member",
                        "subject_id": "Projektmitglied",
                        "subject_type": "PCS Role",
                        "cdb_cdate": "2020-08-02T00:00:00",
                    },
                    "INTEGR_TEST@T2@": {
                        "mapped_subject_name_de": "",
                        "mapped_subject_name_en": "",
                        "subject_id": "",
                        "subject_type": "",
                        "cdb_cdate": "2020-08-03T00:00:00",
                        "cdbpcs_task_txt": self.long_text,
                    },
                },
            },
        )

        # now that caches are warm, check amount of SQL stmts
        # 1. select task data from cdbpcs_task
        # 2. select long text data from cdbpcs_task_txt
        with testcase.max_sql(2):
            client.post_json(url, requested_data)


if __name__ == "__main__":
    unittest.main()
