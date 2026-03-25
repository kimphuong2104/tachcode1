#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access


import unittest

import mock
import pytest
from cdb import testcase

from cs.pcs.projects import reports


@pytest.mark.unit
class TestProjectMTA(testcase.RollbackTestCase):
    @mock.patch.object(
        reports.ObjectQualityCharacteristic,
        "KeywordQuery",
        return_value=[
            mock.MagicMock(
                spec=reports.ObjectQualityCharacteristic,
                cdb_object_id="QC",
            ),
        ],
    )
    def test_getData(self, _):
        "E068935: make sure date comparisons work"
        x = mock.MagicMock(
            spec=reports.ProjectMTA,
            _date_format=reports.ProjectMTA._date_format,
        )
        x.getIntervalMatchingDate = lambda *args: args[0]
        parent_result = mock.MagicMock(spec=reports.PowerReports.ReportData)
        parent_result.getObject.return_value = mock.MagicMock(
            start_time_fcast=reports.datetime.date(2022, 9, 18),
            end_time_fcast=reports.datetime.date(2022, 9, 19),
            Milestones=[
                mock.MagicMock(end_time_act="21.09.2022"),
                mock.MagicMock(end_time_act="22.09.2022"),
            ],
        )
        args = {
            "map_mode": 0,
            "time_window_mode": 0,
            "update_clock": 10,
        }
        result = reports.ProjectMTA.getData(x, parent_result, args)
        self.assertEqual(
            [dict(x) for x in result],
            [
                {
                    "ms_date": "18.09.2022",
                    "ms_name": "Verlauf",
                    "report_date": "18.09.2022",
                },
                {
                    "ms_date": "19.09.2022",
                    "ms_name": "Verlauf",
                    "report_date": "19.09.2022",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
