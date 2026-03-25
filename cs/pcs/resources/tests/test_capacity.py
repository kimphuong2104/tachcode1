#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access
# flake8: noqa

from datetime import date

import mock
import pytest

from cdb import testcase

# FIXME: importing from capacity already requires DB connection
testcase.run_level_setup()
from cs.pcs.resources import capacity

CADDOK = "99504583-76e1-11de-a2d5-986f0c508d59"


@pytest.mark.parametrize("capa_class,start,end,expected", [
    (capacity.CapacityScheduleHalfYear, date(2023, 2, 14), date(2023, 3, 15), (date(2023, 1, 1), date(2023, 6, 30))),
    (capacity.CapacityScheduleHalfYear, date(2023, 11, 14), date(2023, 12, 15), (date(2023, 7, 1), date(2023, 12, 31))),

    (capacity.CapacityScheduleQuarter, date(2023, 2, 14), date(2023, 3, 15), (date(2023, 1, 1), date(2023, 3, 31))),
    (capacity.CapacityScheduleQuarter, date(2023, 5, 14), date(2023, 6, 15), (date(2023, 4, 1), date(2023, 6, 30))),
    (capacity.CapacityScheduleQuarter, date(2023, 8, 14), date(2023, 9, 15), (date(2023, 7, 1), date(2023, 9, 30))),
    (capacity.CapacityScheduleQuarter, date(2023, 11, 14), date(2023, 12, 15), (date(2023, 10, 1), date(2023, 12, 31))),

    (capacity.CapacityScheduleMonth, date(2023, 1, 14), date(2023, 1, 15), (date(2023, 1, 1), date(2023, 1, 31))),
    (capacity.CapacityScheduleMonth, date(2023, 2, 14), date(2023, 2, 15), (date(2023, 2, 1), date(2023, 2, 28))),
    (capacity.CapacityScheduleMonth, date(2023, 3, 14), date(2023, 3, 15), (date(2023, 3, 1), date(2023, 3, 31))),
    (capacity.CapacityScheduleMonth, date(2023, 4, 14), date(2023, 4, 15), (date(2023, 4, 1), date(2023, 4, 30))),
    (capacity.CapacityScheduleMonth, date(2023, 5, 14), date(2023, 5, 15), (date(2023, 5, 1), date(2023, 5, 31))),
    (capacity.CapacityScheduleMonth, date(2023, 6, 14), date(2023, 6, 15), (date(2023, 6, 1), date(2023, 6, 30))),
    (capacity.CapacityScheduleMonth, date(2023, 7, 14), date(2023, 7, 15), (date(2023, 7, 1), date(2023, 7, 31))),
    (capacity.CapacityScheduleMonth, date(2023, 8, 14), date(2023, 8, 15), (date(2023, 8, 1), date(2023, 8, 31))),
    (capacity.CapacityScheduleMonth, date(2023, 9, 14), date(2023, 9, 15), (date(2023, 9, 1), date(2023, 9, 30))),
    (capacity.CapacityScheduleMonth, date(2023, 10, 14), date(2023, 10, 15), (date(2023, 10, 1), date(2023, 10, 31))),
    (capacity.CapacityScheduleMonth, date(2023, 11, 14), date(2023, 11, 15), (date(2023, 11, 1), date(2023, 11, 30))),
    (capacity.CapacityScheduleMonth, date(2023, 12, 14), date(2023, 12, 15), (date(2023, 12, 1), date(2023, 12, 31))),

    (capacity.CapacityScheduleWeek, date(2023, 10, 15), date(2023, 10, 15), (date(2023, 10, 9), date(2023, 10, 15))),
    (capacity.CapacityScheduleWeek, date(2023, 10, 16), date(2023, 10, 16), (date(2023, 10, 16), date(2023, 10, 22))),
    (capacity.CapacityScheduleWeek, date(2023, 10, 17), date(2023, 10, 17), (date(2023, 10, 16), date(2023, 10, 22))),
    (capacity.CapacityScheduleWeek, date(2023, 10, 18), date(2023, 10, 18), (date(2023, 10, 16), date(2023, 10, 22))),
    (capacity.CapacityScheduleWeek, date(2023, 10, 19), date(2023, 10, 19), (date(2023, 10, 16), date(2023, 10, 22))),
    (capacity.CapacityScheduleWeek, date(2023, 10, 20), date(2023, 10, 20), (date(2023, 10, 16), date(2023, 10, 22))),
    (capacity.CapacityScheduleWeek, date(2023, 10, 21), date(2023, 10, 21), (date(2023, 10, 16), date(2023, 10, 22))),
    (capacity.CapacityScheduleWeek, date(2023, 10, 22), date(2023, 10, 22), (date(2023, 10, 16), date(2023, 10, 22))),
    (capacity.CapacityScheduleWeek, date(2023, 10, 23), date(2023, 10, 23), (date(2023, 10, 23), date(2023, 10, 29))),
])
def test_GetStartAndEnd(capa_class, start, end, expected):
    assert capa_class.GetStartAndEnd(start, end) == expected


