#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Morepath model classes for Web UI history
"""

from __future__ import absolute_import
__revision__ = "$Id$"

from cdbwrapc import RestTabularData, CDBClassDef
from cdb import auth
from cdb.objects import Object
from cs.platform.web.rest.support import rest_name_for_class_name
from cs.platform.web.uisupport.resttable import RestTableWrapper


class HistoryCollection(object):
    def __init__(self, classname, amount, as_table):
        self.classname = classname
        self.amount = amount
        self.as_table = as_table
        self.rest_name = rest_name_for_class_name(classname) if classname else None

    def get_recent_items(self):
        cond = {"cdb_cpersno": auth.persno}
        if self.rest_name:
            cond["rest_name"] = self.rest_name

        return (HistoryItem
                .KeywordQuery(**cond)
                .Query(condition="1=1",
                       order_by='cdb_cdate desc',
                       max_rows=self.amount))

    def getTableResult(self, obj_handles):
        clsdef = CDBClassDef(self.classname)
        if self.as_table:
            tdef = clsdef.getProjection(self.as_table, True)
        else:
            tdef = clsdef.getDefaultProjection()
        return RestTableWrapper(RestTabularData(obj_handles, tdef))


class HistoryItem(Object):
    __classname__ = "cdbweb_history_item"
    __maps_to__ = "cdbweb_history_item"
