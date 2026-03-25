#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest

import mock
import pytest
from cdb import testcase

from cs.pcs.projects import calendar


@pytest.mark.unit
class CalendarProfile(testcase.RollbackTestCase):
    @mock.patch("cs.pcs.projects.tasks.Task")
    def test_on_cdb_recalculate_projects_now_unknown_classname(self, Task):
        calprof = mock.MagicMock(spec=calendar.CalendarProfile)
        ctx = mock.MagicMock()
        self.assertIsNone(
            calendar.CalendarProfile.on_cdb_recalculate_projects_now(calprof, ctx)
        )
        Task.adjustDependingObjects_many.assert_not_called()

    @mock.patch("cs.pcs.projects.tasks.Task")
    def test_on_cdb_recalculate_projects_now_calprof(self, Task):
        p1 = mock.MagicMock(Tasks=["1.1", "1.2"])
        p2 = mock.MagicMock(Tasks=["2.1"])
        p1.checkProjectCalendarDates.return_value = False
        p2.checkProjectCalendarDates.return_value = False
        calprof = mock.MagicMock(
            spec=calendar.CalendarProfile,
            Projects=[p1, p2],
        )
        ctx = mock.MagicMock(classname="cdb_calendar_profile")
        self.assertIsNone(
            calendar.CalendarProfile.on_cdb_recalculate_projects_now(calprof, ctx)
        )

        p1.recalculate.assert_called_once_with()
        p2.recalculate.assert_called_once_with()
        Task.adjustDependingObjects_many.assert_called_once_with(["1.1", "1.2", "2.1"])

    @mock.patch("cs.pcs.projects.tasks.Task")
    def test_on_cdb_recalculate_projects_now_calprof_wrong_dates(self, Task):
        p1 = mock.MagicMock(Tasks=["1.1", "1.2"])
        p2 = mock.MagicMock(Tasks=["2.1"])
        p1.checkProjectCalendarDates.return_value = False
        p2.GetDescription.return_value = "P2"
        calprof = mock.MagicMock(
            spec=calendar.CalendarProfile,
            Projects=[p1, p2],
        )
        ctx = mock.MagicMock(classname="cdb_calendar_profile")
        with self.assertRaises(calendar.ue.Exception) as error:
            calendar.CalendarProfile.on_cdb_recalculate_projects_now(calprof, ctx)

        self.assertEqual(
            str(error.exception),
            "Die folgenden Projekte entsprechen "
            "nicht dem ausgewählten Kalenderprofil:\\nP2",
        )

        p1.recalculate.assert_called_once_with()
        p2.recalculate.assert_not_called()
        Task.adjustDependingObjects_many.assert_called_once_with(["1.1", "1.2"])

    @mock.patch("cs.pcs.projects.tasks.Task")
    @mock.patch("cs.pcs.projects.Project")
    def test_on_cdb_recalculate_projects_now_proj(self, Project, Task):
        p1 = mock.MagicMock(Tasks=["1.1", "1.2"])
        p2 = mock.MagicMock(Tasks=["2.1"])
        Project.ByKeys.side_effect = [p1, p2]
        calprof = mock.MagicMock(spec=calendar.CalendarProfile)
        ctx = mock.MagicMock(
            classname="cdbpcs_project",
            objects=[
                mock.Mock(cdb_project_id="pid1"),
                mock.Mock(cdb_project_id="pid2"),
            ],
        )
        self.assertIsNone(
            calendar.CalendarProfile.on_cdb_recalculate_projects_now(calprof, ctx)
        )

        p1.recalculate.assert_called_once_with()
        p2.recalculate.assert_called_once_with()
        Task.adjustDependingObjects_many.assert_called_once_with(["1.1", "1.2", "2.1"])


if __name__ == "__main__":
    unittest.main()
