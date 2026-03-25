#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

from cdb import sqlapi


# maximum number of values to put into a "WHERE X IN" query.
# most of all this is a Oracle limitation, see MAX_INLIST_VALUE constant
MAX_IN_ELEMENTS = 1000
MAX_PAIRS = MAX_IN_ELEMENTS / 2


def partionedSqlQuery(sql, attribute, values, withAnd=True, withFormat=False):
    """
    :param sql: a SELECT query that ends with the WHERE clause (that we attach to)
    :param attribute: name of attribute to compare to values
    :param values: list of values
    :param withAnd: Whether to use "AND" or just append the condition without.
    :return: list of records
    """
    if len(values) > MAX_IN_ELEMENTS:
        values1 = values[:MAX_IN_ELEMENTS]
        values2 = values[MAX_IN_ELEMENTS:]
        records1 = partionedSqlQuery(sql, attribute, values1, withAnd, withFormat)
        records2 = partionedSqlQuery(sql, attribute, values2, withAnd, withFormat)
        records1.extend(records2)
        return records1

    records = []
    if values:
        valueString = u",".join("'" + sqlapi.quote(val) + "'" for val in values)
        condition = u"%s IN (%s)" % (attribute, valueString)
        if withAnd:
            finalCondition = " AND %s" % condition
        else:
            finalCondition = " %s" % condition
        if withFormat:
            sql = sql % finalCondition
        else:
            sql += finalCondition
        recordSet = sqlapi.RecordSet2(sql=sql)
        records = list(recordSet)
    return records
