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

import sys
import os
import io
import tempfile

from collections import defaultdict
from lxml import etree as ElementTree

import six

from cs.documents import Document
from cdb import rte


def mkZName(docRec):
    return "%s-%s" % (docRec.z_nummer, docRec.z_index)


def toStringTuple(iterable):
    strTuple = "','".join(iterable)
    strTuple = "('%s')" % strTuple
    return strTuple


class AppInfoWriterBase(object):
    """
    Baseclass for all AppInfoWriter implementations
    """

    CAD_System = None
    CDB_CLIENTNAME = None

    TMP_DIR = rte.environ.get("CADDOK_TMPDIR") or tempfile.gettempdir()

    def __init__(self, logMethod=None):
        self._occurrenceTypes = None
        self.log = logMethod or self.log

    def setRelevantOccurrenceTypes(self, occurrenceTypes):
        """
        When creating occurrence entries, the writer will only consider
        docrel entries with one of the given reltypes.

        :param occurrenceTypes: list of occurrence types or None
        """
        if occurrenceTypes is None:
            self._occurrenceTypes = None
        else:
            self._occurrenceTypes = set(occurrenceTypes)

    @classmethod
    def makeAppInfoName(cls, primaryFName):
        """
        primaryFName : string
            filename of the primary file
        """
        appinfoName = "%s.appinfo" % primaryFName
        return appinfoName

    def writeFile(self, doc, appInfoFName, pdm2cadAttributes=None):
        """
        name : string
            the appinfo basename
        """
        self.doc = doc
        self.pdm2cadAttributes = pdm2cadAttributes or {}

        self.root = ElementTree.Element("appinfo")
        self._writeFile()

        # always generate property for all client names
        props = self.getProperties()
        self.root.append(props)

        tmppath = os.path.join(self.TMP_DIR, appInfoFName)
        try:
            with io.open(tmppath, "wb") as f:
                f.write(
                    (
                        ElementTree.tostring(
                            self.root, encoding="utf-8", pretty_print=True
                        )
                    )
                )
        except EnvironmentError as e:
            self.log(
                "Appinfowriter: saving appinfo to temp directory failed:"
                " %s" % six.text_type(e)
            )
            tmppath = None

        return tmppath

    def _writeFile(self):
        """
        To be implemented

        Content of appinfo file, e.g. occurrences, sheets, links...
        """
        pass

    def getProperties(self):
        props = ElementTree.Element("properties")

        # sort like WSM does
        for pdmAttrName in sorted(six.iterkeys(self.pdm2cadAttributes)):
            cadAttrName = self.pdm2cadAttributes[pdmAttrName]
            val = getattr(self.doc, pdmAttrName, u"")
            prop = ElementTree.Element("property")
            prop.attrib["id"] = six.text_type(cadAttrName)
            prop.attrib["value"] = six.text_type(val)
            props.append(prop)

        return props

    def getOccurrence(self, ref, occId):
        occ = None
        doc = Document.ByKeys(ref.z_nummer2, ref.z_index2)
        primFName = self.getPrimaryFilename(doc)

        if primFName is not None:
            occ = ElementTree.Element("occurrence")
            # set attribs sorted, lxml remembers the sequence
            occ.attrib["id"] = six.text_type(occId).zfill(3)
            occ.attrib["bom-relevant"] = "yes"
            occ.attrib["name"] = primFName
            occ.attrib["sortval"] = six.text_type(occId - 1)
            occ.attrib["suppressed"] = "no"

            cadref = ElementTree.Element("cadreference")
            cadref.attrib["path"] = primFName
            occ.append(cadref)
        else:
            self.log(
                "Appinfowriter: no primary file name found for occurrence"
                " link from %s to %s. No occurrence entry written."
                % (mkZName(ref), mkZName(doc))
            )

        return occ

    def getOccurences(self):
        occs = ElementTree.Element("occurrences")
        referencedDocs = []
        occId = 1
        for ref in self.doc.DocumentReferences:
            if self._occurrenceTypes is None or ref.reltype in self._occurrenceTypes:
                if ref.ReferencedDocument:
                    occ = self.getOccurrence(ref, occId)
                    if occ is not None:
                        occs.append(occ)
                        occId += 1
                        if not ref.cdb_link or ref.cdb_link == "0":
                            referencedDocs.append(ref.ReferencedDocument)

        return occs, referencedDocs

    def appendBom(self, referencedDocs):
        """
        Create a <BOM> element based on the referenced documents
        and the quantities and positions numbers in the database BOM (einzelteile).

        :param referencedDocs: list of Document
        """
        posId = 1
        targetItem = self.doc.Item
        if not targetItem:
            self.log(
                "Appinfowriter: no BOM written for document %s because it does not have an associated item."
                % mkZName(self.doc)
            )
        else:
            dbBom = self.getExistingBom()
            bom = ElementTree.Element("bom")
            bom.attrib["partno"] = targetItem.teilenummer
            bom.attrib["partver"] = targetItem.t_index
            for refDoc in referencedDocs:
                component = refDoc.Item
                if not component:
                    self.log(
                        "Appinfowriter: no BOM entry written for document %s in BOM of document %s because it does not have an associated item."
                        % (mkZName(refDoc), mkZName(self.doc))
                    )
                else:
                    existingEntries = dbBom[(component.teilenummer, component.t_index)]
                    if existingEntries:
                        for entry in existingEntries:
                            bomPos = ElementTree.Element("bomposition")
                            bomPos.attrib["id"] = six.text_type(posId).zfill(3)
                            posId += 1
                            bomPos.attrib["partno"] = component.teilenummer
                            bomPos.attrib["partver"] = component.t_index
                            bomPos.attrib["posno"] = str(entry.position)
                            bomPos.attrib["quantity"] = str(entry.menge)
                            bom.append(bomPos)
                    else:
                        # component does not exist yet ->
                        #  write a single bom position with quantity 1 and no position number
                        bomPos = ElementTree.Element("bomposition")
                        bomPos.attrib["id"] = six.text_type(posId).zfill(3)
                        posId += 1
                        bomPos.attrib["partno"] = component.teilenummer
                        bomPos.attrib["partver"] = component.t_index
                        bomPos.attrib["quantity"] = "1.0"
                        bom.append(bomPos)
            self.root.append(bom)

    def getExistingBom(self):
        """
        Precondition: self.doc must have an associated item.
        :return: dict((teilenummer, t_index) -> list of AssemblyComponent)
        """
        bom = defaultdict(list)
        for comp in self.doc.Item.Components:
            if comp.cadsource:
                if comp.cadsource.split(":")[0] == self.doc.erzeug_system.split(":")[0]:
                    bom[(comp.teilenummer, comp.t_index)].append(comp)
        return bom

    def getSheet(self, sheetId):
        sheet = ElementTree.Element("sheet")
        sheet.attrib["id"] = six.text_type(sheetId)
        sheet.attrib["number"] = "1"
        sheet.attrib["scale"] = "1.0"
        # write sortval like wsm does (not written by cad, its not in the appinfo.rnc)
        sheet.attrib["sortval"] = six.text_type(sheetId - 1)
        sheet.append(self.getViews())
        return sheet

    def getSheets(self):
        sheets = ElementTree.Element("sheets")
        sheets.append(self.getSheet(1))

        return sheets

    def getViews(self):
        views = ElementTree.Element("views")
        viewId = 1
        for ref in self.doc.DocumentReferences.Query("cad_link_bez <> 'DRW->FRM'"):
            if ref.ReferencedDocument:
                views.append(self.getView(ref, viewId))
                viewId += 1

        return views

    def getView(self, ref, viewId):
        view = None
        doc = Document.ByKeys(ref.z_nummer2, ref.z_index2)

        primFName = self.getPrimaryFilename(doc)
        if primFName:
            view = ElementTree.Element("view")
            view.attrib["id"] = six.text_type(viewId).zfill(3)
            # write sortval like wsm does (not written by cad, its not in the appinfo.rnc)
            view.attrib["sortval"] = six.text_type(viewId - 1)
            cadref = ElementTree.Element("cadreference")
            cadref.attrib["path"] = primFName
            view.append(cadref)
        else:
            self.log(
                "Appinfowriter: no primary file name found for view link"
                " from %s to %s. No view entry written." % (mkZName(ref), mkZName(doc))
            )

        return view

    def getLinks(self):
        # assumption: for this file type, all document references are links
        links = ElementTree.Element("links")
        for ref in self.doc.DocumentReferences:
            if ref.ReferencedDocument:
                links.append(self.getLink(ref))

        return links

    def getLink(self, ref):
        link = None
        doc = Document.ByKeys(ref.z_nummer2, ref.z_index2)
        primFName = self.getPrimaryFilename(doc)

        if primFName is not None:
            link = ElementTree.Element("link")
            link.attrib["id"] = primFName
            link.attrib["path"] = primFName
            link.attrib["type"] = "external"
        else:
            self.log(
                "Appinfowriter: no primary file name found for link from"
                " %s to %s. No link entry written." % (mkZName(ref), mkZName(doc))
            )

        return link

    def getPrimaryFilename(self, docRec):
        fName = None
        rs = docRec.getPrimaryFiles()

        if len(rs) == 1:
            fName = rs[0].cdbf_name

        elif len(rs) > 1:
            self.log(
                "Appinfowriter: multiple primary files found for document"
                " %s." % mkZName(docRec)
            )
            # try to find a single cdb_file which client name matches the
            # erzeug_system from the zeichnung object
            candidates = [r for r in rs if r.cdbf_type == docRec.erzeug_system]
            if len(candidates) == 1:
                fName = candidates[0].cdbf_name
                self.log("Appinfowriter: using primary file %s." % fName)
            else:
                candidatesStr = ", ".join([c.cdbf_name for c in candidates])
                self.log(
                    "Appinfowriter: determining primary file failed"
                    " (candidates: %s)" % candidatesStr
                )
        else:
            self.log(
                "Appinfowriter: no primary file found for document %s."
                % mkZName(docRec)
            )

        return fName

    def log(self, msg):
        sys.stderr.write("%s\n" % msg)
