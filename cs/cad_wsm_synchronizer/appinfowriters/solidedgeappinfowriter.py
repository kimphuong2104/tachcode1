#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# Revision: "$Id$"
#

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

from cs.cad_wsm_synchronizer.appinfowriters.appinfowriter import AppInfoWriterBase


class SolidEdgeAppInfoWriter(AppInfoWriterBase):
    CAD_System = "SolidEdge"

    def getSheet(self, sheetId):
        sheet = AppInfoWriterBase.getSheet(self, sheetId)
        sheet.attrib["name"] = "tmp"
        return sheet


class SolidEdgeAsmAppInfoWriter(SolidEdgeAppInfoWriter):
    CDB_CLIENTNAME = "SolidEdge:asm"

    def _writeFile(self):
        occs, referencedDocs = self.getOccurences()
        self.root.append(occs)
        self.appendBom(referencedDocs)


class SolidEdgePwdAppInfoWriter(SolidEdgeAppInfoWriter):
    CDB_CLIENTNAME = "SolidEdge:pwd"

    def _writeFile(self):
        occs, referencedDocs = self.getOccurences()
        self.root.append(occs)
        self.appendBom(referencedDocs)


class SolidEdgeDraftAppInfoWriter(SolidEdgeAppInfoWriter):
    CDB_CLIENTNAME = "SolidEdge:draft"

    def _writeFile(self):
        sheets = self.getSheets()
        self.root.append(sheets)


class SolidEdgePartAppInfoWriter(SolidEdgeAppInfoWriter):
    CDB_CLIENTNAME = "SolidEdge:part"

    def _writeFile(self):
        links = self.getLinks()
        self.root.append(links)


class SolidEdgePsmAppInfoWriter(SolidEdgeAppInfoWriter):
    CDB_CLIENTNAME = "SolidEdge:psm"

    def _writeFile(self):
        links = self.getLinks()
        self.root.append(links)
