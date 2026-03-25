#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=no-value-for-parameter

import unittest

import pytest
from mock import MagicMock, patch
from webob.exc import HTTPBadRequest

from cs.pcs.timeschedule.web.models import read_only_model


@pytest.mark.unit
class ReadOnlyModel(unittest.TestCase):
    @patch.object(read_only_model.ReadOnlyModel, "collect_plugins")
    def _get_model(self, _):
        # initialize model without calling __init__
        return read_only_model.ReadOnlyModel.__new__(read_only_model.ReadOnlyModel)

    @patch.object(read_only_model.WithTimeSchedulePlugin, "__init__", autospec=True)
    @patch.object(read_only_model.ScheduleBaseModel, "__init__", autospec=True)
    def test___init__(self, base_init, with_init):
        "model and super class are initialized"
        model = self._get_model()
        model.__init__("foo")  # pylint: disable=unnecessary-dunder-call
        base_init.assert_called_once_with(model, "foo")
        with_init.assert_not_called()

    @patch.object(read_only_model, "logging")
    def test_get_read_only_request_missing_oids(self, logging):
        "Raises HTTPBadRequest, since request json is incomplete"
        model = self._get_model()
        mock_request = MagicMock()
        mock_request.json = {}
        with self.assertRaises(HTTPBadRequest):
            model.get_read_only(mock_request)
        logging.error.assert_called_once_with("request is missing 'oids'")

    @patch.object(read_only_model, "get_pcs_oids", return_value="resolved_oids")
    @patch.object(
        read_only_model,
        "get_oids_by_relation",
        return_value=[("tablename", ["id1", "id2"])],
    )
    @patch.object(read_only_model, "get_oid_query_str", return_value="oid_query_str")
    @patch.object(read_only_model, "sqlapi")
    def test_get_read_only(
        self, sqlapi, get_oid_query_str, get_oids_by_relation, get_pcs_oids
    ):
        model = self._get_model()
        mock_request = MagicMock()
        mock_request.json = {"oids": "bar"}
        mock_plugin = MagicMock()
        mock_plugin.classname = "classname"
        mock_plugin.table_name = "tablename"
        mock_plugin.GetClassReadOnlyFields = MagicMock(return_value="foo")
        mock_plugin.GetObjectReadOnlyFields = MagicMock(return_value={"id2": "baz"})
        model.plugins = {"p1": mock_plugin}
        mock_record = MagicMock()
        mock_record.cdb_object_id = "id2"
        sqlapi.RecordSet2 = MagicMock(return_value=[mock_record])
        self.assertDictEqual(
            {
                "OIDs": ["id1"],
                "byClass": {"classname": "foo"},
                "byObject": {"id2": "baz"},
            },
            model.get_read_only(mock_request),
        )
        get_pcs_oids.assert_called_once_with("bar")
        get_oids_by_relation.assert_called_once_with("resolved_oids")
        get_oid_query_str.assert_called_once_with(["id1", "id2"])
        sqlapi.RecordSet2.assert_called_once_with(
            "tablename", "oid_query_str", access="save"
        )
        mock_plugin.GetClassReadOnlyFields.assert_called_once()
        mock_plugin.GetObjectReadOnlyFields.assert_called_once_with(["id2"])


if __name__ == "__main__":
    unittest.main()
