#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Powerscript catalog "cdbwf_resp_browser"
"""

from cdb import sqlapi
from cdb.platform.gui import CDBCatalog
from cdb.platform.gui import CDBCatalogContent
from cdb.platform.mom import CDBObjectHandle
from cdb.platform.mom import SimpleArgument
from cdb.platform.mom import SimpleArgumentList
from cdb.typeconversion import to_untyped_c_api

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class CatalogWFResponsibleData(CDBCatalogContent):
    def __init__(self, cdb_project_id, catalog):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()

        if self.cdef:
            tabdef = self.cdef.getProjection(tabdefname, True)
        else:
            tabdef = tabdefname

        CDBCatalogContent.__init__(self, tabdef)
        self.cdb_project_id = cdb_project_id
        self.data = None

    def _initData(self, refresh=False):
        if not self.data or refresh:
            condition = self.getSQLCondition()
            self.data = sqlapi.RecordSet2("cdbwf_resp_browser",
                                          "{}".format(condition),
                                          addtl=" ORDER BY order_by")

    def onSearchChanged(self):
        self._initData(True)

    def refresh(self):
        self._initData(True)

    def getNumberOfRows(self):
        self._initData()
        return len(self.data)

    def getRowObject(self, row):
        if not self.cdef:
            return CDBCatalogContent.getRowObject(self, row)

        else:
            self._initData()
            keys = SimpleArgumentList()

            for keyname in self.cdef.getKeyNames():
                keys.append(SimpleArgument(keyname, self.data[row][keyname]))

            return CDBObjectHandle(self.cdef, keys, False, True)

    def _get_value(self, rec, attr):
        "Retrieves the value of `attr` from the record `rec`"
        result = u""

        if self.cdef:
            adef = self.cdef.getAttributeDefinition(attr)

            for db_name in adef.getSQLSelectNames():
                result = rec[db_name]

                if result:
                    break
        else:
            result = rec[attr]

        return to_untyped_c_api(result)

    def getRowData(self, row):
        self._initData()
        result = []
        tdef = self.getTabDefinition()

        for col in tdef.getColumns():
            attr = col.getAttribute()
            value = u""

            try:
                obj = self.data[row]
                value = self._get_value(obj, attr)
                if not value:
                    value = u""

            except Exception:
                value = u""

            result.append(value)

        return result


class CatalogWFResponsible(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)

    def init(self):
        # if the project is known, we fill the catalog on our own
        cdb_project_id = ""
        try:
            cdb_project_id = self.getInvokingDlgValue("cdb_project_id")
        except Exception:
            pass

        if cdb_project_id:
            self.setResultData(CatalogWFResponsibleData(cdb_project_id, self))
