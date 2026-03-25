#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import datetime, six, unittest
from cs.calendar import workday

LAST_FRIDAY = datetime.date(2022, 8, 5)
MONDAY = datetime.date(2022, 8, 8)
LAST_FRIDAY_TIME = datetime.datetime(2022, 8, 5, 6, 5, 4)
MONDAY_TIME = datetime.datetime(2022, 8, 8, 1, 2, 3)


class Utility(unittest.TestCase):
    maxDiff = None

    def test_workdays_dt(self):
        self.assertEqual(
            workday.workdays(LAST_FRIDAY, MONDAY_TIME),
            [LAST_FRIDAY, MONDAY],
        )

    def test_personal_workdays_dt(self):
        self.assertEqual(
            workday.personal_workdays("caddok", LAST_FRIDAY, MONDAY_TIME),
            [LAST_FRIDAY, MONDAY],
        )

    def test_next_workday_date(self):
        self.assertEqual(workday.next_workday(LAST_FRIDAY, 1), MONDAY)

    def test_next_workday_datetime(self):
        self.assertEqual(workday.next_workday(LAST_FRIDAY_TIME, 1), MONDAY)

    def test_next_workday_de(self):
        self.assertEqual(workday.next_workday(LAST_FRIDAY, 1, "de"), MONDAY)

    def test_next_personal_workday_dt(self):
        self.assertEqual(
            workday.next_personal_workday("caddok", MONDAY_TIME, -3),
            LAST_FRIDAY,
        )


class GetIndexOfDay(unittest.TestCase):
    def _giod(self, days, day, next_val, expected_result, msg):
        the_day = datetime.datetime.strptime(day, '%d.%m.%Y')
        all_days = [datetime.datetime.strptime(d, '%d.%m.%Y') for d in days]
        result = workday.get_index_of_day(the_day, all_days, next_val)
        self.assertEqual(
            expected_result, result,
            "%s:Got %d instead of %d" % (msg, result, expected_result))

    def test_get_index_of_day_empty_list(self):
        """
        Test for workday.get_index_of_day with empty daylist
        """
        self._giod([], "15.07.2013", 0,
                   -1, "Empty list without next value.")
        self._giod([], "15.07.2013", 1,
                   -1, "Empty list with next=1.")
        self._giod([], "15.07.2013", -1,
                   -1, "Empty list with next=-1.")

    def _test_find_day(self, days):
        """
        Calls the test for every day in days
        """
        msg = "Find day in list of %d elements" % len(days)
        for d in six.moves.range(0, len(days)):
            self._giod(days, days[d], 0,
                       d, msg)
            self._giod(days, days[d], 1,
                       d, msg + " (next = 1)")
            self._giod(days, days[d], -1,
                       d, msg + " (next = -1)")

    def test_get_index_of_day_one_day_list(self):
        """
        Test for workday.get_index_of_day with a list that
        contains exactly one day.
        """
        days = ["15.07.2013"]
        self._test_find_day(days)
        self._giod(days, "16.07.2013", 0,
                   -1, "Find not existing day in an One-Day-List")
        self._giod(days, "16.07.2013", 1,
                   0, "Find not existing day in an One-Day-List with next=1.")
        self._giod(days, "16.07.2013", -1,
                   0, "Find not existing day in an One-Day-List with next=-1.")
        self._giod(days, "10.07.2013", 0,
                   -1, "Find not existing day in an One-Day-List")
        self._giod(days, "10.07.2013", 1,
                   0, "Find not existing day in an One-Day-List with next=1.")
        self._giod(days, "10.07.2013", -1,
                   0, "Find not existing day in an One-Day-List with next=-1.")

    def test_get_index_of_day(self):
        """
        Test for `workday.get_index_of_day` with a list that
        contains several elmenents.
        """
        days = ["01.07.2013",
                "05.07.2013",
                "09.07.2013",
                "14.07.2013",
                "19.07.2013"]
        # Find the days
        self._test_find_day(days)
        # Search for a day that is not part of the list
        # 1. A day before the first entry
        self._giod(days, "01.01.2013", 0,
                   -1, "Find not existing day in list")
        self._giod(days, "01.01.2013", 1,
                   0, "Find a date before days withe next = 1")
        self._giod(days, "01.01.2013", 1,
                   0, "Find a date before days withe next = -1")
        # 2. A day after the last entry
        self._giod(days, "01.12.2013", 0,
                   -1, "Find not existing day in list")
        self._giod(days, "01.12.2013", 1,
                   4, "Find a date after days with next = 1")
        self._giod(days, "01.12.2013", -1,
                   4, "Find a date after days with next = -1")
        # 3. A day in the middle
        self._giod(days, "06.07.2013", 0,
                   -1, "Find not existing day in list")
        self._giod(days, "06.07.2013", 1,
                   2, "Find a date after days with next = 1")
        self._giod(days, "06.07.2013", -1,
                   1, "Find a date after days with next = -1")


if __name__ == "__main__":
    unittest.main()