@pytest.mark.parametrize("capa_class,start_and_end", [
    (capacity.CapacityScheduleHalfYear, 1),
    (capacity.CapacityScheduleQuarter, 1),
    (capacity.CapacityScheduleMonth, 1),
    (capacity.CapacityScheduleWeek, 1),
    (capacity.CapacityScheduleDay, 0),
])
def test_RecreateCapacitySchedule(capa_class, start_and_end):
    calculator = mock.Mock(
        __sql_first_of_halfyear__=mock.Mock(),
        __sql_first_of_quarter__=mock.Mock(),
        __sql_first_of_month__=mock.Mock(),
        __sql_first_of_week__=mock.Mock(),
        __sql_capacity_base__=mock.Mock(),
    )

    with (
        mock.patch.object(capa_class, "GetStartAndEnd", create=True, return_value="se") as GetStartAndEnd,
        mock.patch.object(capacity.sqlapi, "SQLinsert") as SQLinsert,
        mock.patch.object(capacity.sqlapi, "SQLdelete") as SQLdelete,
    ):
        capa_class.RecreateCapacitySchedule(calculator, "AB", "S", "E")

    assert GetStartAndEnd.call_count == start_and_end
    assert calculator.get_query_stmt.call_count == 2
    SQLdelete.assert_called_once()
    SQLinsert.assert_called_once()


@pytest.mark.integration
class CapacityCalculator(testcase.RollbackTestCase):
    # "wrapping" mocks lets us make assertions, but still runs the wrapped implementation
    @mock.patch.object(capacity.sqlapi, "SQLinsert", wraps=capacity.sqlapi.SQLinsert)
    @mock.patch.object(capacity.sqlapi, "SQLdelete", wraps=capacity.sqlapi.SQLdelete)
    def test_createSchedules_no_args(self, SQLdelete, SQLinsert):
        capacity.CAPACITY_CALCULATOR.createSchedules()
        SQLdelete.assert_not_called()
        SQLinsert.assert_not_called()

    @mock.patch.object(capacity.sqlapi, "SQLinsert", wraps=capacity.sqlapi.SQLinsert)
    @mock.patch.object(capacity.sqlapi, "SQLdelete", wraps=capacity.sqlapi.SQLdelete)
    def test_createSchedules_no_dates(self, SQLdelete, SQLinsert):
        capacity.CAPACITY_CALCULATOR.createSchedules([CADDOK])
        self.assertEqual(SQLdelete.call_count, 5)
        self.assertEqual(SQLinsert.call_count, 5)
        SQLdelete.assert_has_calls(
            [
                mock.call(
                    f"FROM cdbpcs_capa_sched_pd WHERE resource_oid IN ('{CADDOK}')"
                ),
                mock.call(
                    f"FROM cdbpcs_capa_sched_pw WHERE resource_oid IN ('{CADDOK}')"
                ),
                mock.call(
                    f"FROM cdbpcs_capa_sched_pm WHERE resource_oid IN ('{CADDOK}')"
                ),
                mock.call(
                    f"FROM cdbpcs_capa_sched_pq WHERE resource_oid IN ('{CADDOK}')"
                ),
                mock.call(
                    f"FROM cdbpcs_capa_sched_ph WHERE resource_oid IN ('{CADDOK}')"
                ),
            ]
        )

    @mock.patch.object(capacity.sqlapi, "SQLinsert", wraps=capacity.sqlapi.SQLinsert)
    @mock.patch.object(capacity.sqlapi, "SQLdelete", wraps=capacity.sqlapi.SQLdelete)
    def test_createSchedules_dates(self, SQLdelete, SQLinsert):
        day = date(2023, 2, 14)
        day_str = capacity.sqlapi.SQLdate_literal(day)
        capacity.CAPACITY_CALCULATOR.createSchedules([CADDOK], start=day, end=day)
        self.assertEqual(SQLdelete.call_count, 5)
        self.assertEqual(SQLinsert.call_count, 5)
        SQLdelete.assert_has_calls(
            [
                mock.call(
                    f"FROM cdbpcs_capa_sched_pd WHERE resource_oid IN ('{CADDOK}') "
                    f"AND day >= {day_str} "
                    f"AND day <= {day_str}"
                ),
                mock.call(
                    f"FROM cdbpcs_capa_sched_pw WHERE resource_oid IN ('{CADDOK}') "
                    f"AND day >= {capacity.sqlapi.SQLdate_literal(date(2023, 2, 13))} "
                    f"AND day <= {capacity.sqlapi.SQLdate_literal(date(2023, 2, 19))}"
                ),
                mock.call(
                    f"FROM cdbpcs_capa_sched_pm WHERE resource_oid IN ('{CADDOK}') "
                    f"AND day >= {capacity.sqlapi.SQLdate_literal(date(2023, 2, 1))} "
                    f"AND day <= {capacity.sqlapi.SQLdate_literal(date(2023, 2, 28))}"
                ),
                mock.call(
                    f"FROM cdbpcs_capa_sched_pq WHERE resource_oid IN ('{CADDOK}') "
                    f"AND day >= {capacity.sqlapi.SQLdate_literal(date(2023, 1, 1))} "
                    f"AND day <= {capacity.sqlapi.SQLdate_literal(date(2023, 3, 31))}"
                ),
                mock.call(
                    f"FROM cdbpcs_capa_sched_ph WHERE resource_oid IN ('{CADDOK}') "
                    f"AND day >= {capacity.sqlapi.SQLdate_literal(date(2023, 1, 1))} "
                    f"AND day <= {capacity.sqlapi.SQLdate_literal(date(2023, 6, 30))}"
                ),
            ]
        )
