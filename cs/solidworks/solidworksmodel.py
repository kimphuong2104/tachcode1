#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
# $Id$
#
# Copyright (C) 2000 - 2002 by CONTACT Software GmbH.
# All rights reserved.
# http://www.contact.de/
#
# pylint: disable-msg=R0904
"""
Spezialisierte Implementierung fuer das Rahmenhandling von Solidworks
+ Erweiterung fuer die Beruecksichtigung von Konfigurationen
"""

from __future__ import absolute_import
from cs.documents.docref_resolver_base import BaseStrategy
from cs.documents import Document, DocumentReference


class SolidWorksModel(BaseStrategy):
    """Spezialisierung der /BaseStrategy/ Klasse für CAD-System SolidWorks
    """
    priority = 10
    match_expression = "SolidWorks"

    def __init__(self, doc):
        """ Konstruktor

            Initialisiert das Model  durch aufrufen des Konstruktors der Basisklasse
            /BaseStrategy/. Art und  Umfang  der bereitgestellten  Eigenschaften
            kann dort nachgelesen werden.
        """
        BaseStrategy.__init__(self, doc)
        # SolidWorks fuellt die Blattanzahl nicht aus daher
        # die nr auch ermitteln, wenn diese 0 ist
        if doc.blattnr:
            self.sheet = int(doc.blattnr)

    def getDrawingOfSheet(self):
        """ ermitteln des Dokuments mit Seite 0

            Diese Methode ermittelt das erste Blatt und gibt eine Modellinstanz (der
            Zeichnung) zurück.

            Wenn eine Zeichnung aus mehr als einem Blatt besteht, so zeigen letzten
            endes alle Blätter auf das selbe Dokument (die Zeichnung). Die Zeichnung
            selbst entspricht dem Blatt 1 und nur  über Blatt 1 können  die
            Native-Daten erreicht werden. Bei SolidWorks ist diese Beziehung in der
            cdb_doc_rel als Beziehungstyp 'solidworks_sheet' definiert.
        """
        if self.document.erzeug_system == "SolidWorks:sht":
            # es gibt mehrere  Blätter und dies ist nicht  Blatt 1 ... ermitteln
            # des Blatt 1
            cond = "z_nummer2 = '%s' AND z_index2 = '%s' AND reltype = 'solidworks_sheet'" \
                   % (self.docNo, self.docIndex)
            refs = DocumentReference.Query(condition=cond)
            docNo, docIndex = refs[0].z_nummer, refs[0].z_index
            drawingModel = Document.ByKeys(docNo, docIndex)
            return drawingModel
        elif self.document.erzeug_system == "SolidWorks:cfg":
            # ermitteln des Dokument, das das Modell der Konfiguration enthaelt
            cond = "z_nummer2 = '%s' AND z_index2 = '%s' AND reltype = 'solidworks_cfg'" \
                   % (self.docNo, self.docIndex)
            refs = DocumentReference.Query(condition=cond)
            docNo, docIndex = refs[0].z_nummer, refs[0].z_index
            drawingModel = Document.ByKeys(docNo, docIndex)
            return drawingModel
        else:
            return self.document

    def _computeDocRelChildren(self):
        """ Spezialisierung der Referenzstruktur

            Hier dürfen für Masterzeichnungen keine Sheets ausgeleitet werden. Wenn
            ein Sheet ubergeben wird,  muss  fuer das Sheet die  Referenz der
            Hauptzeichnung verwendet werden.
        """
        # bei einem sheet dieses auf das Haupdokument umsetzen
        drawModel = self.getDrawingOfSheet()
        if drawModel:
            # Verweise auf sheets und Konfigurationen werden nicht verfolgt
            refs = [dr for dr in drawModel.DocumentReferences
                    if dr.reltype not in ['solidworks_sheet',
                                          'solidworks_cfg'] and not self._is_wsm_ref(dr)]
            for child in refs:
                (childDoc, sml_data, pRelType) = self._createChildDocument(child)
                if childDoc:
                    self._append_child(childDoc, sml_data, pRelType)
                else:
                    raise Exception("creation of child model '%s'-'%s' reltype: %s failed !!"
                                    % (child.z_nummer2, child.z_index2, child.reltype))
