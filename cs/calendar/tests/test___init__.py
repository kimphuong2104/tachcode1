#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import datetime, six, unittest
from cdb import sqlapi, testcase
import cs.calendar as calendar

if six.PY2:
    import mock
else:
    from unittest import mock

LAST_FRIDAY = datetime.date(2022, 8, 5)
LAST_SUNDAY = datetime.date(2022, 8, 6)
MONDAY = datetime.date(2022, 8, 8)
NEXT_MONDAY = datetime.date(2022, 8, 15)
MONDAY_TIME = datetime.datetime(2022, 8, 8, 1, 2, 3)
MONDAY_LEGACY = "08.08.2022 10:11:12"
PROFILE = "1cb4cf41-0f40-11df-a6f9-9435b380e702"


class Utility(unittest.TestCase):
    maxDiff = None

    def test_lose_time_info_none(self):
        with self.assertRaises(ValueError):
            calendar.lose_time_info(None)

    def test_lose_time_info_str(self):
        with self.assertRaises(ValueError):
            calendar.lose_time_info("09.08.2022")

    def test_lose_time_info_d(self):
        self.assertEqual(calendar.lose_time_info(MONDAY), MONDAY)

    def test_lose_time_info_dt(self):
        self.assertEqual(calendar.lose_time_info(MONDAY_TIME), MONDAY)

    def test_make_sql_date_invalid_str(self):
        with self.assertRaises(ValueError):
            calendar.make_sql_date("not a legacy date")

    def test_make_sql_date_no_date(self):
        with self.assertRaises(ValueError):
            calendar.make_sql_date(42)

    @mock.patch.object(calendar.sqlapi, "SQLdbms_date")
    def test_make_sql_date_legacy_str(self, sqldate):
        self.assertEqual(
            calendar.make_sql_date(MONDAY_LEGACY),
            sqldate.return_value,
        )
        sqldate.assert_called_once_with(MONDAY)

    @mock.patch.object(calendar.sqlapi, "SQLdbms_date")
    def test_make_sql_date_d(self, sqldate):
        self.assertEqual(
            calendar.make_sql_date(MONDAY),
            sqldate.return_value,
        )
        sqldate.assert_called_once_with(MONDAY)

    @mock.patch.object(calendar.sqlapi, "SQLdbms_date")
    def test_make_sql_date_dt(self, sqldate):
        self.assertEqual(
            calendar.make_sql_date(MONDAY_TIME),
            sqldate.return_value,
        )
        sqldate.assert_called_once_with(MONDAY)

    def test_getNextStartDate_empty_date(self):
        self.assertEqual(
            calendar.getNextStartDate(PROFILE, ""),
            "",
        )

    def test_getNextStartDate_dt(self):
        self.assertEqual(
            calendar.getNextStartDate(PROFILE, MONDAY_TIME, -1),
            LAST_FRIDAY,
        )

    def test_getNextStartDate_distance_0(self):
        self.assertEqual(
            calendar.getNextStartDate(PROFILE, MONDAY),
            MONDAY,
        )

    def test_getNextStartDate_distance_0_weekend(self):
        self.assertEqual(
            calendar.getNextStartDate(PROFILE, LAST_SUNDAY),
            MONDAY,
        )

    def test_getNextStartDate_out_of_range(self):
        with self.assertRaises(calendar.ue.Exception) as error:
            calendar.getNextStartDate(PROFILE, MONDAY_TIME, 999999)

        self.assertEqual(
            str(error.exception),
            "Das eingegebene Datum liegt außerhalb "
            "der Gültigkeit des Kalenderprofils.\\n"
            "Bitte geben Sie ein gültiges Datum ein oder "
            "informieren Sie ihren Systemadministrator."
        )

    def test_getNextEndDate_empty_date(self):
        self.assertEqual(
            calendar.getNextEndDate(PROFILE, ""),
            "",
        )

    def test_getNextEndDate_dt(self):
        self.assertEqual(
            calendar.getNextEndDate(PROFILE, MONDAY_TIME, 5),
            NEXT_MONDAY,
        )

    def test_getPersonalWorkdays(self):
        self.assertEqual(
            calendar.getPersonalWorkdays(["caddok"], MONDAY, NEXT_MONDAY),
            {
                "caddok": [
                    (MONDAY, "Arbeitstag"),
                    (datetime.date(2022, 8, 9), "Arbeitstag"),
                    (datetime.date(2022, 8, 10), "Arbeitstag"),
                    (datetime.date(2022, 8, 11), "Arbeitstag"),
                    (datetime.date(2022, 8, 12), "Arbeitstag"),
                    (NEXT_MONDAY, "Arbeitstag"),
                ],
            }
        )

    def test_getPersonalDaysOff(self):
        self.assertEqual(
            calendar.getPersonalDaysOff(["caddok"], MONDAY, NEXT_MONDAY),
            {
                "caddok": [
                    (datetime.date(2022, 8, 13), "Wochenende"),
                    (datetime.date(2022, 8, 14), "Wochenende"),
                ],
            }
        )


class UtilityIntegration(testcase.RollbackTestCase):
    def _setup_personal_capa(self):
        """
        set up three users for this test:

        1. caddok (Standard calendar profile, capacity of 2)
        2. vendorsupport (no calendar profile, irrelevant capacity of 3)
        3. cs.dcs.service (Standard calendar profile, no capacity)
        """
        # Standard calendar profile
        cal_prof = "1cb4cf41-0f40-11df-a6f9-9435b380e702"

        for login, cal, capa in [
            ("caddok", cal_prof, 2),
            ("vendorsupport", "", 3),
            ("cs.dcs.service", cal_prof, 0),
        ]:
            sqlapi.SQLupdate(
                "angestellter"
                " SET org_id='testorg', is_resource=1,"
                " capacity={}, calendar_profile_id='{}'"
                " WHERE login='{}'".format(capa, cal, login)
            )

    def test_getPersonalCapacities_org_ids(self):
        self._setup_personal_capa()
        self.assertDictEqual(
            calendar.getPersonalCapacities(
                datetime.date(2022, 12, 29),
                datetime.date(2023, 1, 3),
                list_of_orgs=["testorg", "unknown org"],
            ),
            {
                "caddok": [2.0, 2.0, 0.0, 0.0, 2.0, 2.0],
                "cs.dcs.service": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            }
        )

    def test_getPersonalCapacities_user_ids(self):
        self._setup_personal_capa()
        self.assertDictEqual(
            calendar.getPersonalCapacities(
                datetime.date(2022, 12, 29),
                datetime.date(2023, 1, 3),
                list_of_persnr=["caddok", "vendorsupport", "unknown user"],
            ),
            {
                "caddok": [2.0, 2.0, 0.0, 0.0, 2.0, 2.0],
            }
        )

    def test_getPersonalCapacities_both_id_lists(self):
        self._setup_personal_capa()
        self.assertDictEqual(
            calendar.getPersonalCapacities(
                datetime.date(2022, 12, 29),
                datetime.date(2023, 1, 3),
                list_of_orgs=["testorg", "unknown org"],
                list_of_persnr=["caddok", "unknown user"],
            ),
            {
                "caddok": [2.0, 2.0, 0.0, 0.0, 2.0, 2.0],
                "cs.dcs.service": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            }
        )


if __name__ == "__main__":
    unittest.main()
