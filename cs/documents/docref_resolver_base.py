#!/usr/bin/env python
# -*- mode: python; coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

# pylint: disable=protected-access
# pylint: disable=bad-continuation

"""
Implement CAD specific behaviour for document reference structure resolving.

Strategy pattern to adapt cs.documents.Document behaviour to different
CAD Systems. The class BaseStrategy implements the default behaviour, that
can be redefined for specific CAD Systems.
"""


import logging
from collections import namedtuple

from cdb import cad, sqlapi
from cdb.objects import NULL
from cs.documents import Document

_Logger = logging.getLogger(__name__)


class NoCadViewError(Exception):
    pass


SML_Info = namedtuple("SML_Info", ["sml_data", "teilenummer", "t_index"])


class BaseStrategy(object):
    def __init__(self, doc):
        self.document = doc
        self.children = None
        # multi sheet related
        self.sheet_count = 0
        self.sheet = 0
        try:
            self.sheet_count = int(doc.blattanz)
            if self.sheet_count >= 1:
                self.sheet = int(doc.blattnr)
        except Exception:  # nosec # pylint: disable=broad-except
            pass
        # FIXME: the following was contained in several CAD Model classes, but
        # is never used - determine if it can be thrown away
        if self.document.erzeug_system == NULL:
            ms = cad.getCADConfValue("ZVS Mehrblattzeichnungen", "default_cad")
        else:
            ms = cad.getCADConfValue(
                "ZVS Mehrblattzeichnungen", self.document.erzeug_system
            )
        self.manageSheets = cad.isTrue(ms[:4].upper())
        # project handling
        self._prjAttr = None
        self._prjValue = None
        self._include_wsm_refs = False  # temporary fix for E023381

    @property
    def docNo(self):
        return self.document.z_nummer

    @property
    def docIndex(self):
        return self.document.z_index

    @property
    def partNo(self):
        return self.document.teilenummer

    @property
    def partIndex(self):
        return self.document.t_index

    def getProjectValue(self):
        """ermitteln des Projektes zum Model

        Die  Ermittlung des Projektes  zum  Model  erfolgt  hier, in der   Basis
        Implementierung  ueber   das   'erzeug_system'.    In   Abhaengigkeit  vom
        'erzeug_system' wird das Attribut in Rel. 'zeichnung' ermittelt, das den
        Wert fuer das  Projekt traegt.  Zurueckgegeben  wird der Wert der in diesem
        Attribut zum Model hinterlegt ist.

        Vorraussetzung sind die, zum 'erzeug_system' gehoerenden Konfigurationen:

        - 'Project name'       == ENVIRON
        - 'Project attribute'  --> Attribut in Zeichnung in dem das Projekt hinterlegt ist

        ... sind diese    Konfigurationen nicht gegeben  oder   kann aus anderen
        Gruenden kein Wert ermittelt werden liefert die Methode 'None' zurueck.
        """
        if not self._prjValue:
            if not self._prjAttr:
                cadsys = self.document.erzeug_system
                if cad.getCADConfValue("Project name", cadsys) == "ENVIRON":
                    self._prjAttr = cad.getCADConfValue("Project attribute", cadsys)
                    self._prjValue = self.document[self._prjAttr]
            else:
                self._prjValue = self.document[self._prjAttr]
        return self._prjValue

    def getDrawingOfSheet(self):
        """Gibt bei Mehrblattzeichnungen das Document zurueck, das dem ersten
        Blatt entspricht. Dieses Dokument verwaltet die Primaerdatei, alle
        anderen haben nur Sekundaer-Repraesentationen.
        Im Normalfall (d.h. keine Mehrblattzeichnung) wird das Dokument
        selbst zurueckgegeben.
        """
        return self.document

    def getAllRefDocs(self):
        """Liste aller Documents (incl. /self/ ) der Ref-Struktur

        Ermittelt werden alle Objekte der Referenzstruktur die
        sich fuer /self/ ergeben. Zurueckgegeben wird eine Py-Liste
        der Dokumente. Jedes Document ist, auch bei Rekursion oder
        Mehrfachreferenzierung nur einmal in der Liste enthalten.
        """
        _refDocs = set()
        _smlDocs = set()
        self._addDocRecursive(
            _refDocs, _smlDocs, self.getDrawingOfSheet(), None, None, True
        )
        return list(_refDocs)

    def getSMLModels(self):
        """Liste aller SMLModelle die in der Ref-Struktur zu finden sind.

        Ermittelt werden alle Objekte der Refernzstruktur die
        sich fuer /self/ ergeben und vom Typ /SMLModel/ sind.
        Zurueckgegeben wird eine Liste von Tupeln (SML-Dokument, SML_Info, Rel-Typ).
        Jede Kombination ist, auch bei Rekursion oder Mehrfachreferenzierung
        nur einmal in der Liste enthalten.
        """
        _refDocs = set()
        _smlDocs = set()
        self._addDocRecursive(
            _refDocs, _smlDocs, self.getDrawingOfSheet(), None, None, False
        )
        return list(_smlDocs)

    def _addDocRecursive(
        self, all_docs, sml_docs, this_doc, sml_data, pRelType, skip_sml
    ):
        if sml_data is not None:
            sml_docs.add((this_doc, sml_data, pRelType))
            if not skip_sml or pRelType != "IRef":
                all_docs.add(this_doc)
        else:
            all_docs.add(this_doc)
        cs = this_doc._getCadStrategy()
        cs._include_wsm_refs = self._include_wsm_refs  # temporary fix for E023381
        for (child, child_sml_data, child_pRelType) in cs._getChildrenComplete():
            if child_sml_data is None:
                rec_call = child not in all_docs
            else:
                rec_call = (child, child_sml_data, child_pRelType) not in sml_docs
            if rec_call:
                self._addDocRecursive(
                    all_docs, sml_docs, child, child_sml_data, child_pRelType, skip_sml
                )

    def getChildren(self):
        """Get referenced documents of the next level"""
        if self.children is None:
            self.children = []
            self._computeDocRelChildren()
        return [entry[0] for entry in self.children]

    def _getChildrenComplete(self):
        if self.children is None:
            self.children = []
            self._computeDocRelChildren()
        return self.children

    def _append_child(self, childDoc, sml_data, pRelType):
        self.children.append((childDoc, sml_data, pRelType))

    def _computeDocRelChildren(self):
        """Compute a list of the direct (non-recursive) Child documents defined
        with DocumentReferences (aka cdb_doc_rel). Entries in cdb_doc_rel
        stored by the WSM for backward compatibility are ignored, as these
        are followed by traversing the WSM structure.
        This will be overwritten for CAD Systems that store the references
        differently in cdb_doc_rel.
        """
        refs = [
            dr
            for dr in self.document.DocumentReferences
            if dr.cdb_link == 0 and not self._is_wsm_ref(dr)
        ]
        for child in refs:
            (childDoc, sml_data, pRelType) = self._createChildDocument(child)
            if childDoc:
                self._append_child(childDoc, sml_data, pRelType)
            else:
                raise Exception(
                    "creation of child doc '%s'-'%s' reltype: %s failed !!"
                    % (child.z_nummer2, child.z_index2, child.reltype)
                )

    def _is_wsm_ref(self, doc_ref):
        if self._include_wsm_refs:
            # temporary fix for E023381:
            # returning False here means that this doc ref gets included, no
            # matter if it is a WSM reltype or not!
            return False
        else:
            # a new attribute to be able to run classic
            # integrations along with Workspace Manager
            NO_VALUE = object()
            if getattr(doc_ref, "owner_application", NO_VALUE) not in [NO_VALUE, ""]:
                ret = doc_ref.owner_application == "WSM"
            else:
                ret = doc_ref.reltype == "WSM"
            return ret

    def _createChildDocument(self, child_ref):
        """Create a document instance from a DocumentReference. Depending on
        the reltype, an SML reference is assumed.
        """
        smlInfo = None
        if child_ref.reltype.endswith("VRef"):
            cDoc = child_ref.ReferencedDocument
            smlData = cad.get_sml_data(
                "", "", cDoc.teilenummer, cDoc.t_index, ".", cDoc.erzeug_system
            )
            smlInfo = SML_Info(
                sml_data=smlData, teilenummer=cDoc.teilenummer, t_index=cDoc.t_index
            )
        elif child_ref.reltype.endswith("IRef"):
            # bei SMLModellen deren Beziehung zum Vater eine IRef
            # ist, sind docNo und docIndex nicht gesetzt (dies sind
            # die Varianten, die nur ueber einen Eintrag in teile_stamm
            # verfuegen, ein eintrag in zeichnung gibts nicht).
            smlData = cad.get_sml_data(
                "",
                "",
                child_ref.z_nummer2,
                child_ref.z_index2,
                ".",
                self.document.erzeug_system,
            )
            smlInfo = SML_Info(
                sml_data=smlData,
                teilenummer=child_ref.z_nummer2,
                t_index=child_ref.z_index2,
            )
            if not smlData:
                msg = "no sml data for %s-%s." % (
                    child_ref.z_nummer2,
                    child_ref.z_index2,
                )
                _Logger.info(msg)
                raise Exception(msg)

            sachgruppe = smlData.split("@")[0]
            if not sachgruppe:
                # Im Fall der ProE- Integration ('IRef') handelt es
                # sich nicht unbedingt um einen Fehler.  Diese Instanz
                # kann z.B. mit dem Modull für Verwalten der
                # Instanzenvon von Fam.Tabellen verwaltet werden.  In
                # diesem Fall ist keine SML-Leiste in CIM DATABASE zu
                # erwarten.
                _Logger.warning(
                    "no 'sc' for %s-%s.", child_ref.z_nummer2, child_ref.z_index2
                )
                return ("", smlInfo, child_ref.reltype.split(":")[-1])

            (aDocNo, aDocIndex) = self.findAnsicht(sachgruppe)
            cDoc = Document.ByKeys(aDocNo, aDocIndex)
        else:
            cDoc = child_ref.ReferencedDocument
        return (cDoc, smlInfo, child_ref.reltype.split(":")[-1])

    def findAnsicht(self, sachgruppe):
        ansicht = self.getBindView()
        cond = "pset_id = '%s' and view_name ='%s'" % (
            sqlapi.quote(sachgruppe),
            sqlapi.quote(ansicht),
        )
        docRecSet = sqlapi.RecordSet2("cdbsml_pset_view", cond)

        if docRecSet:
            # Primäres cad_system (z.B. 'ProE', 'Catia V5') des
            # self-Dokuments ermitteln: z.B. ProE:GenAssembly -> ProE
            cad_system = self.document.erzeug_system.split(":")[0]

            for docrec in docRecSet:
                z_nummer = docrec["z_nummer"]
                z_index = docrec["z_index"]
                view_cDoc = Document.ByKeys(z_nummer, z_index)
                # Primäres cad_system des Ansichts-Modells
                # (z.B. ProE:Part -> ProE) soll mit dem cad_system des
                # self-Modells (z.B. ProE:Assembly -> ProE)
                # übereinstimmen:
                view_cad_system = view_cDoc.erzeug_system.split(":")[0]
                if view_cad_system == cad_system:
                    return (z_nummer, z_index)

            raise NoCadViewError(
                "No ansicht found for sachgruppe %s with cad_system: %s"
                % (sachgruppe, cad_system)
            )
        else:
            raise NoCadViewError("No ansicht found for sachgruppe %s" % (sachgruppe))
        return ("", "")

    def getBindView(self):  # pylint: disable=no-self-use
        """Ansicht ermitteln, erst einmal immer "3DVIEW"

        siehe ProE (aus Sachgruppe und references). Sonderfall fuer Vulkan, sonst
        wird immer "3DVIEW" angenommen
        """
        return "3DVIEW"


class DefaultStrategy(BaseStrategy):
    """Fallback implementation, used if no other more specialized strategy
    matches.
    """

    priority = 0
    match_expression = ".*"
