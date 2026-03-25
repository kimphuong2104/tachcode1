#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import mock
import pytest

from cs.pcs.projects.project_structure import util
from cs.pcs.timeschedule.web import baseline_helpers


@pytest.mark.unit
class TimeScheduleProjectView(unittest.TestCase):
    @mock.patch.object(baseline_helpers.sqlapi, "RecordSet2")
    def test_get_project(self, RecordSet2):
        RecordSet2.return_value = [1]
        self.assertEqual(baseline_helpers.get_project("id1"), 1)
        RecordSet2.assert_called_once_with(
            sql=baseline_helpers.PROJECT_SQL.format("id1")
        )

    @mock.patch.object(baseline_helpers.sqlapi, "RecordSet2")
    def test_get_baselined_task(self, RecordSet2):
        RecordSet2.return_value = [1]
        self.assertEqual(baseline_helpers.get_baselined_task("id1", "blid1"), 1)
        RecordSet2.assert_called_once_with(
            sql=baseline_helpers.BASELINED_TASK_SQL.format("id1", "blid1")
        )

    def test_get_requested_baseline(self):
        request = mock.MagicMock(json={})
        pid = "pid1"
        self.assertEqual(baseline_helpers.get_requested_baseline(pid, request), None)
        request = mock.MagicMock(json={"selectedBaselines": {"pid1": "blid1"}})
        self.assertEqual(baseline_helpers.get_requested_baseline(pid, request), "blid1")

    @mock.patch.object(baseline_helpers, "get_tasks_data")
    def test_merge_with_baseline(self, get_tasks_data):
        pcs_levels = [
            util.PCS_LEVEL("P_oid", "cdbpcs_project", 1),
            util.PCS_LEVEL("t1_oid", "cdbpcs_task", 2),
            util.PCS_LEVEL("t2_oid", "cdbpcs_task", 2),
        ]
        bl_levels = [
            util.PCS_LEVEL("t2_oid", "cdbpcs_task", 2),
            util.PCS_LEVEL("t3_oid", "cdbpcs_task", 2),
        ]
        pcs_data = (
            {"t1_oid": ("P1", "", "T1", 10), "t2_oid": ("P1", "", "T2", 20)},
            {"P1@T1": "t1_oid", "P1@T2": "t2_oid"},
        )
        bl_data = (
            {"t2_oid": ("P1", "", "T2", 20), "t3_oid": ("P1", "", "T3", 30)},
            {"P1@T2": "t2_oid", "P1@T3": "t3_oid"},
        )
        get_tasks_data.side_effect = [pcs_data, bl_data]

        expected = [
            util.PCS_LEVEL("P_oid", "cdbpcs_project", 1),
            util.PCS_LEVEL("t1_oid", "cdbpcs_task", 2),
            util.PCS_LEVEL("t2_oid", "cdbpcs_task", 2, "t2_oid"),
            util.PCS_LEVEL("t3_oid", "cdbpcs_task", 2),
        ]

        self.assertEqual(
            baseline_helpers.merge_with_baseline(pcs_levels, bl_levels, "P1@"), expected
        )


if __name__ == "__main__":
    unittest.main()
