#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


from cdb import sqlapi
from cdb import ddl


class DropOldTimeUnitTable(object):
    def run(self):
        t = ddl.Table('cs_taskboard_interval')
        if t.exists():
            t.drop()


class DropOldSprintView(object):
    def run(self):
        t = ddl.View('cs_taskboard_sprint_v')
        if t.exists():
            t.drop()


class AdjustIntervalObjectClass(object):
    def run(self):
        t = ddl.Table('cs_taskboard_sprint')
        if t.exists():
            sqlapi.SQLinsert(
                "INTO cs_taskboard_iteration "
                "(cdb_object_id, board_object_id, title, cdb_status_txt, status, "
                "cdb_objektart, start_date, end_date, description, cdb_classname) "
                "SELECT cdb_object_id, board_object_id, title, cdb_status_txt, status, "
                "cdb_objektart, start_date, end_date, description, 'cs_taskboard_iter_interval' "
                "FROM cs_taskboard_sprint")
            sqlapi.SQLupdate(
                "cs_taskboard_iteration SET cdb_objektart='cs_taskboard_iteration' "
                "WHERE cdb_classname!='cs_taskboard_iter_sprint'"
            )
            sqlapi.SQLupdate(
                "cdb_object SET relation='cs_taskboard_iteration' "
                "WHERE relation='cs_taskboard_sprint'"
            )
            t.drop()


pre = []
post = [
    DropOldTimeUnitTable,
    AdjustIntervalObjectClass,
    DropOldSprintView
]
