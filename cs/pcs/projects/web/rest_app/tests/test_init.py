#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


import unittest

import mock
import pytest
from cdb import testcase
from webob.exc import HTTPBadRequest

from cs.pcs.projects.web import rest_app


@pytest.mark.unit
class UtilityTestCase(testcase.RollbackTestCase):
    @mock.patch.object(rest_app, "get_url_patterns")
    @mock.patch.object(rest_app.ProjectsApp, "get_app")
    def test_get_app_url_patterns(self, get_app, get_url_patterns):
        self.assertEqual(
            rest_app.get_app_url_patterns("request"),
            get_url_patterns.return_value,
        )
        get_app.assert_called_once_with("request")
        get_url_patterns.assert_called_once_with(
            "request",
            get_app.return_value,
            [
                ("kpis", rest_app.ProjectKPIsModel, []),
                ("relshiplists", rest_app.RelshipListsModel, []),
            ],
        )


@pytest.mark.unit
class RelshipListsModelTestCase(testcase.RollbackTestCase):
    @mock.patch.object(rest_app.logging, "exception")
    def test_get_relship_list_no_keys(self, exception):
        "1) no keys at all"
        mock_request = mock.Mock(json={})
        with self.assertRaises(HTTPBadRequest):
            rest_app.RelshipListsModel().get_relship_list(mock_request)

        exception.assert_called_once_with(
            "get_relship_list, request: %s",
            mock_request,
        )

    @mock.patch.object(rest_app.logging, "exception")
    def test_get_relship_list_no_relship(self, exception):
        "2) no relship"
        mock_request = mock.Mock(
            json={
                "restKey": "restKey",
                "classname": "classname",
            }
        )
        with self.assertRaises(HTTPBadRequest):
            rest_app.RelshipListsModel().get_relship_list(mock_request)

        exception.assert_called_once_with("get_relship_list, request: %s", mock_request)

    @mock.patch.object(rest_app.logging, "exception")
    def test_get_relship_list_no_rest_key(self, exception):
        "3) no restkey"
        mock_request = mock.Mock(
            json={
                "relshipName": "relshipName",
                "classname": "classname",
            }
        )
        with self.assertRaises(HTTPBadRequest):
            rest_app.RelshipListsModel().get_relship_list(mock_request)

        exception.assert_called_once_with("get_relship_list, request: %s", mock_request)

    @mock.patch.object(rest_app.logging, "exception")
    def test_get_relship_list_no_classname(self, exception):
        "4) no classname"
        mock_request = mock.Mock(
            json={
                "relshipName": "relshipName",
                "restKey": "restKey",
            }
        )
        with self.assertRaises(HTTPBadRequest):
            rest_app.RelshipListsModel().get_relship_list(mock_request)

        exception.assert_called_once_with("get_relship_list, request: %s", mock_request)

    @mock.patch.object(rest_app.ListDataProvider, "KeywordQuery")
    def test_get_relship_list(self, KeywordQuery):
        mock_request = mock.Mock(
            json={
                "classname": "foo",
                "relshipName": "bar",
                "restKey": "baz",
            }
        )
        mock_provider_config = mock.Mock(generateListJSON=mock.Mock())
        KeywordQuery.return_value = [mock_provider_config]

        self.assertEqual(
            rest_app.RelshipListsModel().get_relship_list(mock_request),
            mock_provider_config.generateListJSON.return_value,
        )
        KeywordQuery.assert_called_once_with(rolename="bar", referer="foo")
        mock_provider_config.generateListJSON.assert_called_once_with(
            mock_request, "baz"
        )

    @mock.patch.object(
        rest_app.util, "get_label", side_effect=["foo_title", "foo_error: {} {}"]
    )
    @mock.patch.object(rest_app, "auth")
    @mock.patch.object(rest_app.logging, "exception")
    @mock.patch.object(rest_app.ListDataProvider, "KeywordQuery")
    def test_get_relship_list_no_access_granted(
        self,
        KeywordQuery,
        exception,
        auth,
        get_label,
    ):
        # this testcase handles
        # a) no list_config with given name found
        # b) no read access granted on requested list_config name
        mock_request = mock.Mock(
            json={
                "classname": "foo",
                "relshipName": "bar",
                "restKey": "baz",
            }
        )
        mock_provider_config = mock.Mock(generateListJSON=mock.Mock())
        mock_provider_config.CheckAccess.return_value = False
        KeywordQuery.return_value = [mock_provider_config]

        self.assertDictEqual(
            rest_app.RelshipListsModel().get_relship_list(mock_request),
            {
                "title": "foo_title",
                "items": [],
                "displayConfigs": {},
                "configError": "foo_error: bar foo",
            },
        )
        KeywordQuery.assert_called_once_with(rolename="bar", referer="foo")
        exception.assert_called_once_with(
            """
                RelshipListsModel: '%s' has no read access on ListDataProvider
                with rolename '%s' and referer '%s' or ListDataProvider does
                not exist.
                """,
            auth.persno,
            "bar",
            "foo",
        )
        mock_provider_config.generateListJSON.assert_not_called()
        mock_provider_config.CheckAccess.assert_called_once_with("read")
        get_label.assert_has_calls(
            [
                mock.call("web.cs-pcs-projects.relship_list_error_title"),
                mock.call("cs.pcs.projects.common.lists.provider_access_error"),
            ]
        )


