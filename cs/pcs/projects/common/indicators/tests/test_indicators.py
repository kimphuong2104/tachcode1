#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import mock
import pytest
from cdb import testcase
from webob.exc import HTTPBadRequest

from cs.pcs.projects.common import indicators


@pytest.mark.unit
class IndicatorModelTestCase(testcase.RollbackTestCase):
    @mock.patch("cs.pcs.projects.common.indicators.logging.exception")
    @mock.patch.object(indicators, "ResolveIndicators")
    def test_resolve_indicators_faulty_request(self, ResolveIndicators, exception):
        mock_request = mock.Mock()
        mock_request.json = {}
        with self.assertRaises(HTTPBadRequest):
            indicators.IndicatorModel().resolve_indicators(mock_request)

        ResolveIndicators.assert_not_called()
        exception.assert_called_once_with(
            "IndicatorModel: JSON does not include '%s'", "indicators"
        )

    @mock.patch("cs.pcs.projects.common.indicators.get_classinfo_REST")
    @mock.patch("cs.pcs.projects.common.indicators.get_sql_condition")
    @mock.patch.object(indicators.sqlapi, "RecordSet2")
    @mock.patch.object(indicators, "ResolveIndicators")
    def test_resolve_indicators(
        self, ResolveIndicators, RecordSet2, get_sql_condition, get_classinfo_REST
    ):
        mock_request = mock.Mock()
        mock_request.json = {
            "indicators": "foo",
            "rest_name": "project",
            "keys": ["bar"],
        }
        cldef = mock.MagicMock()
        cldef.getKeyNames.return_value = ["cdb_project_id"]
        get_classinfo_REST.return_value = (cldef, "project")
        get_sql_condition.return_value = "condition"
        RecordSet2.return_value = [{"cdb_project_id": "bar"}]
        ResolveIndicators.return_value = [None, 123]
        self.assertEqual(
            indicators.IndicatorModel().resolve_indicators(mock_request), 123
        )
        get_sql_condition.assert_called_once_with(
            "project", cldef.getKeyNames.return_value, [["bar"]]
        )
        ResolveIndicators.assert_called_once_with("project", [["bar"]], "foo")
        RecordSet2.assert_called_once_with("project", "condition", access="read")

    @mock.patch("cs.pcs.projects.common.indicators.get_classinfo_REST")
    @mock.patch("cs.pcs.projects.common.indicators.get_sql_condition")
    @mock.patch.object(indicators.sqlapi, "RecordSet2")
    @mock.patch("cs.pcs.projects.common.indicators.logging.warning")
    @mock.patch("cs.pcs.projects.common.indicators.auth")
    def test_resolve_indicators_no_access(
        self, auth, warning, RecordSet2, get_sql_condition, get_classinfo_REST
    ):
        mock_request = mock.Mock()
        mock_request.json = {
            "indicators": "foo",
            "rest_name": "project",
            "keys": ["bar"],
        }
        cldef = mock.MagicMock()
        cldef.getKeyNames.return_value = ["cdb_project_id"]
        get_classinfo_REST.return_value = (cldef, "project")
        get_sql_condition.return_value = "condition"
        RecordSet2.return_value = []
        self.assertEqual(
            indicators.IndicatorModel().resolve_indicators(mock_request), {}
        )
        warning.assert_called_once_with(
            "IndicatorModel - Either '%s' has no read access on '%s': '%s'"
            + "or the objects do not exist.",
            auth.persno,
            "project",
            ["bar"],
        )
        get_sql_condition.assert_called_once_with(
            "project", cldef.getKeyNames.return_value, [["bar"]]
        )
        RecordSet2.assert_called_once_with("project", "condition", access="read")

    @mock.patch.object(indicators, "ResolveIndicators")
    def test_resolve_indicators_none(self, ResolveIndicators):
        mock_request = mock.Mock()
        mock_request.json = {"indicators": "foo", "rest_name": "project_task"}
        self.assertEqual(
            indicators.IndicatorModel().resolve_indicators(mock_request), {}
        )
        ResolveIndicators.assert_not_called()


@pytest.mark.unit
class IndicatorOverlayModelTestCase(testcase.RollbackTestCase):
    @mock.patch("cs.pcs.projects.common.indicators.logging")
    def test_get_overlay_missing_payload_key(self, logging):
        mock_request = mock.Mock()
        mock_request.json = {}

        with self.assertRaises(HTTPBadRequest):
            indicators.IndicatorOverlayModel().get_overlay(mock_request)

        logging.exception.assert_called_once_with(
            "get_overlay, request: %s", mock_request
        )

    @mock.patch.object(indicators.ListConfig, "KeywordQuery")
    def test_get_overlay(self, KeywordQuery):
        mock_request = mock.Mock()
        mock_request.json = {
            "list_config_name": "foo",
            "restKey": "bar",
        }
        mock_list_config = mock.Mock()
        mock_list_config.generateListJSON = mock.Mock()
        KeywordQuery.return_value = [mock_list_config]

        self.assertEqual(
            indicators.IndicatorOverlayModel().get_overlay(mock_request),
            mock_list_config.generateListJSON.return_value,
        )
        KeywordQuery.assert_called_once_with(name="foo")
        mock_list_config.generateListJSON.assert_called_once_with(mock_request, "bar")

    @mock.patch(
        "cs.pcs.projects.common.indicators.util.get_label",
        side_effect=["foo_title", "foo_error: {}"],
    )
    @mock.patch("cs.pcs.projects.common.indicators.auth", persno="foo_user")
    @mock.patch("cs.pcs.projects.common.indicators.logging.warning")
    @mock.patch.object(indicators.ListConfig, "KeywordQuery")
    def test_get_overlay_no_access_granted(
        self, KeywordQuery, warning, auth, get_label
    ):
        # this testcase handles
        # a) no list_config with given name found
        # b) no read access granted on requested list_config name
        mock_request = mock.Mock()
        mock_request.json = {
            "list_config_name": "foo",
            "restKey": "bar",
        }
        mock_list_config = mock.Mock()
        mock_list_config.CheckAccess.return_value = False
        mock_list_config.generateListJSON = mock.Mock()
        KeywordQuery.return_value = [mock_list_config]

        self.assertDictEqual(
            indicators.IndicatorOverlayModel().get_overlay(mock_request),
            {
                "title": "foo_title",
                "items": [],
                "displayConfigs": {},
                "configError": "foo_error: foo",
            },
        )
        KeywordQuery.assert_called_once_with(name="foo")
        warning.assert_called_once_with(
            "IndicatorOverlayModel - Either '%s' has no read access on ListConfig '%s'"
            + " or the ListConfig does not exists.",
            "foo_user",
            "foo",
        )
        mock_list_config.generateListJSON.assert_not_called()
        mock_list_config.CheckAccess.assert_called_once_with("read")
        get_label.assert_has_calls(
            [
                mock.call("web.cs-pcs-widgets.list_widget_error_title"),
                mock.call("cs.pcs.projects.common.lists.list_access_error"),
            ]
        )
