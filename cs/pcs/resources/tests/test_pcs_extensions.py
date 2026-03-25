#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest
from collections import defaultdict

import pytest
from mock import MagicMock, PropertyMock, patch

from cdb import testcase


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


@pytest.mark.unit
class TimeScheduleTestCase(testcase.RollbackTestCase):
    def test_mirror_attribute_changes_to_RS(self):
        from cs.pcs.resources import pcs_extensions
        ts = MagicMock(spec=pcs_extensions.TimeSchedule)
        rs = MagicMock()
        ts.CombinedResourceSchedules = [MagicMock(ResourceSchedule=rs)]
        ctx = MagicMock()
        ctx.dialog = {"name": "foo_changed", "subject_id": "bar", "subject_type": "baz", "cdb_project_id": "bam"}
        ctx.previous_values = {"name": "foo", "subject_id": "bar", "subject_type": "baz", "cdb_project_id": "bam"}
        with patch.object(pcs_extensions, "operation") as mock_op:
            pcs_extensions.TimeSchedule.mirror_attribute_changes_to_RS(ts, ctx)
        mock_op.assert_called_once_with(
            pcs_extensions.kOperationModify,
            rs,
            name="foo_changed"
        )


@pytest.mark.unit
class ProjectTestCase(testcase.RollbackTestCase):
    def test_project_get_demands(self):
        from cs.pcs.resources import schedule

        with patch.object(schedule, "instantiate_schedule_creator"):
            from cs.pcs.resources import pcs_extensions

            obj1 = MagicMock(hours=7, task_id="bass")
            obj2 = MagicMock(hours=11, task_id="bass")
            with patch.object(
                pcs_extensions.sqlapi, "RecordSet2", return_value=[obj1, obj2]
            ):
                # call method
                result = pcs_extensions.sig.emit("project_get_demands")("foo")

                # check calls
                pcs_extensions.sqlapi.RecordSet2.assert_called_once_with(
                    "cdbpcs_prj_demand", "cdb_project_id = 'foo'"
                )
                self.assertEqual(result, [defaultdict(bass=18)])

    def test_project_get_assignments(self):
        from cs.pcs.resources import schedule

        with patch.object(schedule, "instantiate_schedule_creator"):
            from cs.pcs.resources import pcs_extensions

            obj1 = MagicMock(hours=7, task_id="bass")
            obj2 = MagicMock(hours=11, task_id="bass")
            with patch.object(
                pcs_extensions.sqlapi, "RecordSet2", return_value=[obj1, obj2]
            ):
                # call method
                result = pcs_extensions.sig.emit("project_get_assignments")("foo")

                # check calls
                pcs_extensions.sqlapi.RecordSet2.assert_called_once_with(
                    "cdbpcs_prj_alloc", "cdb_project_id = 'foo'"
                )
                self.assertEqual(result, [defaultdict(bass=18)])

    def test_delete_resource_schedule_objects(self):
        from cs.pcs.resources import pcs_extensions

        ctx = MagicMock()
        d1 = MagicMock()
        d2 = MagicMock()
        a1 = MagicMock()
        a2 = MagicMock()

        with patch.object(
            pcs_extensions.Task,
            "RessourceDemands",
            new_callable=PropertyMock,
            return_value=[d1, d2],
        ):
            with patch.object(
                pcs_extensions.Task,
                "RessourceAssignments",
                new_callable=PropertyMock,
                return_value=[a1, a2],
            ):
                task = pcs_extensions.Task()
                pcs_extensions.delete_resource_schedule_objects(task, ctx)

        d1.deleteResourceScheduleObjects.assert_called_once_with()
        d2.deleteResourceScheduleObjects.assert_called_once_with()
        a1.deleteResourceScheduleObjects.assert_called_once_with()
        a2.deleteResourceScheduleObjects.assert_called_once_with()


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
