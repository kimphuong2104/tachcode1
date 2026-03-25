#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from __future__ import absolute_import
__revision__ = "$Id$"

from cdb import sqlapi
from cdb import ddl


def update_owner(table):
    tbl = ddl.Table(table)
    if tbl.exists():
        if not tbl.hasColumn('subject_id'):
            tbl.addAttributes(ddl.Char('subject_id'))
        if not tbl.hasColumn('subject_type'):
            tbl.addAttributes(ddl.Char('subject_type'))

    if tbl.hasColumn('owner'):
        sqlapi.SQLupdate(
            "%s SET subject_id = owner, subject_type = 'Person' WHERE owner IS NOT "
            "NULL AND owner <> ''" % table)


class UpdateDashboard(object):
    """
    Adds the attributes subject_id and subject_type for dashboards an dashboard items
    """
    def run(self):
        update_owner('csweb_dashboard')
        update_owner('csweb_dashboard_item')


class UpdateDefault(object):
    """
    Drops the attribute is_default for dashboards
    """
    def run(self):
        tbl = ddl.Table('csweb_dashboard')
        if tbl.hasColumn('is_default'):
            tbl.dropAttributes('is_default')


pre = [UpdateDashboard, UpdateDefault]
