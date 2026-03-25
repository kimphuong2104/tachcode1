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


class SolidWorksAppInfoWriter(AppInfoWriterBase):
    CAD_System = "SolidWorks"


class SolidWorksAsmAppInfoWriter(SolidWorksAppInfoWriter):
    CDB_CLIENTNAME = "SolidWorks:asm"

    def _writeFile(self):
        occs, referencedDocs = self.getOccurences()
        self.root.append(occs)
        self.appendBom(referencedDocs)


class SolidWorksPartAppInfoWriter(SolidWorksAppInfoWriter):
    CDB_CLIENTNAME = "SolidWorks:part"

    def _writeFile(self):
        links = self.getLinks()
        self.root.append(links)


class SolidWorksDrwAppInfoWriter(SolidWorksAppInfoWriter):
    CDB_CLIENTNAME = "SolidWorks"

    def _writeFile(self):
        sheets = self.getSheets()
        self.root.append(sheets)
