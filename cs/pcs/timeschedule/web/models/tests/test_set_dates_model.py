#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

import unittest

import pytest
from cdb import testcase
from cdb.ue import Exception as ueException
from mock import MagicMock, call, patch
from webob.exc import HTTPBadRequest, HTTPNotFound

from cs.pcs.timeschedule.web.models import set_dates_model


def _get_model(model_cls):
    # initialize model without calling __init__
    return model_cls.__new__(model_cls)


@pytest.mark.unit
class SetDatesModel(unittest.TestCase):
    def _get_model(self):
        return _get_model(set_dates_model.SetDatesModel)

    @patch.object(set_dates_model.SetDatesModel, "get_object_from_uuid", autospec=True)
    @patch.object(set_dates_model.UpdateModel, "__init__", autospec=True)
    @testcase.without_error_logging
    def test___init__no_access(self, base_init, get_object_from_uuid):
        "fails if save access is denied for content object"
        get_object_from_uuid.return_value.CheckAccess.return_value = False
        model = self._get_model()
        with self.assertRaises(HTTPNotFound):
            model.__init__("foo", "bar")  # pylint: disable=unnecessary-dunder-call
        self.assertEqual(model.content_obj, get_object_from_uuid.return_value)
        base_init.assert_called_once_with(model, "foo", True)
        get_object_from_uuid.assert_called_once_with(model, "bar")
        get_object_from_uuid.return_value.CheckAccess.assert_called_once_with("save")

    @patch.object(set_dates_model.SetDatesModel, "get_object_from_uuid", autospec=True)
    @patch.object(set_dates_model.UpdateModel, "__init__", autospec=True)
    def test___init__(self, base_init, get_object_from_uuid):
        "initializes if content object is found and save access granted"
        model = self._get_model()
        # pylint: disable=unnecessary-dunder-call
        self.assertIsNone(model.__init__("foo", "bar"))
        self.assertEqual(model.content_obj, get_object_from_uuid.return_value)
        base_init.assert_called_once_with(model, "foo", True)
        get_object_from_uuid.assert_called_once_with(model, "bar")
        get_object_from_uuid.return_value.CheckAccess.assert_called_once_with("save")

    def _adjust_milestone(self, constraint_type):
        obj = MagicMock(constraint_type=constraint_type)
        set_dates_model.adjust_milestone(obj, "bar")
        return obj

    def test_adjust_milestone_ASAP_ALAP(self):
        for c in ["0", "1"]:
            obj = self._adjust_milestone(c)
            obj.setStartTimeFcast.assert_called_once_with(start="bar")
            obj.setEndTimeFcast.assert_not_called()
            self.assertEqual(obj.constraint_type, "4")
            self.assertEqual(obj.constraint_date, "bar")

    def test_adjust_milestone_MSO_SNET_SNLT(self):
        for c in ["2", "4", "5"]:
            obj = self._adjust_milestone(c)
            obj.setStartTimeFcast.assert_called_once_with(start="bar")
            obj.setEndTimeFcast.assert_not_called()
            self.assertEqual(obj.constraint_type, c)
            self.assertEqual(obj.constraint_date, "bar")

    def test_adjust_milestone_MFO_FNET_FNLT(self):
        for c in ["3", "6", "7"]:
            obj = self._adjust_milestone(c)
            obj.setStartTimeFcast.assert_not_called()
            obj.setEndTimeFcast.assert_called_once_with(end="bar")
            self.assertEqual(obj.constraint_type, c)
            self.assertEqual(obj.constraint_date, "bar")

    @patch.object(set_dates_model, "adjust_milestone")
    @patch.object(set_dates_model.SetDatesModel, "verify_writable")
    def test__verify_and_set_start_error(self, verify_writeable, adjust_milestone):
        "passes user-readable error message to frontend"
        obj = MagicMock()
        obj.setStartTimeFcastByBar.side_effect = ueException("foo")
        obj.milestone = None
        model = self._get_model()
        model.content_obj = obj
        with self.assertRaises(HTTPBadRequest) as error:
            model._verify_and_set_start("bar")
        self.assertEqual("foo (Error reading messages)", str(error.exception))
        adjust_milestone.assert_not_called()
        obj.setStartTimeFcastByBar.assert_called_once_with(
            start="bar",
        )
        verify_writeable.assert_called_once_with(obj, ["start_time_fcast"])

    @patch.object(set_dates_model, "adjust_milestone")
    @patch.object(set_dates_model.SetDatesModel, "verify_writable")
    def test__verify_and_set_start_without_milestone(
        self, verify_writeable, adjust_milestone
    ):
        "passes user-readable error message to frontend"
        obj = MagicMock()
        obj.milestone = None
        model = self._get_model()
        model.content_obj = obj
        model._verify_and_set_start("bar")
        adjust_milestone.assert_not_called()
        obj.setStartTimeFcastByBar.assert_called_once_with(
            start="bar",
        )
        verify_writeable.assert_called_once_with(obj, ["start_time_fcast"])

    @patch.object(set_dates_model, "adjust_milestone")
    @patch.object(set_dates_model.SetDatesModel, "verify_writable")
    def test__verify_and_set_start_with_milestone(
        self, verify_writeable, adjust_milestone
    ):
        "passes user-readable error message to frontend"
        obj = MagicMock()
        obj.milestone = "ml"
        model = self._get_model()
        model.content_obj = obj
        model._verify_and_set_start("bar")
        adjust_milestone.assert_called_once_with(obj, "bar")
        obj.setStartTimeFcastByBar.assert_not_called()
        verify_writeable.assert_called_once_with(obj, ["start_time_fcast"])

    @patch.object(set_dates_model, "adjust_milestone")
    @patch.object(set_dates_model.SetDatesModel, "verify_writable")
    def test__verify_and_set_start_error_milestone(
        self, verify_writeable, adjust_milestone
    ):
        "passes user-readable error message to frontend"
        obj = MagicMock(milestone=1)
        model = self._get_model()
        model.content_obj = obj
        adjust_milestone.side_effect = ueException("foo")
        with self.assertRaises(HTTPBadRequest) as error:
            model._verify_and_set_start("bar")
        self.assertEqual("foo (Error reading messages)", str(error.exception))
        adjust_milestone.assert_called_once_with(obj, "bar")
        obj.setStartTimeFcastByBar.assert_not_called()
        verify_writeable.assert_called_once_with(obj, ["start_time_fcast"])

    @patch.object(set_dates_model, "adjust_milestone")
    @patch.object(set_dates_model.SetDatesModel, "verify_writable")
    def test__verify_and_set_start_milestone(self, verify_writeable, adjust_milestone):
        "passes user-readable error message to frontend"
        obj = MagicMock(milestone=1)
        model = self._get_model()
        model.content_obj = obj
        model._verify_and_set_start("bar")
        adjust_milestone.assert_called_once_with(obj, "bar")
        obj.setStartTimeFcastByBar.assert_not_called()
        verify_writeable.assert_called_once_with(obj, ["start_time_fcast"])

    @patch.object(set_dates_model.SetDatesModel, "_verify_and_set_start")
    @patch.object(set_dates_model.SetDatesModel, "get_changed_data", autospec=True)
    @patch.object(set_dates_model, "get_date", autospec=True)
    def test_set_start(self, get_date, get_changed_data, _verify_and_set_start):
        "calls update method and returns updated data"
        obj = MagicMock()
        request = MagicMock()
        model = self._get_model()
        model.content_obj = obj
        self.assertEqual(model.set_start(request), get_changed_data.return_value)
        get_date.assert_called_once_with(request.json, "startDate")
        _verify_and_set_start.assert_called_once_with(get_date.return_value)
        get_changed_data.assert_called_once_with(model, request)

    @patch.object(set_dates_model, "adjust_milestone")
    @patch.object(set_dates_model.SetDatesModel, "verify_writable")
    def test__verify_and_set_end_error(self, verify_writeable, adjust_milestone):
        "passes user-readable error message to frontend"
        obj = MagicMock()
        obj.milestone = None
        obj.setEndTimeFcastByBar.side_effect = ueException("foo")
        model = self._get_model()
        model.content_obj = obj
        with self.assertRaises(HTTPBadRequest) as error:
            model._verify_and_set_end("bar")
        self.assertEqual("foo (Error reading messages)", str(error.exception))
        adjust_milestone.assert_not_called()
        obj.setEndTimeFcastByBar.assert_called_once_with(
            end="bar",
        )
        verify_writeable.assert_called_once_with(obj, ["end_time_fcast"])

    @patch.object(set_dates_model, "adjust_milestone")
    @patch.object(set_dates_model.SetDatesModel, "verify_writable")
    def test__verify_and_set_end_without_milestone(
        self, verify_writeable, adjust_milestone
    ):
        "passes user-readable error message to frontend"
        obj = MagicMock()
        obj.milestone = None
        model = self._get_model()
        model.content_obj = obj
        model._verify_and_set_end("bar")
        adjust_milestone.assert_not_called()
        obj.setEndTimeFcastByBar.assert_called_once_with(
            end="bar",
        )
        verify_writeable.assert_called_once_with(obj, ["end_time_fcast"])

    @patch.object(set_dates_model, "adjust_milestone")
    @patch.object(set_dates_model.SetDatesModel, "verify_writable")
    def test__verify_and_set_end_with_milestone(
        self, verify_writeable, adjust_milestone
    ):
        "passes user-readable error message to frontend"
        obj = MagicMock()
        obj.milestone = "ml"
        model = self._get_model()
        model.content_obj = obj
        model._verify_and_set_end("bar")
        adjust_milestone.assert_called_once_with(obj, "bar")
        obj.setEndTimeFcastByBar.assert_not_called()
        verify_writeable.assert_called_once_with(obj, ["end_time_fcast"])

    @patch.object(set_dates_model, "adjust_milestone")
    @patch.object(set_dates_model.SetDatesModel, "verify_writable")
    def test__verify_and_set_end_error_milestone(
        self, verify_writeable, adjust_milestone
    ):
        "passes user-readable error message to frontend"
        obj = MagicMock(milestone=1)
        model = self._get_model()
        model.content_obj = obj
        adjust_milestone.side_effect = ueException("foo")
        with self.assertRaises(HTTPBadRequest) as error:
            model._verify_and_set_end("bar")
        self.assertEqual("foo (Error reading messages)", str(error.exception))
        adjust_milestone.assert_called_once_with(obj, "bar")
        obj.setEndTimeFcastByBar.assert_not_called()
        verify_writeable.assert_called_once_with(obj, ["end_time_fcast"])

    @patch.object(set_dates_model, "adjust_milestone")
    @patch.object(set_dates_model.SetDatesModel, "verify_writable")
    def test__verify_and_set_end_milestone(self, verify_writeable, adjust_milestone):
        obj = MagicMock(milestone=1)
        model = self._get_model()
        model.content_obj = obj
        model._verify_and_set_end("bar")
        adjust_milestone.assert_called_once_with(obj, "bar")
        obj.setEndTimeFcastByBar.assert_not_called()
        verify_writeable.assert_called_once_with(obj, ["end_time_fcast"])

    @patch.object(set_dates_model.SetDatesModel, "_verify_and_set_end")
    @patch.object(set_dates_model.SetDatesModel, "get_changed_data", autospec=True)
    @patch.object(set_dates_model, "get_date", autospec=True)
    def test_set_end(self, get_date, get_changed_data, _verify_and_set_end):
        "calls update method and returns updated data"
        obj = MagicMock()
        request = MagicMock()
        model = self._get_model()
        model.content_obj = obj
        self.assertEqual(model.set_end(request), get_changed_data.return_value)
        get_date.assert_called_once_with(request.json, "endDate")
        _verify_and_set_end.assert_called_once_with(get_date.return_value)
        get_changed_data.assert_called_once_with(model, request)

    @patch.object(set_dates_model.SetDatesModel, "verify_writable")
    @patch.object(set_dates_model.SetDatesModel, "get_changed_data", autospec=True)
    @patch.object(set_dates_model, "get_date", autospec=True)
    def test_set_start_and_end_error(self, get_date, get_changed_data, verify_writable):
        "passes user-readable error message to frontend"
        obj = MagicMock(milestone=False)
        obj.moveTimeframe.side_effect = ueException("foo")
        request = MagicMock()
        model = self._get_model()
        model.content_obj = obj
        with self.assertRaises(HTTPBadRequest) as error:
            model.set_start_and_end(request)
        self.assertEqual("foo (Error reading messages)", str(error.exception))
        get_date.assert_has_calls(
            [
                call(request.json, "startDate"),
                call(request.json, "endDate"),
            ]
        )
        self.assertEqual(get_date.call_count, 2)
        obj.moveTimeframe.assert_called_once_with(
            start=get_date.return_value,
            end=get_date.return_value,
        )
        self.assertEqual(get_changed_data.call_count, 0)

    @patch.object(set_dates_model.SetDatesModel, "verify_writable")
    @patch.object(set_dates_model.SetDatesModel, "get_changed_data", autospec=True)
    @patch.object(set_dates_model, "get_date", autospec=True)
    def test_set_start_and_end_non_milestone(
        self, get_date, get_changed_data, verify_writable
    ):
        "calls update method on non milestone and returns updated data"
        obj = MagicMock(milestone=False)
        request = MagicMock()
        model = self._get_model()
        model.content_obj = obj
        self.assertEqual(
            model.set_start_and_end(request), get_changed_data.return_value
        )
        get_date.assert_has_calls(
            [
                call(request.json, "startDate"),
                call(request.json, "endDate"),
            ]
        )
        self.assertEqual(get_date.call_count, 2)
        obj.moveTimeframe.assert_called_once_with(
            start=get_date.return_value,
            end=get_date.return_value,
        )
        get_changed_data.assert_called_once_with(model, request)
        verify_writable.assert_called_once_with(
            obj, ["start_time_fcast", "end_time_fcast"]
        )

    @patch.object(set_dates_model.SetDatesModel, "_verify_and_set_start")
    @patch.object(set_dates_model.SetDatesModel, "get_changed_data", autospec=True)
    @patch.object(
        set_dates_model, "get_date", autospec=True, side_effect=["start", "end"]
    )
    def test_set_start_and_end_milestone(
        self, get_date, get_changed_data, _verify_and_set_start
    ):
        "calls update method on milestone and returns updated data"
        # Note: We only test one of the two case of start_is_early
        obj = MagicMock(milestone=True, start_is_early=True)
        obj.__contains__.return_value = True
        request = MagicMock()
        model = self._get_model()
        model.content_obj = obj
        model.context_object_id = "foo"
        self.assertEqual(
            model.set_start_and_end(request), get_changed_data.return_value
        )
        get_date.assert_has_calls(
            [
                call(request.json, "startDate"),
                call(request.json, "endDate"),
            ]
        )
        self.assertEqual(get_date.call_count, 2)
        get_changed_data.assert_called_once_with(model, request)
        _verify_and_set_start.assert_called_once_with("start")


if __name__ == "__main__":
    unittest.main()
