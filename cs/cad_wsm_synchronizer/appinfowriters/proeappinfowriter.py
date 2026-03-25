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


class ProeAppInfoWriter(AppInfoWriterBase):
    CAD_System = "ProE"

    def getSheet(self, sheetId):
        sheet = AppInfoWriterBase.getSheet(self, sheetId)
        return sheet


class ProePrtAppInfoWriter(ProeAppInfoWriter):
    CDB_CLIENTNAME = "ProE:Part"

    def _writeFile(self):
        links = self.getLinks()
        self.root.append(links)


class ProeAsmAppInfoWriter(ProeAppInfoWriter):
    CDB_CLIENTNAME = "ProE:Asmbly"

    def _writeFile(self):
        occs, referencedDocs = self.getOccurences()
        self.root.append(occs)
        self.appendBom(referencedDocs)


class ProeGenAsmblyAppInfoWriter(ProeAppInfoWriter):
    CDB_CLIENTNAME = "ProE:GenAsmbly"

    def _writeFile(self):
        occs, referencedDocs = self.getOccurences()
        self.root.append(occs)
        self.appendBom(referencedDocs)


class ProeDrwAppInfoWriter(ProeAppInfoWriter):
    CDB_CLIENTNAME = "ProE:Drawing"

    def _writeFile(self):
        sheets = self.getSheets()
        self.root.append(sheets)


class ProeGenPartAppInfoWriter(ProeAppInfoWriter):
    CDB_CLIENTNAME = "ProE:GenPart"

    def _writeFile(self):
        links = self.getLinks()
        self.root.append(links)


class ProeDiagramAppInfoWriter(ProeAppInfoWriter):
    CDB_CLIENTNAME = "ProE:Diagram"

    def _writeFile(self):
        links = self.getLinks()
        self.root.append(links)


class ProeManufactAppInfoWriter(ProeAppInfoWriter):
    CDB_CLIENTNAME = "ProE:Manufact"

    def _writeFile(self):
        links = self.getLinks()
        self.root.append(links)


class ProeFormatAppInfoWriter(ProeAppInfoWriter):
    CDB_CLIENTNAME = "ProE:Format"

    def _writeFile(self):
        links = self.getLinks()
        self.root.append(links)


class ProeLayoutAppInfoWriter(ProeAppInfoWriter):
    CDB_CLIENTNAME = "ProE:Layout"

    def _writeFile(self):
        links = self.getLinks()
        self.root.append(links)


class ProeMarkupAppInfoWriter(ProeAppInfoWriter):
    CDB_CLIENTNAME = "ProE:Markup"

    def _writeFile(self):
        links = self.getLinks()
        self.root.append(links)


class ProeReportAppInfoWriter(ProeAppInfoWriter):
    CDB_CLIENTNAME = "ProE:Report"

    def _writeFile(self):
        links = self.getLinks()
        self.root.append(links)


class ProeSketchAppInfoWriter(ProeAppInfoWriter):
    CDB_CLIENTNAME = "ProE:Sketch"

    def _writeFile(self):
        links = self.getLinks()
        self.root.append(links)


class ProeUDFAppInfoWriter(ProeAppInfoWriter):
    CDB_CLIENTNAME = "ProE:UDF"

    def _writeFile(self):
        links = self.getLinks()
        self.root.append(links)
