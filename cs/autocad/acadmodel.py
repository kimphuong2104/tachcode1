#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
# $Id$
#
# Copyright (C) 1990 - 2006 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# pylint: disable-msg=R0904

from __future__ import absolute_import
from cs.documents.docref_resolver_base import BaseStrategy
from cs.documents import Document, DocumentReference


class AcadModel(BaseStrategy):
    """Spezialisierung der /BaseStrategy/ Klasse für CAD-System AutoCAD [Mechanical]
    """
    priority = 10
    match_expression = "acad"

    def __init__(self, doc):
        """ Konstruktor

            Initialisiert das Model  durch aufrufen des Konstruktors der Basisklasse
            /BaseStrategy/. Art und  Umfang  der bereitgestellten  Eigenschaften
            kann dort nachgelesen werden.
        """
        BaseStrategy.__init__(self, doc)

    def checkoutFile(self, dstFPName, suffix=None):
        """

        Acad specific overload: If checkouting a file for a sheet,
        determine the appropriate model object and use its checkoutFile
        method.
        The implementation in the parent isnt capable checkouting files for
        sheets.
        """
        if (self.erzeug_system in ["acad:sht", "acad_mechanical:sht"]):
            drawingModel = self.getDrawingOfSheet()
            return drawingModel.checkoutFile(dstFPName, suffix)
        else:
            return self.document.checkoutFile(self, dstFPName, suffix)

    def _getwsmdrawingofsheetwsm(self, sheetDoc):
        """
        :return Document: The Document containing the drawing file for the sheet document
        """
        drawingDoc = sheetDoc
        for sref in sheetDoc.DrawingOfSheetReferences:
            if sref.z_index == sref.z_index_origin:
                drawingDoc = sref.Drawing
        return drawingDoc

    def getDrawingOfSheet(self):
        """ ermitteln des Dokuments mit Seite 0

           Diese Methode ermittelt das erste Blatt und gibt eine Modellinstanz (der
           Zeichnung) zurück.

           Wenn eine Zeichnung aus mehr als einem Blatt besteht, so zeigen letzten
           endes alle Blätter auf das selbe Dokument (die Zeichnung).
           Die Zeichnung
           selbst entspricht dem Blatt 1 und nur über Blatt 1 können die
           Native-Daten erreicht werden. Bei AutoCAD ist diese Beziehung in
           der cdb_doc_rel als Beziehungstyp 'acad_sheet' definiert.
        """
        if "additional_document_type" in self.document.keys():
            # 0 = no multisheet
            # 1 = multisheet master
            # 2 = multisheet sheet
            mainDoc = self.document
            if mainDoc.additional_document_type == u"2":
                drawingDoc = self._getwsmdrawingofsheetwsm(mainDoc)

                if drawingDoc is not None:
                    mainDoc = drawingDoc
            return mainDoc
        else:
            if self.document.erzeug_system in ["acad:sht", "acad_mechanical:sht"]:
                # es gibt mehrere  Blätter und dies ist nicht Blatt 1 ... ermitteln
                # des Blatt 1
                cond = "z_nummer2 = '%s' AND z_index2 = '%s' AND reltype = 'acad_sheet'" \
                       % (self.docNo, self.docIndex)
                refs = DocumentReference.Query(condition=cond)
                docNo, docIndex = refs[0].z_nummer, refs[0].z_index
                drawingModel = Document.ByKeys(docNo, docIndex)
                return drawingModel
            else:
                return self.document

    def _computeDocRelChildren(self):
        """ Spezialisierung der Referenzstruktur

            Hier dürfen für Masterzeichnungen keine Sheets ausgeleitet werden.
            Wenn ein  Sheet ubergeben  wird, muss fuer das Sheet die Referenz der
            Hauptzeichnung verwendet werden.
        """
        # bei einem sheet dieses auf das Haupdokument umsetzen
        drawModel = self.getDrawingOfSheet()
        if drawModel:
            # Verweise auf sheets werden nicht verfolgt
            refs = [dr for dr in drawModel.DocumentReferences
                    if dr.reltype != 'acad_sheet' and not self._is_wsm_ref(dr)]
            for child in refs:
                (childDoc, sml_data, pRelType) = self._createChildDocument(child)
                if childDoc:
                    self._append_child(childDoc, sml_data, pRelType)
                else:
                    raise Exception("creation of child model '%s'-'%s' reltype: %s failed !!"
                                    % (child.z_nummer2, child.z_index2, child.reltype))
