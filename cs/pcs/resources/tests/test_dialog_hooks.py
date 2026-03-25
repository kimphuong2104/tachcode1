#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

from unittest import TestCase

from mock import MagicMock, call, patch

from cs.pcs.resources import dialog_hooks as dh


class TestDialogHooks(TestCase):
    def test__get_object_from_hook(self):
        hook = MagicMock()
        hook.get_new_values.side_effect = lambda: {"a.b": 1, "a.c": 2}
        cls_obj = MagicMock(__maps_to__="a")
        self.assertEqual(dh._get_object_from_hook(cls_obj, hook), cls_obj.return_value)
        cls_obj.assert_called_once_with(b=1, c=2)

    def test_get_prefixed_field(self):
        cls_obj = MagicMock(__maps_to__="a")
        self.assertEqual(dh.get_prefixed_field(cls_obj, "b"), "a.b")

    @patch.object(dh, "get_prefixed_field")
    def test_set_hook_values(self, get_prefixed_field):
        cls_obj = MagicMock()
        hook = MagicMock()
        changes = {"a": 2, "b": 4}
        dh.set_hook_values(cls_obj, changes, hook)
        get_prefixed_field.assert_has_calls([call(cls_obj, "a"), call(cls_obj, "b")])
        hook.set.assert_has_calls(
            [
                call(get_prefixed_field.return_value, 2),
                call(get_prefixed_field.return_value, 4),
            ]
        )

    @patch.object(dh, "_get_object_from_hook")
    @patch.object(dh, "set_hook_values")
    def test_ResPool_dialogitem_change_web(
        self, set_hook_values, _get_object_from_hook
    ):
        hook = MagicMock()
        obj = MagicMock()
        _get_object_from_hook.return_value = obj
        changes = {
            "start_date": obj.getStart.return_value,
            "end_date": obj.getEnd.return_value,
        }

        dh.ResourcePoolAssignment.dialogitem_change_web(hook)
        _get_object_from_hook.assert_called_once_with(dh.ResourcePoolAssignment, hook)
        set_hook_values.assert_called_once_with(
            dh.ResourcePoolAssignment, changes, hook
        )

    @patch.object(dh, "_get_object_from_hook")
    @patch.object(dh, "date_from_legacy_str")
    def test_ResPool_check_dates_overlap_web(
        self, date_from_legacy_str, _get_object_from_hook
    ):
        hook = MagicMock()
        state_info = MagicMock()
        obj = MagicMock()

        state_info.get_objects.return_value = [obj]
        hook.get_operation_name.return_value = dh.kOperationModify
        hook.get_operation_state_info.return_value = state_info

        dh.ResourcePoolAssignment.check_dates_overlap_web(hook)

        hook_obj = _get_object_from_hook.return_value

        hook.get_operation_state_info.assert_called_once()
        _get_object_from_hook.assert_called_once_with(dh.ResourcePoolAssignment, hook)
        date_from_legacy_str.assert_has_calls(
            [call(obj.start_date), call(obj.end_date)]
        )
        hook_obj.check_dates_overlap.assert_called_once_with(
            date_from_legacy_str.return_value,
            date_from_legacy_str.return_value,
            _get_object_from_hook.return_value.start_date,
            _get_object_from_hook.return_value.end_date,
        )
