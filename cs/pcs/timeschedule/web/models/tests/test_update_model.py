# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=protected-access

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import unittest
from datetime import datetime

import pytest
from mock import MagicMock, patch
from webob.exc import HTTPForbidden

from cs.pcs.timeschedule.web.models import update_model


@pytest.mark.unit
class UpdateModel(unittest.TestCase):
    @patch.object(update_model.DataModel, "__init__", autospec=True)
    def test___init__now(self, base_init):
        "initializes base model with current timestamp"
        model = MagicMock(spec=update_model.UpdateModel)
        self.assertIsNone(
            update_model.UpdateModel.__init__(model, "foo", True),
        )
        self.assertIsInstance(model.baseline, datetime)
        diff = (datetime.utcnow() - model.baseline).seconds
        self.assertGreaterEqual(diff, 0)
        self.assertLessEqual(diff, 1)
        base_init.assert_called_once_with(model, "foo")

    @patch.object(update_model.DataModel, "__init__", autospec=True)
    def test___init__(self, base_init):
        "initializes base model without timestamp"
        model = MagicMock(spec=update_model.UpdateModel)
        self.assertIsNone(update_model.UpdateModel.__init__(model, "foo"))
        self.assertIsNone(model.baseline)
        base_init.assert_called_once_with(model, "foo")

    def test__set_baseline_already_done(self):
        "does nothing if baseline already initialized"
        model = MagicMock(
            spec=update_model.UpdateModel,
            baseline=True,
        )
        self.assertIsNone(update_model.UpdateModel._set_baseline(model, None))
        self.assertEqual(model.baseline, True)

    def test__set_baseline_no_json(self):
        "fails if JSON payload is missing"
        model = MagicMock(
            spec=update_model.UpdateModel,
            baseline=None,
        )
        request = MagicMock()
        request.json.get.side_effect = ValueError
        with self.assertRaises(update_model.HTTPBadRequest):
            update_model.UpdateModel._set_baseline(model, request)

    def test__set_baseline_invalid_format(self):
        "initializes baseline if lastUpdated does not match expected format"
        model = MagicMock(
            spec=update_model.UpdateModel,
            baseline=None,
            TIMESTAMP_FORMAT="%Y-%m-%d",
        )
        request = MagicMock(json={"lastUpdated": "2020.3.17"})
        with self.assertRaises(update_model.HTTPBadRequest):
            update_model.UpdateModel._set_baseline(model, request)

    def test__set_baseline_no_date(self):
        "does not initialize baseline if lastUpdated not given"
        model = MagicMock(
            spec=update_model.UpdateModel,
            baseline=None,
        )
        request = MagicMock(json={})
        self.assertIsNone(update_model.UpdateModel._set_baseline(model, request))
        self.assertEqual(model.baseline, None)

    def test__set_baseline(self):
        "initializes baseline if not initialized yet"
        model = MagicMock(
            spec=update_model.UpdateModel,
            baseline=None,
            TIMESTAMP_FORMAT="%Y-%m-%d",
        )
        request = MagicMock(json={"lastUpdated": "2020-3-17"})
        self.assertIsNone(update_model.UpdateModel._set_baseline(model, request))
        self.assertEqual(model.baseline, datetime(2020, 3, 16, 23, 59, 59))

    def test__get_full_data_first_page_no_baseline(self):
        "returns all data if baseline is not set"
        model = MagicMock(
            spec=update_model.UpdateModel,
            baseline=None,
        )

        record_a = MagicMock(cdb_object_id="A")
        record_a.get.return_value = None
        ts_record_a = MagicMock(record=record_a)
        record_b = MagicMock(cdb_object_id="B")
        record_b.get.return_value = 5
        ts_record_b = MagicMock(record=record_b)
        record_c = MagicMock(cdb_object_id="C")
        record_c.get.return_value = 2
        ts_record_c = MagicMock(record=record_c)

        self.assertEqual(
            update_model.UpdateModel._get_full_data_first_page(
                model,
                None,
                [ts_record_a, ts_record_b, ts_record_c],
                [],
                {},
                "request",
            ),
            model.get_full_data.return_value,
        )
        model.get_full_data.assert_called_once_with(
            ["A", "B", "C"],
            None,
            [ts_record_a, ts_record_b, ts_record_c],
            [],
            "request",
        )

    def test__get_full_data_first_page(self):
        "returns changed data if baseline is set"
        model = MagicMock(
            spec=update_model.UpdateModel,
            baseline=2,
        )

        record_a = MagicMock(cdb_object_id="A")
        record_a.get.return_value = None
        ts_record_a = MagicMock(record=record_a)
        record_b = MagicMock(cdb_object_id="B")
        record_b.get.return_value = 5
        ts_record_b = MagicMock(record=record_b)
        record_c = MagicMock(cdb_object_id="C")
        record_c.get.return_value = 2
        ts_record_c = MagicMock(record=record_c)

        self.assertEqual(
            update_model.UpdateModel._get_full_data_first_page(
                model,
                None,
                [ts_record_a, ts_record_b, ts_record_c],
                [],
                {},
                "request",
            ),
            model.get_full_data.return_value,
        )
        model.get_full_data.assert_called_once_with(
            ["A", "B", "C"],
            None,
            [ts_record_a, ts_record_b],
            [],
            "request",
        )

    def test_get_changed_data(self):
        "returns full data of changed objects"
        model = MagicMock(spec=update_model.UpdateModel)
        self.assertEqual(
            update_model.UpdateModel.get_changed_data(model, "request"),
            model.get_data.return_value,
        )
        model._set_baseline.assert_called_once_with("request")
        model.get_data.assert_called_once_with("request")

    @patch.object(update_model, "get_label", return_value="refresh")
    @patch.object(update_model, "ReadOnlyModel")
    def test_verify_writable(self, ReadOnlyModel, get_label):
        model = MagicMock(spec=update_model.UpdateModel)
        model.context_object_id = "context_id"
        read_only_data = {"byClass": {"foo": ["bar"]}, "byObject": {"id": ["bar"]}}

        obj = MagicMock(_getClassname=MagicMock(return_value="foo"), cdb_object_id="id")

        ReadOnlyModel.return_value = MagicMock(
            get_read_only_data=MagicMock(return_value=read_only_data)
        )

        with self.assertRaises(HTTPForbidden):
            update_model.UpdateModel.verify_writable(model, obj, ["bar"])


if __name__ == "__main__":
    unittest.main()
