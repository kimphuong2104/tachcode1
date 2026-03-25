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

from cs.taskmanager.web import rest_app
from cs.taskmanager.web.models.views import MYTASKSAPP


@pytest.mark.unit
class Utility(unittest.TestCase):
    def test_require_payload_single(self):
        request = mock.MagicMock(json={"bar": "B", "foo": "F"})
        self.assertEqual(
            rest_app.require_payload(None, request, "foo"),
            "F",
        )

    def test_require_payload_multi(self):
        request = mock.MagicMock(json={"bar": "B", "foo": "F"})
        self.assertEqual(
            rest_app.require_payload(None, request, "foo", "bar"),
            ["F", "B"],
        )

    @mock.patch.object(rest_app.logging, "error")
    def test_require_payload_missing(self, error):
        request = mock.MagicMock(json={})
        with self.assertRaises(rest_app.HTTPBadRequest):
            rest_app.require_payload(None, request, "foo")
        error.assert_called_once()

    @mock.patch.object(
        rest_app.Settings,
        "get_tasks_settings",
        side_effect=rest_app.ErrorMessage("not an error message"),
    )
    def test_get_tasks_settings(self, _):
        model = rest_app.Settings()

        with self.assertRaises(rest_app.HTTPInternalServerError) as error:
            rest_app.get_tasks_settings(model, None)

        self.assertEqual(
            str(error.exception),
            # use non-existing error message because nosetest cannot resolve messages
            "not an error message (Error reading messages)",
        )

    @mock.patch.object(
        rest_app,
        "require_payload",
        return_value=[{"payload": "payload", "widgetID": MYTASKSAPP}],
    )
    def test_get_data(self, require_payload):
        model = mock.MagicMock()
        model.get_tasks.return_value = {}
        request = mock.MagicMock()

        self.assertEqual(
            rest_app.get_data(model, request), [model.get_tasks.return_value]
        )

        require_payload.assert_called_once_with("data", request, "conditions")
        model.get_tasks.assert_called_once_with(
            {"payload": "payload", "widgetID": MYTASKSAPP}, request
        )

    @mock.patch.object(
        rest_app,
        "require_payload",
        return_value=[{"payload": "payload", "widgetID": MYTASKSAPP}],
    )
    def test_get_updates(self, require_payload):
        model = mock.MagicMock()
        request = mock.MagicMock()
        self.assertEqual(
            rest_app.get_updates(model, request), [model.get_updates.return_value]
        )
        require_payload.assert_called_once_with("updates", request, "conditions")
        model.get_updates.assert_called_once_with(
            {"payload": "payload", "widgetID": MYTASKSAPP}, request
        )

    @mock.patch.object(rest_app, "require_payload", return_value="cdb_object_id")
    def test_get_target_statuses(self, require_payload):
        model = mock.MagicMock()
        request = mock.MagicMock()
        self.assertEqual(
            rest_app.get_target_statuses(model, request),
            model.get_target_statuses.return_value,
        )
        require_payload.assert_called_once_with(
            "data_target_statuses", request, "cdb_object_id"
        )
        model.get_target_statuses.assert_called_once_with("cdb_object_id")

    def test_get_task_context(self):
        model = mock.MagicMock()
        self.assertEqual(
            rest_app.get_task_context(model, None), model.resolve_context.return_value
        )
        model.resolve_context.assert_called_once_with(None)

    @mock.patch.object(rest_app, "require_payload", return_value=["read", "unread"])
    def test_set_read_status(self, require_payload):
        model = mock.MagicMock()
        request = mock.MagicMock()
        self.assertEqual(rest_app.set_read_status(model, request), None)
        require_payload.assert_called_once_with(
            "set_read_status", request, "read", "unread"
        )
        model.set_read_status.assert_called_once_with("read", "unread")

    def test_set_tags(self):
        model = mock.MagicMock()
        request = mock.MagicMock()

        self.assertEqual(rest_app.set_tags(model, request), model.set_tags.return_value)

        model.set_tags.assert_called_once_with(request.json)

    @mock.patch.object(rest_app, "require_payload", return_value=["name", "condition"])
    def test_new_view(self, require_payload):
        model = mock.MagicMock()
        request = mock.MagicMock()

        self.assertEqual(
            rest_app.new_view(model, request), model.get_all_views.return_value
        )

        require_payload.assert_called_once_with(
            "new_view", request, "name", "condition"
        )
        model.new.assert_called_once_with("name", "condition")
        model.get_all_views.assert_called_once_with(request)

    def test_select_view(self):
        model = mock.MagicMock()
        request = mock.MagicMock()

        self.assertEqual(
            rest_app.select_view(model, request), model.get_all_views.return_value
        )

        model.select.assert_called_once()
        model.get_all_views.assert_called_once_with(request)

    @mock.patch.object(rest_app, "require_payload", return_value="name")
    def test_edit_view(self, require_payload):
        model = mock.MagicMock()
        request = mock.MagicMock()

        self.assertEqual(
            rest_app.edit_view(model, request), model.get_all_views.return_value
        )

        model.edit.assert_called_once_with(require_payload.return_value)
        model.get_all_views.assert_called_once_with(request)

    def test_revert_view(self):
        model = mock.MagicMock()
        request = mock.MagicMock()

        self.assertEqual(
            rest_app.revert_view(model, request), model.get_all_views.return_value
        )

        model.revert.assert_called_once()
        model.get_all_views.assert_called_once_with(request)

    def test_get_webdata(self):
        model = mock.MagicMock()
        request = mock.MagicMock()

        self.assertEqual(
            rest_app.get_webdata(model, request), model.get_async_data.return_value
        )


if __name__ == "__main__":
    unittest.main()
