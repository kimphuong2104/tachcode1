#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest
from datetime import date

import mock
import pytest

from cdb import sqlapi, testcase
from cs.taskmanager import conditions


def setUpModule():
    testcase.run_level_setup()


@pytest.mark.unit
class ConditionsUnit(unittest.TestCase):
    def test_parse_date_None(self):
        self.assertIsNone(conditions.parse_date(None))

    def test_parse_date_no_str(self):
        self.assertIsNone(conditions.parse_date(42))

    def test_parse_date_invalid(self):
        self.assertIsNone(conditions.parse_date("1-2-3-4-"))

    def test_parse_date_date_only(self):
        self.assertEqual(
            conditions.parse_date("2021-04-01"),
            date(2021, 4, 1),
        )

    def test_parse_date_datetime(self):
        self.assertEqual(
            conditions.parse_date("2021-04-01T11"),
            date(2021, 4, 1),
        )

    def test_parse_date_datetime_seconds(self):
        self.assertEqual(
            conditions.parse_date("2021-04-01T10:11:12"),
            date(2021, 4, 1),
        )

    @mock.patch.object(conditions.UserSubstitute, "get_substituted_users")
    @mock.patch.object(conditions.cdbwrapc, "clearUserSubstituteCache")
    @mock.patch.object(conditions, "auth")
    def test_get_substitutes(self, auth, clear_cache, get_subs):
        self.assertEqual(
            conditions.get_substitutes("absence"),
            get_subs.return_value,
        )
        clear_cache.assert_called_once_with()
        get_subs.assert_called_once_with(
            auth.persno,
            "absence",
        )


