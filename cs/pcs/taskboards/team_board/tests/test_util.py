#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest

import mock
import pytest
from cdb import sqlapi, testcase
from cdb.dberrors import DBError

from cs.pcs.taskboards.team_board import util


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


VALID_STATEMENT = "SELECT cdb_object_id FROM cs_taskboard_board"


@pytest.mark.unit
class TestTeamBoardUtil(unittest.TestCase):
    @mock.patch.object(util.sig, "emit", autospec=True)
    def test_get_valid_boards_sql_condition_without_params(self, emit):
        "Function 'valid_boards_sql_condition' called without parameters"
        emit.return_value.return_value = [VALID_STATEMENT]

        # actual method called without parameters
        error = "no exception"
        try:
            # valid db table name is given
            stmt = util.get_valid_boards_sql_condition()
            sqlapi.RecordSet2(sql="SELECT * FROM cs_taskboard_card c WHERE " + stmt)
        except DBError:
            error = "DBError"

        # check if correct error occurs
        self.assertTrue(
            error == "no exception",
            f"No exception should occur. Instead {error} occurred",
        )

        # check if emit is called with the right parameter
        emit.assert_called_once_with("get_valid_board_object_ids")

        # check if returned method is called the right way
        emit.return_value.assert_called_once_with()

    @mock.patch.object(util.sig, "emit", autospec=True)
    def test_get_valid_boards_sql_condition_with_valid_params(self, emit):
        "Function 'valid_boards_sql_condition' called with valid parameters"
        emit.return_value.return_value = [VALID_STATEMENT]

        # actual method called with parameters
        error = "no exception"
        try:
            # valid db table name is given, plus additional params
            table_alias = "overwriting_table"
            stmt = util.get_valid_boards_sql_condition(
                table_alias=table_alias, unused="unused", valid_stmt="overwritten"
            )
            sql = (
                "SELECT * FROM cs_taskboard_card {table_alias} WHERE " + stmt
            ).format(table_alias=table_alias)
            sqlapi.RecordSet2(sql=sql)
        except DBError:
            error = "DBError"

        # check if correct error occurs
        self.assertTrue(
            error == "no exception",
            f"No exception should occur. Instead {error} occurred",
        )

        # check if emit is called with the right parameter
        emit.assert_called_once_with("get_valid_board_object_ids")

        # check if returned method is called the right way
        emit.return_value.assert_called_once_with()

    @mock.patch.object(util.sig, "emit", autospec=True)
    def test_get_valid_boards_sql_condition_invalid_params(self, emit):
        "Function 'valid_boards_sql_condition' called with invalid parameters"
        emit.return_value.return_value = [VALID_STATEMENT]

        # actual method called with parameters
        error = "no exception"
        try:
            # invalid db table name is given
            table_alias = 1
            stmt = util.get_valid_boards_sql_condition(table_alias=table_alias)
            sql = (
                "SELECT * FROM cs_taskboard_card {table_alias} WHERE " + stmt
            ).format(table_alias=table_alias)
            sqlapi.RecordSet2(sql=sql)
        except DBError:
            error = "DBError"

        # check if correct error occurs
        self.assertTrue(
            error == "DBError",
            f"DBError should occur. Instead {error} occurred",
        )

        # check if emit is called with the right parameter
        emit.assert_called_once_with("get_valid_board_object_ids")

        # check if returned method is called the right way
        emit.return_value.assert_called_once_with()

    @mock.patch.object(util.sig, "emit", autospec=True)
    def test_get_valid_boards_sql_condition_signal_returns_valid_sql(self, emit):
        "Emitted signal returns valid SQL statement"
        emit.return_value.return_value = [VALID_STATEMENT]

        # actual method called with parameters
        error = "no exception"
        try:
            # valid db table name is given
            table_alias = "valid_table_name"
            stmt = util.get_valid_boards_sql_condition(table_alias=table_alias)
            sql = (
                "SELECT * FROM cs_taskboard_card {table_alias} WHERE " + stmt
            ).format(table_alias=table_alias)
            sqlapi.RecordSet2(sql=sql)
        except DBError:
            error = "DBError"

        # check if correct error occurs
        self.assertTrue(
            error == "no exception",
            f"No exception should occur. Instead {error} occurred",
        )

        # check if emit is called with the right parameter
        emit.assert_called_once_with("get_valid_board_object_ids")

        # check if returned method is called the right way
        emit.return_value.assert_called_once_with()

    @mock.patch.object(util.sig, "emit", autospec=True)
    def test_get_valid_boards_sql_condition_signal_returns_invalid_sql(self, emit):
        "Emitted signal returns invalid SQL statement"
        emit.return_value.return_value = ["invalid SQL statement"]

        # actual method called with parameters
        error = "no exception"
        try:
            # invalid db table name is given
            table_alias = "valid_table_name"
            stmt = util.get_valid_boards_sql_condition(table_alias=table_alias)
            sql = (
                "SELECT * FROM cs_taskboard_card {table_alias} WHERE " + stmt
            ).format(table_alias=table_alias)
            sqlapi.RecordSet2(sql=sql)
        except DBError:
            error = "DBError"

        # check if correct error occurs
        self.assertTrue(
            error == "DBError",
            f"DBError should occur. Instead {error} occurred",
        )

        # check if emit is called with the right parameter
        emit.assert_called_once_with("get_valid_board_object_ids")

        # check if returned method is called the right way
        emit.return_value.assert_called_once_with()

    @mock.patch.object(util.sig, "emit", autospec=True)
    def test_get_valid_boards_sql_condition_signal_returns_no_iterable(self, emit):
        "Emitted signal returns invalid SQL statement"
        emit.return_value.return_value = True

        # actual method called with parameters
        error = "no exception"
        try:
            # invalid db table name is given
            table_alias = "valid_table_name"
            stmt = util.get_valid_boards_sql_condition(table_alias=table_alias)
            sql = (
                "SELECT * FROM cs_taskboard_card {table_alias} WHERE " + stmt
            ).format(table_alias=table_alias)
            sqlapi.RecordSet2(sql=sql)
        except TypeError:
            error = "TypeError"

        # check if correct error occurs
        self.assertTrue(
            error == "TypeError",
            f"TypeError should occur. Instead {error} occurred",
        )

        # check if emit is called with the right parameter
        emit.assert_called_once_with("get_valid_board_object_ids")

        # check if returned method is called the right way
        emit.return_value.assert_called_once_with()
