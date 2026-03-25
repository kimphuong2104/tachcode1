#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


import unittest

import mock
from cdb import testcase

from cs.pcs.projects.web import dialog_hooks


def _setup_hook(with_bid=False):
    # setup mock hook for testing
    hook = mock.MagicMock()
    hook.get_new_values.return_value = [
        "foo_unused",
        "bar.unused",
        "cdbpcs_task.cdb_project_id",
        "cdbpcs_task.task_id",
    ]
    if with_bid:
        hook.get_new_values.return_value.append("cdbpcs_task.ce_baseline_id")
    hook.get_new_value.side_effect = lambda key: key.upper()
    return hook


class Hook(testcase.RollbackTestCase):
    @mock.patch.object(dialog_hooks.Task, "ByKeys", return_value=None)
    def test_task_create_from_template_with_bid_no_task(self, ByKeys):
        # hook's dialog has bid
        hook = _setup_hook(True)

        dialog_hooks.task_create_from_template(hook)

        hook.get_new_value.assert_has_calls(
            [
                mock.call("cdb_project_id"),
                mock.call("task_id"),
                mock.call("ce_baseline_id"),
            ]
        )
        ByKeys.assert_called_once_with(
            cdb_project_id="CDB_PROJECT_ID",
            task_id="TASK_ID",
            ce_baseline_id="CE_BASELINE_ID",
        )

    @mock.patch.object(dialog_hooks.Task, "ByKeys", return_value=None)
    def test_task_create_from_template_without_bid_no_task(self, ByKeys):
        # hook's dialog has not bid
        hook = _setup_hook()

        dialog_hooks.task_create_from_template(hook)

        hook.get_new_value.assert_has_calls(
            [
                mock.call("cdb_project_id"),
                mock.call("task_id"),
            ]
        )
        ByKeys.assert_called_once_with(
            cdb_project_id="CDB_PROJECT_ID", task_id="TASK_ID"
        )

    @mock.patch.object(dialog_hooks.Task, "ByKeys")
    def test_task_create_from_template_start_time_fcast(self, ByKeys):
        # Found Task has start_time_fcast
        hook = _setup_hook()

        dialog_hooks.task_create_from_template(hook)

        hook.get_new_value.assert_has_calls(
            [
                mock.call("cdb_project_id"),
                mock.call("task_id"),
            ]
        )
        ByKeys.assert_called_once_with(
            cdb_project_id="CDB_PROJECT_ID", task_id="TASK_ID"
        )
        hook.set.assert_called_once_with(
            ".start_time_old",
            ByKeys.return_value.start_time_fcast.isoformat.return_value,
        )
        hook.set_writeable.assert_called_once_with(".start_time_new")
        hook.set_mandatory.assert_called_once_with(".start_time_new")
        ByKeys.return_value.start_time_fcast.isoformat.assert_called_once()

    @mock.patch.object(dialog_hooks.Task, "ByKeys")
    def test_task_create_from_template_no_start_time_fcast(self, ByKeys):
        # Found Task has not start_time_fcast
        hook = _setup_hook()
        ByKeys.return_value.start_time_fcast = None

        dialog_hooks.task_create_from_template(hook)

        hook.get_new_value.assert_has_calls(
            [
                mock.call("cdb_project_id"),
                mock.call("task_id"),
            ]
        )
        ByKeys.assert_called_once_with(
            cdb_project_id="CDB_PROJECT_ID", task_id="TASK_ID"
        )
        hook.set_readonly.assert_called_once_with(".start_time_new")
        hook.set_optional.assert_called_once_with(".start_time_new")


if __name__ == "__main__":
    unittest.main()
