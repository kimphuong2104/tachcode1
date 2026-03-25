#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=import-error,invalid-name
# flake8: noqa E501; ignore line too long error

"""
Integration tests for project structure
"""

import json
import os
import unittest
from urllib.parse import parse_qs, splitquery

import pytest
from cdb import sig, sqlapi, testcase, transactions

from cs.pcs.projects import Project
from cs.pcs.projects.project_structure import views
from cs.pcs.projects.tasks import Task

PROJECT_ID = "INTEGR_TEST_{}"
CALENDAR = "1cb4cf41-0f40-11df-a6f9-9435b380e702"
TESTDATA_OIDS = {
    "cdbpcs_project": [],
    "cdbpcs_task": [],
}


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()

    @sig.connect(views.GET_VIEWS)
    def _register_view(register_callback):
        register_callback(views.TreeTableView)

    create_data()


def create_data():
    """
    Project A
        Project B
            Project C
                Task C.1
                    Task C.1.1
            Task B.1
                Task B.1.1
        Project D
            Task D.1
        Task A.1
            Task A.1.1
            Task A.1.2
        Task A.2
    """
    # pylint: disable=global-statement,too-many-locals

    def create_project(pid, parent=None, position=None, msp_active=0):
        """
        Create Test Project with given project id, parent project id
        and position.
        """
        return Project.Create(
            cdb_object_id=pid,
            parent_project=(PROJECT_ID.format(parent) if parent else ""),
            cdb_project_id=PROJECT_ID.format(pid),
            ce_baseline_id="",
            project_name=PROJECT_ID.format(pid),
            calendar_profile_id=CALENDAR,
            status=0,
            position=position,
            cdb_objektart="cdbpcs_project",
            msp_active=msp_active,
        )

    def create_task(proj, tid, position, parent=None, milestone=None):
        """
        Create Test Task with given project id, task id, position and
        parent task id.
        """
        return Task.Create(
            cdb_object_id=tid,
            cdb_project_id=proj.cdb_project_id,
            ce_baseline_id=proj.ce_baseline_id,
            task_id=tid,
            parent_task=(parent.task_id if parent else ""),
            position=position,
            task_name=f"Task {tid}",
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            status=0,
            cdb_objektart="cdbpcs_task",
            milestone=milestone,
        )

    with transactions.Transaction():
        proj_a = create_project("A")
        # position of Null is treated as 0 for determining order in project structure
        proj_b = create_project("B", "A")
        proj_c = create_project("C", "B")
        proj_d = create_project("D", "A", 20, 1)

        task_a1 = create_task(proj_a, "A.1", 0)
        task_a11 = create_task(proj_a, "A.1.1", 10, task_a1)
        task_a12 = create_task(proj_a, "A.1.2", 20, task_a1)
        task_a2 = create_task(proj_a, "A.2", 20, None, 1)

        task_b1 = create_task(proj_b, "B.1", 10)
        task_b11 = create_task(proj_b, "B.1.1", 10, task_b1)

        task_c1 = create_task(proj_c, "C.1", 10)
        task_c11 = create_task(proj_c, "C.1.1", 10, task_c1)

        task_d1 = create_task(proj_d, "D.1", 10)

        TESTDATA_OIDS["cdbpcs_project"] = [
            proj_a.cdb_object_id,
            proj_b.cdb_object_id,
            proj_c.cdb_object_id,
            proj_d.cdb_object_id,
        ]
        TESTDATA_OIDS["cdbpcs_task"] = [
            task_a1.cdb_object_id,
            task_a11.cdb_object_id,
            task_a12.cdb_object_id,
            task_a2.cdb_object_id,
            task_b1.cdb_object_id,
            task_b11.cdb_object_id,
            task_c1.cdb_object_id,
            task_c11.cdb_object_id,
            task_d1.cdb_object_id,
        ]
        # cdb_object contents are spotty (A, B missing, C, D exist)
        # when simply running `nosetests` (they all exist when debugging)
        # so repair it explicitly here
        from cdb import util

        util.ObjectDictionary.repair("cdbpcs_project")


def tearDownModule():
    """
    clear testdata
    """
    for table, oids in TESTDATA_OIDS.items():
        condition = "', '".join(oids)
        sqlapi.SQLdelete(f"FROM {table} WHERE cdb_object_id IN ('{condition}')")
        sqlapi.SQLdelete(f"FROM cdb_object WHERE id IN ('{condition}')")


def load_json(filename):
    """
    Load json from file with given filename.
    """
    filepath = os.path.join(
        os.path.abspath(os.path.dirname(__file__)),
        "testdata",
        filename,
    )
    with open(filepath, "r", encoding="utf8") as testdata:
        return json.load(testdata)


def replace_url(val_str):
    """
    test utility

    if val_str is a url, split it up into path and query
    to make queries comparable independent of sorting
    """
    path, query = splitquery(val_str)
    if query:
        result = {
            "path": path,
            "query": parse_qs(query),
        }
    else:
        result = val_str
    return result