@pytest.mark.unit
class ProjectKPIsModelTestCase(testcase.RollbackTestCase):
    @mock.patch.object(rest_app.logging, "exception")
    def test_get_kpis_missing_payload_key(self, exception):
        mock_request = mock.Mock(json={})

        with self.assertRaises(HTTPBadRequest):
            rest_app.ProjectKPIsModel().get_kpis(mock_request)

        exception.assert_called_once_with(
            "get_kpis, request: %s",
            mock_request,
        )

    @mock.patch.object(
        rest_app,
        "get_and_check_object",
        return_value=mock.MagicMock(
            success_threshold=0.7,
            danger_threshold=0.85,
        ),
    )
    @mock.patch.object(rest_app, "get_objects_from_rest_keys")
    @mock.patch.object(rest_app, "rest_key", return_value="foo@")
    def test_get_kpis_all_thresholds(
        self, rest_key, get_objects_from_rest_keys, get_and_check_object
    ):
        mock_request = mock.Mock(json={"projects": ["foo"]})
        project = mock.MagicMock(
            autospec=rest_app.Project,
            cdb_project_id="foo",
        )
        project.get_ev_pv_for_project.return_value = (1.0, 1.0)
        project.get_cost_state.return_value = [None, None, 2.0, 1.0]
        project.get_schedule_state.return_value = [None, None, 2.0, 1.0]
        project.PrimaryTimeSchedule.KeywordQuery.return_value = []
        get_objects_from_rest_keys.return_value = [project]
        result = rest_app.ProjectKPIsModel().get_kpis(mock_request)
        expected_result = {
            "foo@": {
                "cpi": 1.0,
                "cpi_threshold": [0.7, 0.85],
                "cpi_variance": 2.0,
                "spi": 1.0,
                "spi_variance": 2.0,
                "spi_threshold": [0.7, 0.85],
                "timeschedules": {},
            }
        }
        self.assertEqual(result, expected_result)
        get_and_check_object.assert_has_calls(
            [
                mock.call(rest_app.DefaultKPIsThreshold, "read", kpi_name="CPI"),
                mock.call(rest_app.DefaultKPIsThreshold, "read", kpi_name="SPI"),
            ]
        )

    @mock.patch.object(rest_app, "get_and_check_object", return_value=None)
    @mock.patch.object(rest_app, "get_objects_from_rest_keys")
    @mock.patch.object(rest_app, "rest_key", return_value="foo@")
    def test_get_kpis_no_thresholds(self, rest_key, get_objects_from_rest_keys, _):
        mock_request = mock.Mock(json={"projects": ["foo"]})
        project = mock.MagicMock(
            autospec=rest_app.Project,
            cdb_project_id="foo",
        )
        project.get_ev_pv_for_project.return_value = (1.0, 1.0)
        project.get_cost_state.return_value = [None, None, 2.0, 1.0]
        project.get_schedule_state.return_value = [None, None, 2.0, 1.0]
        get_objects_from_rest_keys.return_value = [project]
        # Note: Returning no Thresholds covers
        #   a) no thresholds defined
        #   b) no access granted on thresholds
        result = rest_app.ProjectKPIsModel().get_kpis(mock_request)
        expected_result = {
            "foo@": {
                "cpi": 1.0,
                "cpi_variance": 2.0,
                "spi": 1.0,
                "spi_variance": 2.0,
                "timeschedules": {},
            }
        }
        self.assertEqual(result, expected_result)

    @mock.patch.object(
        rest_app.DefaultKPIsThreshold,
        "ByKeys",
        return_value=mock.MagicMock(
            success_threshold=0.7,
            danger_threshold=0.85,
        ),
    )
    @mock.patch.object(rest_app, "get_objects_from_rest_keys")
    @mock.patch.object(rest_app, "rest_key", return_value="foo@")
    def test_get_kpis_with_timeschedule(self, rest_key, get_objects_from_rest_keys, _):
        mock_request = mock.Mock(json={"projects": ["foo"]})
        project = mock.MagicMock(
            autospec=rest_app.Project,
            cdb_project_id="foo",
        )
        project.get_ev_pv_for_project.return_value = (1.0, 1.0)
        project.get_cost_state.return_value = [None, None, 2.0, 1.0]
        project.get_schedule_state.return_value = [None, None, 2.0, 1.0]
        timeschedule = mock.MagicMock(cdb_status_txt="baz")
        timeschedule.name = "bar"  # not working in constructor
        timeschedule.getProjectPlanURL.return_value = "testurl"
        project.PrimaryTimeSchedule.KeywordQuery.return_value = [timeschedule]
        get_objects_from_rest_keys.return_value = [project]
        result = rest_app.ProjectKPIsModel().get_kpis(mock_request)
        expected_result = {
            "foo@": {
                "cpi": 1.0,
                "cpi_threshold": [0.7, 0.85],
                "cpi_variance": 2.0,
                "spi": 1.0,
                "spi_threshold": [0.7, 0.85],
                "spi_variance": 2.0,
                "timeschedules": {"testurl": {"name": "bar", "status": "baz"}},
            }
        }
        self.assertEqual(result, expected_result)

    @mock.patch.object(rest_app, "get_and_check_object", return_value=None)
    @mock.patch.object(rest_app.Project, "KeywordQuery")
    def test_get_kpis_no_access_on_project(self, KeywordQuery, get_and_check_object):
        mock_request = mock.Mock(json={"projects": ["foo@"]})
        project = mock.MagicMock(
            autospec=rest_app.Project,
            cdb_project_id="foo",
            ce_baseline_id="",
        )
        project.CheckAccess.return_value = False
        KeywordQuery.return_value = [project]

        result = rest_app.ProjectKPIsModel().get_kpis(mock_request)
        self.assertEqual(result, {})

        project.get_ev_pv_for_project.assert_not_called()
        project.get_cost_state.assert_not_called()
        project.get_schedule_state.assert_not_called()
        get_and_check_object.assert_has_calls(
            [
                mock.call(rest_app.DefaultKPIsThreshold, "read", kpi_name="CPI"),
                mock.call(rest_app.DefaultKPIsThreshold, "read", kpi_name="SPI"),
            ]
        )


if __name__ == "__main__":
    unittest.main()
