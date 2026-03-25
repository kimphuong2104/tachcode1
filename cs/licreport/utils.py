#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module cdblib.utils

Utilities for license reporting.
"""
import datetime
import logging

from cdb import ddl, sqlapi

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = ['first_row',
           'first_value',
           'get_rows',
           'sql_str_in',
           'parse_timestamp',
           'format_timestamp']


def first_row(sql):
    rs = sqlapi.RecordSet2(sql=sql)
    if rs:
        return dict(rs[0].items())
    else:
        return {}


def first_value(sql):
    rs = sqlapi.RecordSet2(sql=sql)
    if rs:
        return rs[0].values()[0]
    else:
        return None


def get_rows(sql):
    data = []
    for row in sqlapi.RecordSet2(sql=sql):
        rowd = {}
        for key, value in row.items():
            if key is sqlapi.NULL:
                key = None
            if value is sqlapi.NULL:
                value = None
            rowd[key] = value
        data.append(rowd)
    return data


def sql_str_in(dataset):
    assert dataset
    if len(dataset) > 1:
        return " IN (%s)" % ",".join("'%s'" % sqlapi.quote(d) for d in dataset)
    else:
        return " = '%s'" % sqlapi.quote(dataset[0])


def parse_timestamp(ts_string):
    if ts_string is None:
        return datetime.datetime.utcnow()
    return datetime.datetime.strptime(ts_string, "%Y.%m.%d %H:%M:%S")


def format_timestamp(ts):
    return ts.strftime("%Y.%m.%d %H:%M:%S")


def reindex():
    """
    Rebuild the Indices needed on
    """
    idxs = [
        ('lstat_lbtime', ['lbtime']),
        ('lstat_lbtime_pid_lb_mno', ['pid', 'lbtime', 'event', 'mno']),
        ('lstat_pid_event_mno', ['pid', 'event', 'mno']),
        ('lstat_pid_lbtime_id', ['pid', 'lbtime', 'cs_sortable_id']),
        ('lstat_pid_lbtime', ['pid', 'lbtime']),
        ('lstat_pid', ['pid'])
    ]

    log = logging.getLogger(__name__)

    for name, cols in idxs:
        idx = ddl.Index(name)
        log.info("Checking for index %s", name)
        if not idx.exists():
            log.info("Index %s is missing, creating it.", name)
            try:
                idx.create('lstatistics', cols, unique=False)
            except Exception:
                log.exception("Failed to create: %s", name)

    tab = ddl.Table('lstatistics')
    log.info("Updating all statistics on the lstatistics relation.")
    tab.update_statistics()
    log.info("Finished updates.")
