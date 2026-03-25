#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import mock
import pytest
from cdb import sqlapi, testcase
from cdb.constants import kOperationNew
from cdb.validationkit import operation

from cs.pcs.projects import Project
from cs.pcs.projects.common.webdata.models import subject_thumbnails

COMMON_ROLE_ICON = "/resources/icons/byname/cdb_role?"
PCS_ROLE_ICON_PATTERN = (
    "/resources/icons/byname/cdbpcs_role?team_needed={}&team_assigned={}"
)
PERSON_ICON_PATTERN = "/api/v1/collection/person/caddok/files/{}"


def pcs_role_icon(needed, assigned):
    return PCS_ROLE_ICON_PATTERN.format(needed, assigned)


def person_icon(oid):
    return PERSON_ICON_PATTERN.format(oid)


@pytest.mark.dependency(name="integration", depends=["cs.pcs.projects"])
class SubjectThumbnailIntegration(testcase.RollbackTestCase):
    PROJECT_ID = "INTEGR_TEST"
    SUBJECTS = [
        # (subject_id, subject_type, expected response)
        (
            "Administrator",
            "Common Role",
            (COMMON_ROLE_ICON, "Allgemeine Rolle Administrator"),
        ),
        ("Projektleiter", "PCS Role", (pcs_role_icon(2, 1), "Projektleiter")),
        ("Projektmitglied", "PCS Role", None),
        ("A", "PCS Role", (pcs_role_icon(0, 1), "")),
        ("?", "PCS Role", None),
        ("?", "Common Role", None),
        ("?", "Person", None),
    ]

    def _get_data(self, payload):
        model = subject_thumbnails.SubjectThumbnailModel()
        request = mock.MagicMock(
            json=payload,
            application_url="http://host:1234",
        )
        return model.get_data(request)

    @testcase.without_error_logging
    @mock.patch.object(subject_thumbnails.logging, "error")
    def test_get_data_no_payload(self, error):
        with self.assertRaises(subject_thumbnails.HTTPBadRequest):
            with testcase.max_sql(0):
                self._get_data(None)

        error.assert_called_once_with(
            "%s not a dict: %s", "SubjectThumbnailModel", None
        )

    @testcase.without_error_logging
    @mock.patch.object(subject_thumbnails.logging, "error")
    def test_get_data_invalid_url(self, error):
        with self.assertRaises(subject_thumbnails.HTTPBadRequest):
            with testcase.max_sql(0):
                self._get_data({"foo": ["bar"]})

        error.assert_called_once_with(
            "%s invalid REST URLs: %s",
            "SubjectThumbnailModel",
            {"foo": ["bar"]},
        )

    @testcase.without_error_logging
    @mock.patch.object(subject_thumbnails.logging, "error")
    def test_get_data_no_classdef(self, error):
        with self.assertRaises(subject_thumbnails.HTTPBadRequest):
            with testcase.max_sql(0):
                self._get_data({"/foo/bar": [0]})

        error.assert_called_once_with(
            "cannot find class def for %s(%s)",
            subject_thumbnails.util.CDBClassDef.findByRESTName,
            "foo",
        )

    def test_get_data_no_object(self):
        # expect 1 SQL statement:
        # (restnames are cached)
        # 1. resolve project
        with testcase.max_sql(1):
            self.assertEqual(
                self._get_data({"/project/bar@": ["cdb_cpersno"]}),
                {},
            )

    def test_get_data_no_fields(self):
        with testcase.max_sql(0):
            self.assertEqual(
                self._get_data({"/project/bar@": []}),
                {},
            )

    def test_get_data_empty(self):
        with testcase.max_sql(0):
            self.assertEqual(
                self._get_data({}),
                {},
            )

    def _setup_project(self):
        project_id = "TEST_INTGR_THMBNL"
        project = operation(
            kOperationNew,
            Project,
            preset={
                "project_name": "test project",
                "template": 0,
                "cdb_project_id": project_id,
                "ce_baseline_id": "",
                "cdb_cpersno": "caddok",
                "project_manager": "vendorsupport",
            },
            interactive=False,
        )

        project.getRole("Projektleiter").Update(team_assigned=1, team_needed=2)
        role_a = project.createRole("A")
        role_a.Update(team_assigned=1, team_needed=0)
        project.getRole("Projektmitglied").Delete()

        for i, subject in enumerate(self.SUBJECTS):
            sqlapi.Record(
                "cdbpcs_task",
                cdb_project_id=project_id,
                task_id=f"{project_id}-{i}",
                subject_id=subject[0],
                subject_type=subject[1],
                constraint_type=0,
            ).insert()

        return project_id

    @mock.patch.object(subject_thumbnails.User, "GetThumbnailFile", autospec=True)
    def test_get_data(self, GetThumbnailFile):
        caddok_pic_oid = "picture of caddok"

        def mocked_user_thumbnail(self):
            if self.personalnummer == "caddok":
                return mock.MagicMock(cdb_object_id=caddok_pic_oid)
            return None

        project_id = self._setup_project()
        ce_baseline_id = ""
        GetThumbnailFile.side_effect = mocked_user_thumbnail

        base_url = "/api/v1/collection"
        project_url = (
            f"http://host:1234{base_url}/project/{project_id}@{ce_baseline_id}"
        )
        task_pattern = "{0}/project_task/{1}@{1}-{2}@"
        tasks = {
            task_pattern.format(base_url, project_id, index): {
                "subject_id": subject[2],
            }
            for index, subject in enumerate(self.SUBJECTS)
        }

        request = {project_url: ["project_manager", "cdb_cpersno"]}
        request.update({task_url: ["subject_id"] for task_url in tasks})
        response = {
            project_url: {
                "cdb_cpersno": (
                    person_icon(caddok_pic_oid),
                    " Administrator  (caddok)",
                ),
                "project_manager": (None, " Vendorsupport  (vendorsupport)"),
            },
        }
        response.update(
            {f"http://host:1234{rest_id}": task for rest_id, task in tasks.items()}
        )

        self.maxDiff = None
        # warm up caches to filter out unpredictable SQL
        self._get_data(request)
        self.resetSQLCount()

        with testcase.max_sql(5):
            # expect 5 SQL statements:
            # (restnames are cached)
            # 1. resolve project
            # 2. resolve tasks
            # 3. resolve persons
            # 4. resolve common roles
            # 5. resolve project roles
            self.assertCountEqual(self._get_data(request), response)


if __name__ == "__main__":
    unittest.main()
