#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import datetime
import unittest

import mock
import pytest
from cdb import testcase

from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task
from cs.pcs.projects.web.rest_app import milestones


@pytest.mark.unit
class UtilityTestCase(unittest.TestCase):
    @mock.patch.object(milestones.MilestonesApp, "get_app")
    @mock.patch.object(milestones, "get_url_patterns")
    def test_get_app_url_patterns(self, get_url_patterns, get_app):
        self.assertEqual(
            milestones.get_app_url_patterns("request"),
            get_url_patterns.return_value,
        )
        get_url_patterns.assert_called_once_with(
            "request",
            get_app.return_value,
            [("milestones", milestones.MilestonesModel, [])],
        )
        get_app.assert_called_once_with("request")

    @mock.patch.object(milestones.MilestonesApp, "__new__", autospec=True)
    def test__mount_app(self, MilestoneApp__new__):
        self.assertEqual(milestones._mount_app(), MilestoneApp__new__.return_value)
        MilestoneApp__new__.assert_called_once_with(milestones.MilestonesApp)

    def test_ensure_iso_date_empty(self):
        results = [milestones.ensure_iso_date(value) for value in [None, "", 0]]
        self.assertEqual(
            results,
            [None, None, None],
        )

    @mock.patch.object(
        milestones.sqlapi, "SQLdbms", return_value=milestones.sqlapi.DBMS_SQLITE
    )
    def test_ensure_iso_date_sqlite_no_str(self, _):
        with self.assertRaises(ValueError) as error:
            milestones.ensure_iso_date(20220805)

        self.assertEqual(
            str(error.exception),
            "not an ISO 8601 date string: 20220805 (<class 'int'>)",
        )

    @mock.patch.object(
        milestones.sqlapi, "SQLdbms", return_value=milestones.sqlapi.DBMS_SQLITE
    )
    def test_ensure_iso_date_sqlite_no_iso(self, _):
        with self.assertRaises(ValueError) as error:
            milestones.ensure_iso_date("foo")

        self.assertEqual(
            str(error.exception),
            "not an ISO 8601 date string: foo (<class 'str'>)",
        )

    @mock.patch.object(
        milestones.sqlapi, "SQLdbms", return_value=milestones.sqlapi.DBMS_SQLITE
    )
    def test_ensure_iso_date_sqlite_datetime_ok(self, _):
        self.assertEqual(
            milestones.ensure_iso_date("2022-08-05T01:02:03"),
            "2022-08-05",
        )

    @mock.patch.object(
        milestones.sqlapi, "SQLdbms", return_value=milestones.sqlapi.DBMS_SQLITE
    )
    def test_ensure_iso_date_sqlite_date_ok(self, _):
        self.assertEqual(
            milestones.ensure_iso_date("2022-08-05"),
            "2022-08-05",
        )

    @mock.patch.object(milestones.sqlapi, "SQLdbms", return_value="foo")
    def test_ensure_iso_date_other_dbms_no_datetime(self, _):
        with self.assertRaises(ValueError) as error:
            milestones.ensure_iso_date("2022-08-05")

        self.assertEqual(
            str(error.exception),
            "not a datetime object: 2022-08-05 (<class 'str'>)",
        )

    @mock.patch.object(milestones.sqlapi, "SQLdbms", return_value="foo")
    def test_ensure_iso_date_other_dbms_ok(self, _):
        self.assertEqual(
            milestones.ensure_iso_date(datetime.datetime(2022, 8, 5, 1, 2, 3)),
            "2022-08-05",
        )


@pytest.mark.unit
class MilestonesApp(unittest.TestCase):
    @mock.patch.object(milestones, "APP", "APP")
    @mock.patch.object(milestones, "get_internal")
    def test_get_app(self, get_internal):
        self.assertEqual(
            milestones.MilestonesApp.get_app(None),
            get_internal.return_value.child.return_value,
        )
        get_internal.assert_called_once_with(None)
        get_internal.return_value.child.assert_called_once_with("APP")

    @mock.patch.object(milestones.MilestonesModel, "__new__", autospec=True)
    def test_get_milestones_model(self, milestonesModel__new__):
        self.assertEqual(
            milestones.get_milestones_model("request"),
            milestonesModel__new__.return_value,
        )
        milestonesModel__new__.assert_called_once_with(milestones.MilestonesModel)

    def test_get_milestones_for_projects(self):
        model = mock.MagicMock(spec=milestones.MilestonesModel)
        self.assertEqual(
            milestones.get_milestones_for_projects(model, "request"),
            model.get_milestones.return_value,
        )
        model.get_milestones.assert_called_once_with("request")


