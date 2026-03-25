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


class InventorAppInfoWriter(AppInfoWriterBase):
    CAD_System = "inventor"


class InventorAsmAppInfoWriter(InventorAppInfoWriter):
    CDB_CLIENTNAME = "inventor:asm"

    def _writeFile(self):
        occs, referencedDocs = self.getOccurences()
        self.root.append(occs)
        self.appendBom(referencedDocs)


class InventorWeldAppInfoWriter(InventorAppInfoWriter):
    CDB_CLIENTNAME = "inventor:weld"

    def _writeFile(self):
        occs, referencedDocs = self.getOccurences()
        self.root.append(occs)
        self.appendBom(referencedDocs)


class InventorPartAppInfoWriter(InventorAppInfoWriter):
    CDB_CLIENTNAME = "inventor:prt"

    def _writeFile(self):
        links = self.getLinks()
        self.root.append(links)


class InventorShmAppInfoWriter(InventorAppInfoWriter):
    CDB_CLIENTNAME = "inventor:psm"

    def _writeFile(self):
        links = self.getLinks()
        self.root.append(links)


class InventorDraftAppInfoWriter(InventorAppInfoWriter):
    CDB_CLIENTNAME = "inventor:dft"

    def _writeFile(self):
        sheets = self.getSheets()
        self.root.append(sheets)
