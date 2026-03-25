#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging
import re
from datetime import date

from cdb import sqlapi

LEGACY_DATE = re.compile(r"(?P<day>\d{2})\.(?P<month>\d{2})\.(?P<year>\d{4})")


def SQLdate(table, col, row):
    date_str = sqlapi.SQLdate(table, col, row)
    if date_str:
        day, month, year = LEGACY_DATE.match(date_str).groups()
        return date(int(year), int(month), int(day))
    return ""


def load(select, columns):
    """
    Low-level SQL loading (~60% faster than `cdb.sqlapi.RecordSet2`).

    :param select: SELECT statement (without "SELECT" keyword)
    :type select: str

    :param columns: List of two entries each:
        Column name and value getter function
        (like `cdb.sqlapi.SQLstring` and siblings).
    :type columns: iterable

    :returns: List of dicts representing the queried DB rows
    :rtype: list

    :raises ValueError: if length of ``columns`` does not match
        the number of columns in query result.
    """
    table = sqlapi.SQLselect(select)
    no_of_columns = sqlapi.SQLcols(table)

    if no_of_columns != len(columns):
        logging.error("got %s columns, expected %s", no_of_columns, len(columns))
        raise ValueError

    result = [
        {
            column: value_getter(table, column_index, row_index)
            for column_index, (column, value_getter) in enumerate(columns)
        }
        for row_index in range(sqlapi.SQLrows(table))
    ]
    return result
