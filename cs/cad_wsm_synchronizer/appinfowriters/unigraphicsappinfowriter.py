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


class UnigraphicsAppInfoWriter(AppInfoWriterBase):
    CAD_System = "Unigraphics"


class UnigraphicsPartAppInfoWriter(UnigraphicsAppInfoWriter):
    CDB_CLIENTNAME = "Unigraphics:prt"

    def _writeFile(self):
        links = self.getLinks()
        self.root.append(links)


class UnigraphicsDrwAppInfoWriter(UnigraphicsAppInfoWriter):
    CDB_CLIENTNAME = "Unigraphics:drw"

    def _writeFile(self):
        sheets = self.getSheets()
        self.root.append(sheets)
