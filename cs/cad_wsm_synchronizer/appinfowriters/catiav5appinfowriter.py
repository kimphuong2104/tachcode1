#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# Revision: "$Id$"
#

"""
Erlaeuterung zu moeglichen Eintraegen der cdb_doc_rel:

der reltype steht fuer normale Occurences/Links immer auf "Catia:Ref".

Nur bei Occurences auf SML generierte Varianten gibt es anstatt einem
"Catia:Ref" zwei Eintraege und zwar "Catia:GRef"+"Catia:IRef",
da man fuer die Identifikation zusaetzlich noch die Teilestamm-Schluessel
benoetigt. "Catia:GRef" ist vom Inhalt so wie "Catia:Ref",
dient nur zur Erkennung, dass es dann auch noch ein "Catia:IRef" gibt. In
"Catia:IRef" steht in z_nummer2 die teilenummer, in z_index2 der t_index.
"""

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

from lxml import etree as ElementTree

import six

from cs.cad_wsm_synchronizer.appinfowriters.appinfowriter import AppInfoWriterBase


class CatiaV5AppInfoWriter(AppInfoWriterBase):
    CAD_System = "CatiaV5"
    # overwrite base class methods to implement CatiaV5 specific stuff


class CatiaV5PrtAppInfoWriter(CatiaV5AppInfoWriter):
    CDB_CLIENTNAME = "CatiaV5:Part"

    def _writeFile(self):
        links = self.getLinks()
        self.root.append(links)


class CatiaV5ProdAppInfoWriter(CatiaV5AppInfoWriter):
    CDB_CLIENTNAME = "CatiaV5:Prod"

    def _writeFile(self):
        occs, referencedDocs = self.getOccurences()
        self.root.append(occs)
        self.appendBom(referencedDocs)


class CatiaV5ProcessAppInfoWriter(CatiaV5AppInfoWriter):
    CDB_CLIENTNAME = "CatiaV5:Process"

    def _writeFile(self):
        derivedSources = self.getDerivedSources()
        if derivedSources:
            self.root.append(derivedSources)

    def getDerivedSources(self):
        derivedSources = None
        cadRefId = 1
        for ref in self.doc.DocumentReferences:
            if self._occurrenceTypes is None or ref.reltype in self._occurrenceTypes:
                if ref.ReferencedDocument:
                    primFName = self.getPrimaryFilename(ref.ReferencedDocument)
                    if primFName is not None:
                        derivedSource = ElementTree.Element("derivedsource")
                        derivedSource.attrib["id"] = six.text_type(cadRefId).zfill(3)

                        cadref = ElementTree.Element("cadreference")
                        cadref.attrib["path"] = primFName
                        derivedSource.append(cadref)
                        if derivedSources is None:
                            derivedSources = ElementTree.Element("derivedsources")
                        derivedSources.append(derivedSource)
                        cadRefId += 1
        return derivedSources


class CatiaV5DrwAppInfoWriter(CatiaV5AppInfoWriter):
    CDB_CLIENTNAME = "CatiaV5:Drawing"

    def _writeFile(self):
        sheets = self.getSheets()
        self.root.append(sheets)