def _replace_urls(nested_value):
    """
    test utility

    recursively replace urls in nested_value (see `replace_url`)
    """
    if isinstance(nested_value, dict):
        result = replace_urls(nested_value)
    elif isinstance(nested_value, list):
        result = [_replace_urls(x) for x in nested_value]
    elif isinstance(nested_value, str):
        result = replace_url(nested_value)
    else:
        result = nested_value
    return result


def replace_urls(dict_value):
    """
    test utility

    recursively replace urls in dict_value (see `replace_url`)
    """
    result = {}
    for k, v in dict_value.items():
        result[k] = _replace_urls(v)
    return result


def _request(params, full_data):
    """
    test utility

    sends request to mock http server
    """
    # set up mock http server
    # pylint: disable=no-name-in-module
    from cs.platform.web.root import Root
    from webtest import TestApp as Client

    view = params.get("view", "project_structure") if params else "project_structure"
    client = Client(Root())
    # cdb_project_id, ce_baseline_id
    project_ids = f"{PROJECT_ID.format('A')}@"
    url = f"/internal/structure_tree/{view}/{project_ids}"
    if full_data:
        url = f"{url}/+full"
        response = client.post_json(url, params)
    else:
        response = client.get(url, params)
    return response


# TODO Adjust test for ce_baseline_id


@pytest.mark.dependency(name="integration", depends=["cs.pcs.projects"])
class ProjectStructureIntegration(testcase.RollbackTestCase):
    """
    Class for Project Structure Integration Tests.
    """

    # SQL statements for resolving with subprojects:
    # 1. full data of root project (existence and read access check)
    # 2. subprojects of A
    # 3. task structure of A
    # 4. task structure of B
    # 5. task structure of C
    # 6. task structure of D
    # 7. full data of projects
    # 8. full data of tasks
    # without subprojects, 2, 4, 5 and 6 aren't used
    SQL_STMTS_NO_SUBPROJECTS = 4
    SQL_STMTS_SUBPROJECTS = 8

    def assert_response_equal(self, response, expected):
        """
        asserts if response and expected are equal
        """
        # set maxDiff to none to show full error message, when assertion fails
        self.maxDiff = None  # pylint: disable=attribute-defined-outside-init
        result = replace_urls(response.json)

        self.assertDictEqual(result, expected)

    def _simulate_request(self, params, expected_json, expected_stmts, full_data=False):
        response = _request(params, full_data)
        self.assert_response_equal(response, expected_json)

        # now that caches are warm, check amount of SQL stmts
        # to log stmt, uncomment the following two lines:

        # from cdb import misc
        # misc.cdblog_reinit("SQL:log:lev=0")

        with testcase.max_sql(expected_stmts):
            _request(params, full_data)

    def test_simulate_request_no_params(self):
        "resolves structure without explicit params"
        expected = load_json("simulate_request_00.json")
        self._simulate_request(
            None,
            expected,
            self.SQL_STMTS_NO_SUBPROJECTS,
        )

    def test_simulate_request_00(self):
        "resolves task structure for tree (00)"
        expected = load_json("simulate_request_00.json")
        self._simulate_request(
            {"subprojects": 0},
            expected,
            self.SQL_STMTS_NO_SUBPROJECTS,
        )

    def test_simulate_request_10(self):
        "resolves full structure for tree (10)"
        expected = load_json("simulate_request_10.json")
        self._simulate_request(
            {"subprojects": 1},
            expected,
            self.SQL_STMTS_SUBPROJECTS,
        )

    def test_simulate_request_01(self):
        "resolves task structure for table (01)"
        expected = load_json("simulate_request_01.json")
        # requires "tree_table" view
        self._simulate_request(
            {"subprojects": 0, "view": "tree_table"},
            expected,
            self.SQL_STMTS_NO_SUBPROJECTS,
        )

    def test_simulate_request_11(self):
        "resolves full structure for table (11)"
        expected = load_json("simulate_request_11.json")
        # requires "tree_table" view
        self._simulate_request(
            {"subprojects": 1, "view": "tree_table"},
            expected,
            self.SQL_STMTS_SUBPROJECTS,
        )

    def test_get_full_data_no_oids(self):
        "returns full data for 0 objects"
        self._simulate_request(
            {"objectIDs": []},
            {},
            1,  # SQL: select project
            True,
        )

    def test_get_full_data_oids_missing(self):
        "fails if objectIDs is missing"
        with self.assertRaises(KeyError) as error:
            with testcase.error_logging_disabled():
                self._simulate_request(
                    {},
                    {},
                    0,  # no SQL
                    True,
                )

        self.assertEqual(str(error.exception), "'objectIDs'")

    def test_get_full_data_3(self):
        "returns full data of 1 project and 2 tasks"
        expected = load_json("full_data_3.json")
        self._simulate_request(
            {
                "objectIDs": [
                    "A",
                    "A.1.1",
                    "A.1.2",
                    "unknown",
                ],
            },
            expected,
            4,  # SQL: select project, cdb_object, task data, project data
            True,
        )


if __name__ == "__main__":
    unittest.main()