@pytest.mark.unit
class MilestonesModel(unittest.TestCase):
    @mock.patch.object(milestones, "get_restlink", return_value="restlink")
    def test__getTaskValues(self, get_restlink):
        model = mock.MagicMock(spec=milestones.MilestonesModel)
        mock_task = mock.MagicMock(spec=Task)
        value_dict = {
            "task_name": "bar",
            "mapped_subject_name": "baz",
            "joined_status_name": "bam",
            "resp_thumbnail": "thumb",
            # Cannot mock datetime.dateime.strftime
            "end_time_fcast": "foo",
        }

        # method for get item of dict
        def getitem(name):
            return value_dict[name]

        mock_task.__getitem__.side_effect = getitem

        model.getTaskStatusInfo.return_value = 0
        model.getResponsibleThumbnail.return_value = "thumb"
        self.assertEqual(
            milestones.MilestonesModel._getTaskValues(model, mock_task),
            {
                "status": 0,
                "task_name": "bar",
                "mapped_subject_name": "baz",
                "joined_status_name": "bam",
                "@id": "restlink",
                "resp_thumbnail": "thumb",
                "end_time_fcast": mock_task.end_time_fcast.strftime.return_value,
            },
        )
        get_restlink.assert_called_once_with(mock_task)
        mock_task.end_time_fcast.strftime.assert_called_once()

    @mock.patch.object(Task, "Query")
    def test_get_milestones(self, task_query):
        model = mock.MagicMock(spec=milestones.MilestonesModel)
        model._getTaskValues.return_value = "baz"
        mock_request = mock.Mock(json={"projects": ["foo@2", "bar@1"]})
        mock_task_foo = mock.MagicMock(spec=Task)
        mock_task_foo.__getitem__.side_effect = lambda key: {
            "cdb_project_id": "foo",
            "ce_baseline_id": "2",
        }[key]
        mock_task_bar = mock.MagicMock(spec=Task)
        mock_task_bar.__getitem__.side_effect = lambda key: {
            "cdb_project_id": "bar",
            "ce_baseline_id": "1",
        }[key]
        task_query.return_value = [mock_task_foo, mock_task_bar]
        self.assertEqual(
            milestones.MilestonesModel.get_milestones(model, mock_request),
            {
                "foo@2": {"data": ["baz"], "tasks_date_range": {}},
                "bar@1": {"data": ["baz"], "tasks_date_range": {}},
            },
        )
        task_query.assert_called_once_with(
            "((cdb_project_id='foo' AND ce_baseline_id='2') "
            "OR (cdb_project_id='bar' AND ce_baseline_id='1')) "
            "AND milestone = 1",
            access="read",
        )
        model._getTaskValues.assert_has_calls(
            [
                mock.call(mock_task_foo),
                mock.call(mock_task_bar),
            ]
        )

    @mock.patch.object(milestones, "auth", persno="foo_user")
    @mock.patch.object(milestones.logging, "warning")
    @mock.patch.object(Task, "Query")
    def test_get_milestones_no_access(self, task_query, warning, auth):
        model = mock.MagicMock(spec=milestones.MilestonesModel)
        model._getTaskValues.return_value = "baz"
        mock_request = mock.Mock(json={"projects": ["foo@1", "bar@2"]})
        # Note: since Query is checking access directly, we just pretend, that
        # access was not granted and therefore the result is empty
        task_query.return_value = []

        result = milestones.MilestonesModel.get_milestones(model, mock_request)
        self.assertDictEqual(
            result,
            {
                "bar@2": {"data": [], "tasks_date_range": {}},
                "foo@1": {"data": [], "tasks_date_range": {}},
            },
        )

        task_query.assert_called_once_with(
            "((cdb_project_id='foo' AND ce_baseline_id='1') "
            "OR (cdb_project_id='bar' AND ce_baseline_id='2')) "
            "AND milestone = 1",
            access="read",
        )
        warning.assert_called_once_with(
            "get_milestones: Either '%s' have no read access on"
            + "the tasks of projects '%s' or the tasks do not exist.",
            auth.persno,
            [["foo", "1"], ["bar", "2"]],
        )

    @testcase.without_error_logging
    def test_get_milestones_no_projects_key(self):
        model = mock.MagicMock(spec=milestones.MilestonesModel)
        mock_request = mock.Mock()
        mock_request.json = {}
        with self.assertRaises(milestones.HTTPBadRequest):
            milestones.MilestonesModel.get_milestones(model, mock_request)

    @testcase.without_error_logging
    def test_get_milestones_no_list_of_pids(self):
        model = mock.MagicMock(spec=milestones.MilestonesModel)
        mock_request = mock.Mock()
        mock_request.json = {"projects": None}
        with self.assertRaises(milestones.HTTPBadRequest):
            milestones.MilestonesModel.get_milestones(model, mock_request)


