#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest
from datetime import date, datetime
from cdb import sqlapi, testcase, transactions


def items_equal(xs, ys):
    if isinstance(xs, dict) and isinstance(ys, dict):
        if len(xs) != len(ys):
            return False
        for key in xs.keys():
            try:
                if not items_equal(xs[key], ys[key]):
                    return False
            except KeyError:
                return False
        return True
    elif isinstance(xs, list) and isinstance(ys, list):
        if len(xs) != len(ys):
            return False
        sxs = xs
        sys = ys
        try:
            sxs = sorted(xs)
            sys = sorted(ys)
            for x, y in zip(sxs, sys):
                if not items_equal(x, y):
                    return False
        except TypeError:
            ys_copy = ys.copy()
            for x in xs:
                matches = [i for i, y in enumerate(ys_copy) if items_equal(x, y)]
                if len(matches):
                    del ys_copy[matches[0]]
                    continue
                else:
                    return False
        return True
    else:
        return xs == ys


class ViewPersonCalendarIntegration(testcase.RollbackTestCase):
    """
    Each ``cdb_calendar_entry`` row (if created via official means) is exactly one of the following:

    1. A project-specific entry (if ``cdb_project_id > ''``).
        This type of entry is not analyzed here.
    2. A personal exception (if ``personalnummer > ''``).
        These entries should have empty strings in ``calendar_profile_id`` and ``cdb_project_id``.
        They overrule the day type and capacity for a specific user and day.
    3. A "regular" entry (if ``calendar_profile_id > ''``).
        These entries should have ``NULL`` values in ``personalnummer``, ``cdb_project_id`` and ``capacity``.
        They determine day types for profiles (and by reference, users for which the profile applies).

    Personal calendars (``cdb_person_calendar_v``) work like this:

    1. There is at most one relevant entry for each person and day
    2. Regular entries are overruled by personal exceptions for the same day
    3. Project-specific calendar entries are ignored
    4. Persons without a calendar profile do not have a personal calendar
    5. (quirk) Entries with both ``personalnummer`` and ``calendar_profile_id``
       count as regular entries for all users sharing the same profile.
       This kind of entry is classified as broken data.

    Personal calendars also include a capacity value per day:

    1. On regular workdays, the person is available to its full capacity
    2. On regular non-workdays, the capacity is always 0
    3. Personal exceptions always overrule with its own capacity value
    """
    maxDiff = None
    PREFIX = "###"
    USERS = [
        ("u_p", "prf", 1.00),  # user with profile
        ("u_nc", "prf", None),  # user with profile but no capa
        ("u_np", "", 2.00),  # user without profile
    ]

    @classmethod
    def _user(cls, user_id, profile, capacity):
        sqlapi.Record(
            "angestellter",
            personalnummer=user_id,
            cdb_object_id=user_id,
            capacity=capacity,
            calendar_profile_id=profile,
            org_id="foo",
        ).insert()

    def _cal_entry(self, _uuid, day, user_id, project_id, day_type, profile,
                   capacity):
        uuid = "{} {}".format(self.PREFIX, _uuid)
        sqlapi.Record(
            "cdb_calendar_entry",
            cdb_object_id=uuid,
            day=day,
            personalnummer=user_id,
            cdb_project_id=project_id,
            day_type_id=day_type,
            description=uuid,
            calendar_profile_id=profile,
            capacity=capacity,
        ).insert()

    def assertView(self, expected_rows):
        view_rows = list(sqlapi.RecordSet2(
            "cdb_person_calendar_v",
            "description LIKE '{}%'".format(self.PREFIX),
        ))
        # we do not sort explicitely, so order does not matter
        assert items_equal(view_rows, expected_rows)

    @classmethod
    def setUpClass(cls):
        super(ViewPersonCalendarIntegration, cls).setUpClass()
        with transactions.Transaction():
            for user in cls.USERS:
                cls._user(*user)

    @classmethod
    def tearDownClass(cls):
        super(ViewPersonCalendarIntegration, cls).tearDownClass()
        sqlapi.SQLdelete(
            "FROM angestellter WHERE personalnummer IN ('{}')".format(
                "', '".join([user[0] for user in cls.USERS])
            )
        )

    def test_regular(self):
        "regular entries"
        self._cal_entry("weekend", date(2023, 1, 8), None, None, 2, "prf", 1.08)
        self._cal_entry("workday", date(2023, 1, 9), None, None, 1, "prf", 1.09)
        self.assertView([
            {
                u'description': u'### weekend',
                u'day': datetime(2023, 1, 8, 0, 0),
                u'capacity': 0.00,
                u'personalnummer': u'u_p', u'org_id': u'foo', u'is_resource': None,
                u'day_type_id': u'2', u'day_off': 1,
            },
            {
                u'description': u'### weekend',
                u'day': datetime(2023, 1, 8, 0, 0),
                u'capacity': 0.00,
                u'personalnummer': u'u_nc', u'org_id': u'foo', u'is_resource': None,
                u'day_type_id': u'2', u'day_off': 1,
            },
            {
                u'description': u'### workday',
                u'day': datetime(2023, 1, 9, 0, 0),
                u'capacity': 1.00,
                u'personalnummer': u'u_p', u'org_id': u'foo', u'is_resource': None,
                u'day_type_id': u'1', u'day_off': 0,
            },
            {
                u'description': u'### workday',
                u'day': datetime(2023, 1, 9, 0, 0),
                u'capacity': 0.00,
                u'personalnummer': u'u_nc', u'org_id': u'foo', u'is_resource': None,
                u'day_type_id': u'1', u'day_off': 0,
            },
        ])

    def test_personal_exceptions(self):
        "personal exceptions"
        self._cal_entry("regular", date(2023, 1, 10), None, None, 1, "prf", 1.1)
        self._cal_entry("exception", date(2023, 1, 10), "u_p", None, 1, "", 10.0)
        self._cal_entry("regular off", date(2023, 1, 11), None, None, 2, "prf", 1.11)
        self._cal_entry("exception off", date(2023, 1, 11), "u_p", None, 2, "", 11.0)
        self.assertView([
            {
                u'description': u'### exception',
                u'day': datetime(2023, 1, 10, 0, 0),
                u'capacity': 10.0,
                u'personalnummer': u'u_p', u'org_id': u'foo', u'is_resource': None,
                u'day_type_id': u'1', u'day_off': 0,
            },
            {
                u'description': u'### regular',
                u'day': datetime(2023, 1, 10, 0, 0),
                u'capacity': 0.00,
                u'personalnummer': u'u_nc', u'org_id': u'foo', u'is_resource': None,
                u'day_type_id': u'1', u'day_off': 0,
            },
            {
                u'description': u'### exception off',
                u'day': datetime(2023, 1, 11, 0, 0),
                u'capacity': 11.0,
                u'personalnummer': u'u_p', u'org_id': u'foo', u'is_resource': None,
                u'day_type_id': u'2', u'day_off': 1,
            },
            {
                u'description': u'### regular off',
                u'day': datetime(2023, 1, 11, 0, 0),
                u'capacity': 0.00,
                u'personalnummer': u'u_nc', u'org_id': u'foo', u'is_resource': None,
                u'day_type_id': u'2', u'day_off': 1,
            },
        ])

    def test_other_entries(self):
        "ignore project-specific and broken entries"
        self._cal_entry("prj", date(2023, 1, 10), None, "prj", 1, "prf", 1.1)
        self._cal_entry("other_profile", date(2023, 1, 11), "u_p", None, 1, "p2", 1.11)
        self._cal_entry("no_profile", date(2023, 1, 12), "u_p", None, 1, None, 1.12)
        self._cal_entry("other_user", date(2023, 1, 13), "foo", None, 1, "prf", 1.13)

        # note: "other_user" appears because profile still matches;
        #       correct exceptional entries are not supposed to reference a profile
        self.assertView([
            {
                u'day': datetime(2023, 1, 13, 0, 0),
                u'description': u'### other_user',
                u'capacity': 1.00,
                u'personalnummer': u'u_p', u'org_id': u'foo', u'is_resource': None,
                u'day_type_id': u'1', u'day_off': 0,
            },
            {
                u'day': datetime(2023, 1, 13, 0, 0),
                u'description': u'### other_user',
                u'capacity': 0.00,
                u'personalnummer': u'u_nc', u'org_id': u'foo', u'is_resource': None,
                u'day_type_id': u'1', u'day_off': 0,
            },
        ])


if __name__ == "__main__":
    unittest.main()
