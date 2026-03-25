#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access
import datetime
import unittest

import mock
import pytest

from cdb import testcase
from cs.pcs.costs import reports
from cs.pcs.costs.sheets import CostPosition, CostSheet
from cs.pcs.projects import Project


@pytest.mark.unit
class TestCostTrends(testcase.RollbackTestCase):
    def test_getData(self):
        x = mock.MagicMock(spec=reports.CostTrends)
        parent_result = mock.MagicMock(spec=reports.PowerReports.ReportData)
        positions = [
            mock.MagicMock(
                spec=CostPosition,
                costs=50.0,
                hourly_rate=10.0,
                effort=5.0,
                costs_proj_curr=50.0,
                start_time=datetime.date(2022, 11, 12),
                end_time=datetime.date(2022, 11, 15),
            ),
            mock.MagicMock(
                spec=CostPosition,
                costs=6.0,
                hourly_rate=3.0,
                effort=2.0,
                costs_proj_curr=6.0,
                start_time=datetime.date(2022, 11, 19),
                end_time=datetime.date(2022, 11, 20),
            ),
        ]
        valid_cost_sheets = [mock.MagicMock(spec=CostSheet, Positions=positions)]
        prj = mock.MagicMock(spec=Project, ValidCostSheets=valid_cost_sheets)
        sheet = mock.MagicMock(spec=CostSheet, Project=prj)
        sheet.Positions.Query.return_value = positions
        parent_result.getObject.return_value = sheet
        result = reports.CostTrends.getData(x, parent_result, {})
        self.assertEqual(
            [dict(x) for x in result],
            [{"costs": 56.0, "effort": 7.0, "monthyear": "11.2022"}],
        )


if __name__ == "__main__":
    unittest.main()
