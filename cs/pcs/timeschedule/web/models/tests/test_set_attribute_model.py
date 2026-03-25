#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access,no-value-for-parameter

import unittest
from datetime import date

import mock
import pytest

from cs.pcs.timeschedule.web.models import set_attribute_model
from cs.pcs.timeschedule.web.models.set_attribute_model import SetAttributeModel


@pytest.mark.unit
class SetAttributeModelTest(unittest.TestCase):
    @mock.patch.object(set_attribute_model.UpdateModel, "__init__", autospec=True)
    def test___init__(self, parent_init):
        model = mock.MagicMock(spec=SetAttributeModel)
        self.assertIsNone(SetAttributeModel.__init__(model, "foo", "bar"))
        self.assertEqual(model.cdb_object_id, "bar")
        parent_init.assert_called_once_with(model, "foo", True)
        model.get_object_from_uuid.assert_called_once_with("bar")

    @mock.patch.object(set_attribute_model.logging, "error", autospec=True)
    @mock.patch.object(set_attribute_model.UpdateModel, "__init__", autospec=True)
    def test___init___no_access(self, _, error):
        model = mock.MagicMock(spec=SetAttributeModel)
        model.get_object_from_uuid.return_value.CheckAccess.return_value = False
        with self.assertRaises(set_attribute_model.HTTPForbidden):
            SetAttributeModel.__init__(model, "foo", "bar")

        error.assert_called_once_with("save access not granted on object '%s'", "bar")

    @mock.patch.object(set_attribute_model, "adjust_milestone")
    @mock.patch.object(set_attribute_model, "is_milestone", return_value=True)
    def test__ts_api_fcast_milestone(self, _, adjust_milestone):
        model = mock.MagicMock(spec=SetAttributeModel, object="has no methods")
        self.assertIsNone(SetAttributeModel._ts_api_fcast(model, "foo", "bar"))
        adjust_milestone.assert_called_once_with(model.object, "bar")

    @mock.patch.object(set_attribute_model, "is_milestone", return_value=False)
    def test__ts_api_fcast_task_start(self, _):
        model = mock.MagicMock(spec=SetAttributeModel, object=mock.Mock())
        self.assertIsNone(
            SetAttributeModel._ts_api_fcast(model, "start_time_fcast", "bar")
        )
        model.object.setStartTimeFcast.assert_called_once_with(start="bar")

    @mock.patch.object(set_attribute_model, "is_milestone", return_value=False)
    def test__ts_api_fcast_task_end(self, _):
        model = mock.MagicMock(spec=SetAttributeModel, object=mock.Mock())
        self.assertIsNone(SetAttributeModel._ts_api_fcast(model, "not start", "bar"))
        model.object.setEndTimeFcast.assert_called_once_with(end="bar")

    def test__ts_api_plan_start(self):
        model = mock.MagicMock(spec=SetAttributeModel, object=mock.Mock())
        model.object.MakeChangeControlAttributes.return_value = {"change": "control"}
        self.assertIsNone(
            SetAttributeModel._ts_api_plan(model, "start_time_plan", "bar")
        )
        model.object.Update.assert_called_once_with(
            change="control",
            start_time_plan="bar",
        )
        model.object.change_start_time_plan.assert_called_once_with()

    def test__ts_api_plan_end(self):
        model = mock.MagicMock(spec=SetAttributeModel, object=mock.Mock())
        model.object.MakeChangeControlAttributes.return_value = {"change": "control"}
        self.assertIsNone(SetAttributeModel._ts_api_plan(model, "end_time_plan", "bar"))
        model.object.Update.assert_called_once_with(
            change="control",
            end_time_plan="bar",
        )
        model.object.change_end_time_plan.assert_called_once_with()

    def test__ts_api_act_start(self):
        model = mock.MagicMock(
            spec=SetAttributeModel,
            object=mock.Mock(
                end_time_act=date(2022, 8, 4),
            ),
        )
        model.object.MakeChangeControlAttributes.return_value = {"change": "control"}
        start = date(2022, 8, 1)
        self.assertIsNone(SetAttributeModel._ts_api_act(model, "start_time_act", start))
        model.object.Update.assert_called_once_with(
            change="control",
            start_time_act=start,
        )
        model.object.change_start_time_act.assert_called_once_with()

    def test__ts_api_act_end(self):
        model = mock.MagicMock(
            spec=SetAttributeModel,
            object=mock.Mock(
                start_time_act=date(2022, 8, 1),
            ),
        )
        model.object.MakeChangeControlAttributes.return_value = {"change": "control"}
        end = date(2022, 8, 4)
        self.assertIsNone(SetAttributeModel._ts_api_act(model, "end_time_act", end))
        model.object.Update.assert_called_once_with(
            change="control",
            end_time_act=end,
        )
        model.object.change_end_time_act.assert_called_once_with()

    def test__ts_api_act_end_before_start(self):
        model = mock.MagicMock(
            spec=SetAttributeModel,
            object=mock.Mock(
                start_time_act=date(2022, 8, 1),
            ),
        )
        end = date(2022, 7, 14)

        with self.assertRaises(set_attribute_model.HTTPBadRequest) as error:
            SetAttributeModel._ts_api_act(model, "foo", end)

        self.assertEqual(
            str(error.exception),
            "Ende (Ist) darf nicht früher als Beginn (Ist) sein.",
        )

    def test__ts_api_act_only_end(self):
        model = mock.MagicMock(
            spec=SetAttributeModel,
            object=mock.Mock(
                start_time_act=None,
            ),
        )
        end = date(2022, 7, 14)

        with self.assertRaises(set_attribute_model.HTTPBadRequest) as error:
            SetAttributeModel._ts_api_act(model, "foo", end)

        self.assertEqual(
            str(error.exception),
            "Beginn (Ist) darf nicht leer sein, wenn Ende (Ist) gesetzt ist.",
        )

    def test__ts_api_days(self):
        model = mock.MagicMock(
            spec=SetAttributeModel,
            object=mock.Mock(),
        )
        model.object.MakeChangeControlAttributes.return_value = {"change": "control"}
        self.assertIsNone(SetAttributeModel._ts_api_days(model, "foo"))
        model.object.Update.assert_called_once_with(days="foo", change="control")
        model.object.change_days.assert_called_once_with()

    def test__ts_api_days_invalid(self):
        model = mock.MagicMock(
            spec=SetAttributeModel,
            object=mock.Mock(),
        )
        model.object.MakeChangeControlAttributes.return_value = {}
        model.object.Update.side_effect = ValueError

        with self.assertRaises(set_attribute_model.HTTPBadRequest) as error:
            SetAttributeModel._ts_api_days(model, "foo")

        self.assertEqual(
            str(error.exception),
            "'foo' not valid",
        )

    @mock.patch.object(set_attribute_model, "aggregate_changes")
    @mock.patch.object(set_attribute_model, "get_date")
    def _ts_api_date(self, key, method, get_date, aggregate_changes):
        model = mock.MagicMock(
            spec=SetAttributeModel,
            object=mock.Mock(),
        )
        self.assertIsNone(SetAttributeModel._set_attribute_by_TS_API(model, key, "foo"))
        get_date.assert_called_once_with("foo", key, is_iso=False)
        getattr(model, method).assert_called_once_with(key, get_date.return_value)
        aggregate_changes.assert_called_once_with(model.object.Project)

    def test__set_attribute_by_TS_API_fcast_start(self):
        self._ts_api_date("start_time_fcast", "_ts_api_fcast")

    def test__set_attribute_by_TS_API_fcast_end(self):
        self._ts_api_date("end_time_fcast", "_ts_api_fcast")

    def test__set_attribute_by_TS_API_plan_start(self):
        self._ts_api_date("start_time_plan", "_ts_api_plan")

    def test__set_attribute_by_TS_API_plan_end(self):
        self._ts_api_date("end_time_plan", "_ts_api_plan")

    def test__set_attribute_by_TS_API_act_start(self):
        self._ts_api_date("start_time_act", "_ts_api_act")

    def test__set_attribute_by_TS_API_act_end(self):
        self._ts_api_date("end_time_act", "_ts_api_act")

    @mock.patch.object(set_attribute_model, "aggregate_changes")
    def _ts_api_days(self, key, method, aggregate_changes):
        model = mock.MagicMock(
            spec=SetAttributeModel,
            object=mock.Mock(),
        )
        self.assertIsNone(
            SetAttributeModel._set_attribute_by_TS_API(model, key, {key: "foo"})
        )
        getattr(model, method).assert_called_once_with("foo")
        aggregate_changes.assert_called_once_with(model.object.Project)

    def test__set_attribute_by_TS_API_days(self):
        self._ts_api_days("days", "_ts_api_days")

    def test__set_attribute_by_TS_API_days_fcast(self):
        self._ts_api_days("days_fcast", "_ts_api_days_fcast")

    def test__set_attribute_by_TS_API_invalid_key(self):
        model = mock.MagicMock(spec=SetAttributeModel)
        with self.assertRaises(set_attribute_model.HTTPBadRequest) as error:
            SetAttributeModel._set_attribute_by_TS_API(model, "invalid", "foo")

        self.assertEqual(
            str(error.exception),
            "invalid key: 'invalid'",
        )

    def test_set_attribute_no_updates(self):
        "fails if request is missing the 'updates' key"
        model = mock.MagicMock(spec=SetAttributeModel)
        request = mock.MagicMock(json={})
        with self.assertRaises(set_attribute_model.HTTPBadRequest):
            SetAttributeModel.set_attribute(model, request)

    @mock.patch.object(set_attribute_model, "kOperationModify", "MOD")
    @mock.patch.object(
        set_attribute_model,
        "operation",
        autospec=True,
        side_effect=set_attribute_model.ElementsError,
    )
    @mock.patch.object(set_attribute_model, "form_input", autospec=True)
    def test_set_attribute_fail(self, form_input, operation):
        "fails if operation raises ElementsError"
        model = mock.MagicMock(spec=SetAttributeModel, object=None)
        request = mock.MagicMock(json={"updates": {"foo": "bar"}})

        with self.assertRaises(set_attribute_model.HTTPForbidden):
            SetAttributeModel.set_attribute(model, request)

        form_input.assert_called_once_with(model.object, foo="bar")
        operation.assert_called_once_with(
            "MOD",
            model.object,
            form_input.return_value,
        )
        model.verify_writable.assert_called_once_with(None, ["foo"])

    @mock.patch.object(set_attribute_model, "kOperationModify", "MOD")
    @mock.patch.object(set_attribute_model, "operation", autospec=True)
    @mock.patch.object(set_attribute_model, "form_input", autospec=True)
    def test_set_attribute(self, form_input, operation):
        "succeeds"
        model = mock.MagicMock(spec=SetAttributeModel, object=None)
        request = mock.MagicMock(json={"updates": {"foo": "bar"}})

        self.assertEqual(
            SetAttributeModel.set_attribute(model, request),
            model.get_changed_data.return_value,
        )

        model.get_changed_data.assert_called_once_with(request)
        form_input.assert_called_once_with(model.object, foo="bar")
        operation.assert_called_once_with(
            "MOD",
            model.object,
            form_input.return_value,
        )

        model.verify_writable.assert_called_once_with(None, ["foo"])


if __name__ == "__main__":
    unittest.main()