@pytest.mark.integration
class MilestonesIntegration(testcase.RollbackTestCase):
    def _create_project(self, pid, bid):
        return Project.Create(cdb_project_id=pid, ce_baseline_id=bid)

    def _create_task(self, pid, tid, bid, **kwargs):
        return Task.Create(
            cdb_project_id=pid, task_id=tid, ce_baseline_id=bid, **kwargs
        )

    def test_get_milestones(self):
        model = milestones.MilestonesModel()
        request = mock.MagicMock(json={"projects": ["A@1", "B@", "C@"]})
        end_time = datetime.date(2020, 1, 1)
        end_time_later = datetime.date(2020, 6, 30)
        # Create Project with three tasks, but two milestones
        self._create_project("A", "1")
        self._create_project("A", "2")
        self._create_task("A", "1", "1", task_name="1", end_time_fcast=end_time_later)
        self._create_task(
            "A", "2", "1", task_name="2", milestone=1, end_time_fcast=end_time
        )
        self._create_task(
            "A", "3", "1", task_name="3", milestone=1, end_time_fcast=end_time
        )
        self._create_task(
            "A", "4", "1", task_name="4", milestone=1, end_time_fcast=None
        )
        self._create_task(
            "A",
            "6",
            "2",
            task_name="6 (baseline mismatch)",
            milestone=1,
            end_time_fcast=end_time,
        )

        # Create Project with one milestone
        self._create_project("B", "")
        self._create_task(
            "B", "1", "", task_name="1", milestone=1, end_time_fcast=end_time
        )

        # Create Project with no milestones
        self._create_project("C", "")
        self._create_task("C", "1", "", task_name="1")

        # fill caches
        model.get_milestones(request)

        with testcase.max_sql(3):
            # (1) get Tasks
            # (2) check if any tasks where found
            # (3) get limits of projects
            result = model.get_milestones(request)

        self.maxDiff = None
        self.assertDictEqual(
            result,
            {
                "A@1": {
                    "data": [
                        {
                            "@id": "/api/v1/collection/project_task/A@2@1",
                            "end_time_fcast": "2020-01-01",
                            "status": {
                                "status": None,
                                "label": "",
                                "color": None,
                            },
                            "task_name": "2",
                            "resp_thumbnail": "",
                            "joined_status_name": "",
                            "mapped_subject_name": "",
                        },
                        {
                            "@id": "/api/v1/collection/project_task/A@3@1",
                            "end_time_fcast": "2020-01-01",
                            "status": {
                                "status": None,
                                "label": "",
                                "color": None,
                            },
                            "task_name": "3",
                            "resp_thumbnail": "",
                            "joined_status_name": "",
                            "mapped_subject_name": "",
                        },
                    ],
                    "tasks_date_range": {
                        "min": end_time.isoformat(),
                        "max": end_time_later.isoformat(),
                    },
                },
                "B@": {
                    "data": [
                        {
                            "@id": "/api/v1/collection/project_task/B@1@",
                            "end_time_fcast": "2020-01-01",
                            "status": {
                                "status": None,
                                "label": "",
                                "color": None,
                            },
                            "task_name": "1",
                            "resp_thumbnail": "",
                            "joined_status_name": "",
                            "mapped_subject_name": "",
                        },
                    ],
                    "tasks_date_range": {
                        "min": end_time.isoformat(),
                        "max": end_time.isoformat(),
                    },
                },
                "C@": {
                    "data": [],
                    "tasks_date_range": {
                        "min": None,
                        "max": None,
                    },
                },
            },
        )


if __name__ == "__main__":
    unittest.main()
