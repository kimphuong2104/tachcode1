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


from cdb import tools
from cdb import sqlapi
from cdb.platform.gui import CDBCatalog
from cdb.platform.gui import CDBCatalogContent
from cs.taskboard.objects import Board


class CatalogContentTaskBoardContentTypes(CDBCatalogContent):
    def __init__(self, board_adapter_cls, catalog):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        CDBCatalogContent.__init__(self, tabdef)
        self.classnames = list(board_adapter_cls.get_all_content_classnames()) \
            if board_adapter_cls else []

    def getNumberOfRows(self):
        return len(self.classnames)

    def getRowObject(self, row):
        from cdb.platform import mom
        keys = mom.SimpleArguments(classname=self.classnames[row])
        return mom.CDBObjectHandle(self.cdef, keys, False, True)


class CatalogTaskBoardContentTypes(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)

    def init(self):
        board_api = ""
        try:
            board_api = self.getInvokingDlgValue("board_api")
        except Exception:
            pass
        cdb_object_id = ""
        try:
            cdb_object_id = self.getInvokingDlgValue("cdb_object_id")
        except Exception:
            pass
        template_object_id = ""
        try:
            template_object_id = self.getInvokingDlgValue("template_object_id")
        except Exception:
            pass

        board_id = cdb_object_id or template_object_id
        if not board_api and board_id:
            rset = sqlapi.RecordSet2(
                Board.GetTableName(),
                condition="cdb_object_id='%s'" % (board_id),
                columns=["board_api"]
            )
            if len(rset):
                board_api = rset[0].board_api
        adapter_cls = None
        if board_api:
            adapter_cls = tools.load_callable(board_api)
        self.setResultData(CatalogContentTaskBoardContentTypes(adapter_cls, self))
