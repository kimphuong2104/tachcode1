#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Morepath model classes for Web UI object favorites
"""

from __future__ import absolute_import
__revision__ = "$Id$"

from cdbwrapc import RestTabularData, CDBClassDef
from cdb import auth
from cdb.objects import Object
from cdb.platform.mom import getObjectHandlesFromRESTIDs
from cs.platform.web.rest.support import rest_name_for_class_name
from cs.platform.web.uisupport.resttable import RestTableWrapper


class FavoriteCollection(object):
    def __init__(self, classname, as_table):
        self.classname = classname
        self.as_table = as_table
        self.rest_name = rest_name_for_class_name(classname) if classname else None

    def get_favorites(self):
        cond = {"cdb_cpersno": auth.persno}
        if self.rest_name:
            cond["rest_name"] = self.rest_name
        return Favorite.KeywordQuery(**cond)

    def getTableResult(self, obj_handles):
        clsdef = CDBClassDef(self.classname)
        if self.as_table:
            tdef = clsdef.getProjection(self.as_table, True)
        else:
            tdef = clsdef.getDefaultProjection()
        return RestTableWrapper(RestTabularData(obj_handles, tdef))


class Favorite(Object):
    __classname__ = "cdbweb_favorites"
    __maps_to__ = "cdbweb_favorites"

    @classmethod
    def get_handle(cls, for_item):
        oh = None
        if for_item['rest_name']:
            ohs = getObjectHandlesFromRESTIDs(for_item['rest_name'],
                                              [for_item['rest_id']],
                                              check_access=True)
            if len(ohs) == 1:
                oh = ohs[for_item['rest_id']]
        return oh
