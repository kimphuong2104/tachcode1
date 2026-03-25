# !/usr/bin/env powerscript
# -*- python -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

__revision__ = "$Id$"

from cdb import ue
from cdb.classbody import classbody

from cdb.objects import Object
from cdb.objects import Forward
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import ReferenceMethods_N

from cs.ec import EngineeringChange
from cs.documents import Document

fPlannedChangeDocumentReference = Forward(__name__ + ".PlannedChangeDocumentReference")

PLANNED_BRIEFCASE_NAMES = [
    "zu ändernde CAD Dokumente",
    "Zu ändernde CAD-Dokumente",
    "zu ändernde CAD-Dokumente",
    "Zu ändernde CAD-Dokumente",
    "CAD Documents to be changed", "CAD-documents to be changed"
]


class PlannedChangeDocumentReference(Object):
    __maps_to__ = "cdbecm_ec2pmodel"
    __classname__ = "cdbecm_ec2pmodel"

    __accept_state_list__ = [200]

    EC = Reference_1(EngineeringChange, fPlannedChangeDocumentReference.cdb_ec_id)
    Document = Reference_1(Document,
                           fPlannedChangeDocumentReference.z_nummer,
                           fPlannedChangeDocumentReference.z_index)

    def AcceptReference(self, ctx):
        # Keine Zuordnung zu Vorlagen
        if self.EC.template:
            raise ue.Exception("cdbecm_err_assign7")
        if self.Document.status not in self.__accept_state_list__:
            # Es können nur freigegebene Dokumente zugeordnet werden
            raise ue.Exception("cdbecm_err_assign3")

    def AddToWorkflow(self, ctx):
        self.EC.addToRunningWorkflows(PLANNED_BRIEFCASE_NAMES, self.Document)

    def RemoveFromWorkflow(self, ctx):
        self.EC.removeFromRunningWorkflows(PLANNED_BRIEFCASE_NAMES, self.Document)

    def CheckECState(self, ctx):
        if self.EC.status != 0:
            # Die Zuordnung von geplanten Änderungen kann nicht mehr geändert werden.
            raise ue.Exception("cdbecm_err_assign4")

    event_map = {
        (('create', 'delete'), 'pre'): "CheckECState",
        (('create'), 'pre'): "AcceptReference",
        (('create'), 'post'): "AddToWorkflow",
        (('delete'), 'post'): "RemoveFromWorkflow"
    }


@classbody
class EngineeringChange(object):

    PlannedChangesDocumentReferences = Reference_N(PlannedChangeDocumentReference,
                                                   PlannedChangeDocumentReference.cdb_ec_id == EngineeringChange.cdb_ec_id)

    def _PlannedChangesDocuments(self):
        return [ref.Document for ref in self.PlannedChangesDocumentReferences]

    PlannedChangesDocuments = ReferenceMethods_N(Document, _PlannedChangesDocuments)


for briefcase_name in PLANNED_BRIEFCASE_NAMES:
    EngineeringChange.registerManagedProcessBriefcase(briefcase_name, EngineeringChange.PlannedChangesDocuments)