@pytest.mark.integration
class ConditionsIntegration(testcase.RollbackTestCase):
    __context_uuid__ = "38b7b6d1-9ee5-11ec-872a-334b6053520d"  # Root (天皇)

    @mock.patch.object(conditions, "auth")
    def test_get_substitutes(self, auth):
        auth.persno = "caddok"
        self.assertEqual(
            set(conditions.get_substitutes(False)),
            {"cs.tasks.test", "faraway"},
        )

    @mock.patch.object(conditions, "auth")
    def test_get_substitutes_absentees_only(self, auth):
        auth.persno = "caddok"
        self.assertEqual(
            set(conditions.get_substitutes(True)),
            {
                "faraway",
            },
        )

    @mock.patch.object(conditions, "auth")
    def test_get_conditions_empty(self, auth):
        auth.persno = "caddok"
        self.assertEqual(
            conditions.get_conditions(
                [auth.persno],
                my_personal=False,
                my_roles=False,
                substitutes=False,
                user_personal=True,
                user_roles=True,
            ),
            ([], [], {}, "1=2"),
        )

    @mock.patch.object(conditions, "auth")
    def test_get_conditions_personal(self, auth):
        auth.persno = "caddok"
        self.assertEqual(
            conditions.get_conditions(
                ["user"],
                substitutes=False,
            ),
            (
                ["user", "caddok"],
                [],
                {},
                "("
                "("
                "((persno IN ('caddok') AND (subject_type IN ('', 'Person') OR subject_type IS NULL)) "
                "OR (persno IN ('user') AND (subject_type IN ('', 'Person') OR subject_type IS NULL))"
                ")"
                ") "
                "AND (1=1) "
                "AND (1=1)"
                ")",
            ),
        )

    @mock.patch.object(conditions, "auth")
    def test_get_conditions_user(self, auth):
        auth.persno = "caddok"
        self.assertEqual(
            conditions.get_conditions(
                ["user"],
                my_personal=False,
                my_roles=False,
                substitutes=False,
                user_personal=True,
                user_roles=True,
            ),
            (
                ["user", "caddok"],
                [],
                {},
                "(((persno IN ('user'))) AND (1=1) AND (1=1))",
            ),
        )

    @mock.patch.object(conditions, "auth")
    def test_get_conditions_users(self, auth):
        auth.persno = "caddok"
        self.assertEqual(
            conditions.get_conditions(
                ["user", "caddok", "user"],
                substitutes=True,
            ).users,
            ["user", "caddok"],
        )

    @mock.patch.object(conditions, "auth")
    def test_get_conditions_types(self, auth):
        auth.persno = "caddok"
        self.assertEqual(
            conditions.get_conditions(
                ["user"],
                substitutes=False,
                types=["A", "B"],
            ),
            (
                ["user", "caddok"],
                [],
                {},
                "((((persno IN ('caddok') "
                "AND (subject_type IN ('', 'Person') "
                "OR subject_type IS NULL)) "
                "OR (persno IN ('user') "
                "AND (subject_type IN ('', 'Person') "
                "OR subject_type IS NULL)))) "
                "AND (classname IN ('A','B')) "
                "AND (1=1))",
            ),
        )

    @mock.patch.object(conditions, "auth")
    def test_get_conditions_contexts(self, auth):
        auth.persno = "caddok"
        self.assertEqual(
            conditions.get_conditions(
                ["user"],
                substitutes=False,
                contexts=[self.__context_uuid__],
            ),
            (
                ["user", "caddok"],
                [],
                {"cs_tasks_test_olc": [{"cdb_object_id": self.__context_uuid__}]},
                "((((persno IN ('caddok') "
                "AND (subject_type IN ('', 'Person') "
                "OR subject_type IS NULL)) "
                "OR (persno IN ('user') "
                "AND (subject_type IN ('', 'Person') "
                "OR subject_type IS NULL)))) "
                "AND (1=1) "
                "AND (1=1))",
            ),
        )

    @mock.patch.object(conditions, "auth")
    def test_get_conditions_days(self, auth):
        auth.persno = "caddok"
        self.assertEqual(
            conditions.get_conditions(
                ["user"],
                substitutes=False,
                days=-1,
            ),
            (
                ["user", "caddok"],
                [],
                {},
                "((((persno IN ('caddok') "
                "AND (subject_type IN ('', 'Person') "
                "OR subject_type IS NULL)) "
                "OR (persno IN ('user') "
                "AND (subject_type IN ('', 'Person') "
                "OR subject_type IS NULL)))) "
                "AND (1=1) "
                "AND ((deadline < {})))".format(sqlapi.SQLdate_literal(date.today())),
            ),
        )

    @mock.patch.object(conditions, "auth")
    def test_get_conditions_start(self, auth):
        auth.persno = "caddok"
        expected_start_date = sqlapi.SQLdate_literal(date(2000, 1, 31))
        self.assertEqual(
            conditions.get_conditions(
                ["user"],
                substitutes=False,
                start="2000.1.31",
            ),
            (
                ["user", "caddok"],
                [],
                {},
                "((((persno IN ('caddok') "
                "AND (subject_type IN ('', 'Person') "
                "OR subject_type IS NULL)) "
                "OR (persno IN ('user') "
                "AND (subject_type IN ('', 'Person') "
                "OR subject_type IS NULL)))) "
                "AND (1=1) "
                "AND ((deadline >= {})))".format(expected_start_date),
            ),
        )

    @mock.patch.object(conditions, "auth")
    def test_get_conditions_end(self, auth):
        auth.persno = "caddok"
        expected_end_date = sqlapi.SQLdate_literal(date(2000, 12, 25))
        self.assertEqual(
            conditions.get_conditions(
                ["user"],
                substitutes=False,
                end="2000.12.24",
            ),
            (
                ["user", "caddok"],
                [],
                {},
                "((((persno IN ('caddok') "
                "AND (subject_type IN ('', 'Person') "
                "OR subject_type IS NULL)) "
                "OR (persno IN ('user') "
                "AND (subject_type IN ('', 'Person') "
                "OR subject_type IS NULL)))) "
                "AND (1=1) "
                "AND ((deadline < {})))".format(expected_end_date),
            ),
        )

    def test_apply_post_select_conditions_no_task(self):
        self.assertFalse(conditions.apply_post_select_conditions(None))

    def test_apply_post_select_conditions_no_contexts(self):
        self.assertTrue(conditions.apply_post_select_conditions("task"))

    @mock.patch(
        "cs.taskmanager.conf.get_cache",
        return_value=mock.MagicMock(context_classnames=["A", "B"]),
    )
    def test_apply_post_select_conditions_no_match(self, _):
        a = mock.MagicMock()
        a.GetClassname.return_value = "A"
        b = mock.MagicMock()
        b.GetClassname.return_value = "B"
        task = mock.MagicMock(
            getCsTasksContexts=mock.MagicMock(return_value=[a, b]),
        )
        contexts = {
            a.GetClassname.return_value: [{"id": "foo", "id2": "bar"}],
        }
        self.assertFalse(
            conditions.apply_post_select_conditions(task, contexts),
        )

    @mock.patch.object(conditions.logging, "error")
    @mock.patch(
        "cs.taskmanager.conf.get_cache",
        return_value=mock.MagicMock(context_classnames=["A", "B"]),
    )
    def test_apply_post_select_conditions_match(self, _, error):
        a = mock.MagicMock()
        b = mock.MagicMock()
        b.GetClassname.return_value = "B"
        b._key_dict.return_value = {"id2": "bar", "id": "foo"}
        task = mock.MagicMock(
            getCsTasksContexts=mock.MagicMock(return_value=[a, b]),
        )
        contexts = {
            b.GetClassname.return_value: [{"id": "foo", "id2": "bar"}],
        }
        self.assertTrue(
            conditions.apply_post_select_conditions(task, contexts),
        )
        error.assert_called_once_with(
            "class is missing in cs_tasks_context: '%s'",
            a.GetClassname.return_value,
        )

    def test__get_context_condition_empty(self):
        self.assertEqual(
            conditions._get_context_condition(),
            {},
        )

    @mock.patch.object(conditions.logging, "error")
    def test__get_context_condition(self, error):
        contexts = [self.__context_uuid__, "foo"]
        self.assertEqual(
            conditions._get_context_condition(contexts),
            {"cs_tasks_test_olc": [{"cdb_object_id": self.__context_uuid__}]},
        )
        error.assert_called_once_with("unknown context: '%s'", "foo")

    def test__get_sql_condition_no_users(self):
        self.assertIsNone(conditions._get_sql_condition(None, True, True))

    def test__get_sql_condition_filter00(self):
        self.assertIsNone(conditions._get_sql_condition("foo", False, False))

    @mock.patch.object(conditions, "format_in_condition")
    def test__get_sql_condition_filter11(self, format_in_condition):
        self.assertEqual(
            conditions._get_sql_condition("foo", True, True),
            format_in_condition.return_value,
        )
        format_in_condition.assert_called_once_with("persno", "foo")

    @mock.patch.object(conditions, "format_in_condition", return_value="bar")
    def test__get_sql_condition_filter01(self, format_in_condition):
        self.assertEqual(
            conditions._get_sql_condition("foo", False, True),
            "(bar AND (subject_type NOT IN ('', 'Person')))",
        )
        format_in_condition.assert_called_once_with("persno", "foo")

    @mock.patch.object(conditions, "format_in_condition", return_value="bar")
    def test__get_sql_condition_filter10(self, format_in_condition):
        self.assertEqual(
            conditions._get_sql_condition("foo", True, False),
            "(bar AND (subject_type IN ('', 'Person') OR subject_type IS NULL))",
        )
        format_in_condition.assert_called_once_with("persno", "foo")

    def test__get_deadline_condition_none(self):
        self.assertEqual(
            conditions._get_deadline_condition(),
            "1=1",
        )

    @mock.patch.object(conditions, "date")
    def test__get_deadline_condition_days(self, mock_date):
        mock_date.today.return_value = date(2021, 4, 15)
        self.assertEqual(
            conditions._get_deadline_condition(-2),
            "(deadline < {})".format(sqlapi.SQLdate_literal(date(2021, 4, 14))),
        )

    def test__get_deadline_condition_start(self):
        self.assertEqual(
            conditions._get_deadline_condition(None, "2021-04-01"),
            "(deadline >= {})".format(sqlapi.SQLdate_literal(date(2021, 4, 1))),
        )

    def test__get_deadline_condition_end(self):
        self.assertEqual(
            conditions._get_deadline_condition(None, None, "1.4.2021"),
            "(deadline < {})".format(sqlapi.SQLdate_literal(date(2021, 1, 5))),
        )

    @mock.patch.object(conditions, "date")
    def test__get_deadline_condition_all(self, mock_date):
        def real_date_impl(*args, **kw):
            return date(*args, **kw)

        mock_date.side_effect = real_date_impl
        mock_date.today.return_value = date(2021, 4, 15)
        self.assertEqual(
            conditions._get_deadline_condition(2, "2021-04-01", "21.4.2021"),
            "(deadline < {} "
            "AND deadline >= {} "
            "AND deadline < {})".format(
                sqlapi.SQLdate_literal(date(2021, 4, 18)),
                sqlapi.SQLdate_literal(date(2021, 4, 1)),
                sqlapi.SQLdate_literal(date(2021, 4, 22)),
            ),
        )

    def test__get_deadline_condition_none(self):
        self.assertEqual(
            conditions._get_deadline_condition(),
            "1=1",
        )

    def _format_dl(self, operator, deadline):
        deadline_str = "'{}T00:00:00'".format(deadline.isoformat())

        if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
            deadline_str = "TO_DATE('{}','DD.MM.YYYY')".format(
                deadline.strftime("%d.%m.%Y"),
            )

        return "deadline {} {}".format(operator, deadline_str)

    @mock.patch.object(conditions, "date")
    def test__get_deadline_condition_days(self, mock_date):
        mock_date.today.return_value = date(2021, 4, 15)
        expected = "({})".format(self._format_dl("<", date(2021, 4, 14)))
        self.assertEqual(
            conditions._get_deadline_condition(-2),
            expected,
        )

    def test__get_deadline_condition_start(self):
        expected = "({})".format(self._format_dl(">=", date(2021, 4, 1)))
        self.assertEqual(
            conditions._get_deadline_condition(None, "2021-04-01"),
            expected,
        )

    def test__get_deadline_condition_end(self):
        expected = "({})".format(self._format_dl("<", date(2021, 1, 5)))
        self.assertEqual(
            conditions._get_deadline_condition(None, None, "1.4.2021"),
            expected,
        )

    @mock.patch.object(conditions, "date")
    def test__get_deadline_condition_all(self, mock_date):
        def real_date_impl(*args, **kw):
            return date(*args, **kw)

        mock_date.side_effect = real_date_impl
        mock_date.today.return_value = date(2021, 4, 15)
        expected = "({} AND {} AND {})".format(
            self._format_dl("<", date(2021, 4, 18)),
            self._format_dl(">=", date(2021, 4, 1)),
            self._format_dl("<", date(2021, 4, 22)),
        )
        self.assertEqual(
            conditions._get_deadline_condition(2, "2021-04-01", "21.4.2021"),
            expected,
        )


if __name__ == "__main__":
    unittest.main()
