#!/usr/bin/env python
# -*- python -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from cdb import ue
from cdb import sig
from cdb.classbody import classbody

from cdb.objects import Object
from cdb.objects import Forward
from cdb.objects import Reference_1
from cdb.objects import Reference_N
from cdb.objects import ReferenceMethods_N
from cdb.objects import Rule

from cs.ec import EngineeringChange
from cs.vp.ec_cad import PlannedChangeDocumentReference
from cs.documents import Document
from cs.documents import DocumentECN

ACCOMPANYING_DOCUMENTS_BRIEFCASE_NAMES = [
    "Begleitdokumente",
    "Accompanying Documents"
]

BRIEFCASE_NAMES = [
    "Geänderte CAD Dokumente",
    "Geänderte CAD-Dokumente",
    "geänderte CAD-Dokumente",
    "geänderte CAD Dokumente",
    "Changed CAD Documents"
]


@classbody
class DocumentECN(object):

    # Attributmapping: cdbecm_ec: aenderung
    ECDefaultsMap = {"c_event": "a_event",
                     "c_source": "a_source"
                     }

    EC = ReferenceMethods_N(EngineeringChange,
                            lambda self: self.Document.EngineeringChange)

    def set_a_beschreib(self):
        """
        Reads the attribute `b_beschreib` from self and
        copies the first line to `a_beschreib`. The value
        is shortened if `a_beschreib` does not have the
        necessary size.
        """
        if self.HasField("a_beschreib") and self.HasField("b_beschreib"):
            max_size = self.GetFieldByName("a_beschreib").length
            if max_size:
                try:
                    new_val = self.b_beschreib[:max_size]
                    # The old (2.9.7) algorithm that stops at the
                    # first char < ' '
                    for pos in range(0, len(new_val)):
                        if ord(new_val[pos]) < ord(' '):
                            new_val = new_val[:pos]
                            break
                    self.a_beschreib = new_val
                except Exception as e:
                    # Failed to get the value
                    raise ue.Exception(1024, str(e))


@classbody
class Document(object):

    def CheckECReference(self, old_ec_id, new_ec_id):

        """Prüfung der EC Zuordnung beim Ändern (pre), Statuswechsel (pre) und Indizieren (post_mask).
        Exception, falls eine EC Zuordnung erforderlicht ist und new_ec_id leer ist.
        Bei Änderung der EC Zuordnung (old_ec_id != new_ec_id) wird
        geprüft, ob der neue EC zugeordnet werden darf:
        - Typprüfung - siehe Methode MatchECType
        - Prüfung auf Zuordnung als 'geplante Änderung' - siehe CheckPlannedChanges
        """

        # for backward compatibility with standard installations not using rules
        if not new_ec_id and self.ECReferenceMandatory():
            raise ue.Exception("cdbecm_err_ecref")

        if not new_ec_id:
            self.MatchECType(new_ec_id)
        elif old_ec_id != new_ec_id:
            self.MatchECType(new_ec_id)
            self.CheckPlannedChanges(new_ec_id)

    def CheckPlannedChanges(self, ec_id):

        """Prüfung, ob das Dokument dem EC als geplante Änderung zugeordnet ist."""

        ec = EngineeringChange.ByKeys(ec_id)
        if (ec and ec.Category.planned_changes_only and
                not PlannedChangeDocumentReference.KeywordQuery(z_nummer=self.z_nummer, cdb_ec_id=ec_id)):
            # Das Dokument ist dem EC nicht als zu änderndes Dokument zugeordnet.
            # Die EC Kategorie verlangt die Zuordnung aller geplanten Änderungen im voraus.
            raise ue.Exception("cdbecm_err_assign6")

    def MatchECType(self, ec_id):

        """Prüfung, ob der EC zugeordnet werden darf.
        Die Prüfung erfolgt bei jeder Änderung der EC Zuordnung (Ändern, Statuswechel, Indizieren).
        """
        ec = None
        if ec_id:
            ec = EngineeringChange.ByKeys(ec_id)
            # Keine Zuordnung zu EC Vorlagen
            if ec.template:
                raise ue.Exception("cdbecm_err_assign7")
        EngineeringChange.allow(self, ec)

    def ECReferenceMandatory(self):
        """ Liefert True, wenn für das Dokument eine EC Zuordnung Pflicht ist.
        Die Prüfung erfolgt beim Ändern (pre), Statuswechsel (pre) und Indizieren (post_mask).

        Deprecated: should return always False in installations using rules. """

        return False

    def ECReferenceModifiable(self, state=None):
        """ Liefert True, wenn die EC Zuordnung geändert werden darf. """
        if Rule.ByKeys(self.__ec_ref_modifiable_rule__):
            return self.MatchRule(self.__ec_ref_modifiable_rule__)
        else:
            # Backward compatibility for standard installations not using rules
            if state is None:
                state = self.status
            return state == 0

    def ECMModifyPre(self, ctx):
        # Falls EC Zuordnung geändert wurde, wird die ursprüngliche
        # EC Zuordnung im post ue benötigt
        ctx.set("cdb::argument.old_ec_id", ctx.object.cdb_ec_id)
        self.CheckECReference(ctx.object.cdb_ec_id, self.cdb_ec_id)

    def ECMModifyPreMask(self, ctx):
        if not self.ECReferenceModifiable():
            ctx.set_readonly("cdb_ec_id")

    def ECMWFStepPreMask(self, ctx):
        if not self.ECReferenceModifiable() and self.cdb_ec_id:
            ctx.set_readonly("cdb_ec_id")

    def ECMStateChangePre(self, ctx):
        if "cdb_ec_id" in ctx.dialog.get_attribute_names() and ctx.dialog.cdb_ec_id and self.cdb_ec_id != ctx.dialog.cdb_ec_id:
            # EC Zuordnung über Statuswechselmaske geändert:
            # Prüfung, ob der neue EC vom richtigen Typ ist
            self.MatchECType(ctx.dialog.cdb_ec_id)
            self.CheckPlannedChanges(ctx.dialog.cdb_ec_id)
            # EC Setzen
            old_ec = self.cdb_ec_id
            self.cdb_ec_id = ctx.dialog.cdb_ec_id
            self._ECReferenceModifyPost(old_ec, self.cdb_ec_id)
        else:
            self.CheckECReference(ctx.object.cdb_ec_id, self.cdb_ec_id)

    def ECMModifyPost(self, ctx):
        self._ECReferenceModifyPost(ctx.sys_args.old_ec_id, self.cdb_ec_id)

    def _ECReferenceModifyPost(self, old_ec, new_ec):
        """
        Wird aufgerufen nach Änderung der EC Zuordnung. Die Zuordnung kann beim
        Statuswechsel oder durch das Datenblatt geändert werden.
        """
        if old_ec != new_ec:
            # EC Zuordnung des zugeordneten Artikels ändern, sofern dieser
            # dem selben EC zugeordnet war.
            if self.Item and self.Item.cdb_t_ec_id == old_ec:
                self.Item.cdb_t_ec_id = new_ec

    def _getPCDReferences(self):
        return PlannedChangeDocumentReference.SQL("SELECT a.* FROM cdbecm_ec2pmodel a, cdbecm_ec b"
                                                  " WHERE a.cdb_ec_id = b.cdb_ec_id"
                                                  " AND b.status IN (%s) AND a.z_nummer = '%s'"
                                                  % ("40, 50", self.z_nummer))

    def _checkIndexAllowed(self):
        ec_numbers = []
        for plannedChangeItem in PlannedChangeDocumentReference.KeywordQuery(z_nummer=self.z_nummer, z_index=self.z_index):
            # Wenn EC Zurodnungen existieren, reicht es aus wenn einer der ECs das Index-Recht gewährt.
            # So wird verhindert, das Dokumente, die verworfenen ECs zugeordnet sind nicht mehr
            # indiziert werden können, so wie es mit dem excliven Beziehungsrecht der Fall war.
            ec = plannedChangeItem.EC
            if ec.status in [180, 200]:
                # skip check for finished ECs
                continue
            elif ec.CheckAccess('ec_index_item'):
                return
            else:
                ec_numbers.append(ec.cdb_ec_id)
        if ec_numbers:
            raise ue.Exception("cdbecm_err_index", ', '.join(ec_numbers))

    def ECMIndexPreMask(self, ctx):
        self._checkIndexAllowed()

        # Vorbelegung EC, wenn das Dokument als geplante Änderung
        # genau einem bereits genehmigten oder sich in arbeit befindlichen
        # EC zugeordnet ist.
        refs = self._getPCDReferences()
        if len(refs) == 1:
            ctx.set("index_ec_id", refs[0].cdb_ec_id)
            ctx.set_readonly("index_ec_id")

    def ECMIndexPre(self, ctx):
        if ctx.dialog:
            index_ec_id = getattr(ctx.dialog, "index_ec_id", "")
            self.CheckECReference("", index_ec_id)

        self._checkIndexAllowed()

        # Wenn wir im Kontext eines ECs Dokumente/CAD-Dokumente versionieren, soll der
        # neue Index nicht in zu ändernde CAD-Dokumente bzw. Begleitdokumente landen
        if ctx.relationship_name in ("cdbecm_ec2pmodels", "cdbecm_ec2docs"):
            ctx.skip_relationship_assignment()
        # Note: Im Gegensatz zu Artikeln funktioniert das bei Dokumenten mit ctx.set(...)
        if ctx.interactive or ctx.uses_webui:
            # Versuche den Index aus dem Dialog zu nutzen
            self.cdb_ec_id = getattr(ctx.dialog, "index_ec_id", "")
        else:
            # Falls Dialogfeld nicht zugreifbar (weil Indizierung via Batch angestoßen)
            #
            refs = self._getPCDReferences()
            if len(refs) == 1:
                self.cdb_ec_id = refs[0].cdb_ec_id

    def ECMIndexPost(self, ctx):
        if ctx.error:
            return
        if self.ChangeNotice:
            EngineeringChange.ApplyDefaultsFromEC(self.ChangeNotice)
        # Add document to the running workflows
        ec = EngineeringChange.ByKeys(cdb_ec_id=self.cdb_ec_id)
        if ec:
            ec.addToRunningWorkflows(BRIEFCASE_NAMES, self)

    def ECMCopyPreMask(self, ctx):
        if ctx.get_current_mask() == "initial::predicate_mask":
            self.cdb_ec_id = ""
            self._preset_project_from_ec(ctx)

    def ECMCreatePreMask(self, ctx):
        self._preset_project_from_ec(ctx)

    def _preset_project_from_ec(self, ctx):
        if ctx.relationship_name == 'cdbecm_ec2docs':
            ec = EngineeringChange.ByKeys(ctx.parent.cdb_ec_id)
            if ec:
                self.cdb_project_id = ec.cdb_project_id


if hasattr(Document, "cdb_ec_id"):
    Document.EngineeringChange = Reference_1(EngineeringChange, Document.cdb_ec_id)
    Document.__ec_ref_modifiable_rule__ = "cdbecm: EC Reference modifiable"

    # register user exits for ec handling
    # each user exit calls an instance method of Document,
    # customers can override these instance methods in subclasses of Document
    # e.g. instead of overriding ecm_state_change_pre, customers
    # should override Document.ECMStateChangePre

    @sig.connect(Document, "state_change", "pre")
    def ecm_state_change_pre(doc, ctx):
        doc.ECMStateChangePre(ctx)

    @sig.connect(Document, "modify", "pre_mask")
    def ecm_modify_pre_mask(doc, ctx):
        doc.ECMModifyPreMask(ctx)

    @sig.connect(Document, "wf_step", "pre_mask")
    def ecm_wf_step_pre_mask(doc, ctx):
        doc.ECMWFStepPreMask(ctx)

    @sig.connect(Document, "modify", "pre")
    def ecm_modify_pre(doc, ctx):
        doc.ECMModifyPre(ctx)

    @sig.connect(Document, "modify", "post")
    def ecm_modify_post(doc, ctx):
        doc.ECMModifyPost(ctx)

    @sig.connect(Document, "index", "pre")
    def ecm_index_pre(doc, ctx):
        doc.ECMIndexPre(ctx)

    @sig.connect(Document, "index", "post")
    def ecm_index_post(doc, ctx):
        doc.ECMIndexPost(ctx)

    @sig.connect(Document, "index", "pre_mask")
    def ecm_index_pre_mask(doc, ctx):
        doc.ECMIndexPreMask(ctx)

    @sig.connect(Document, "copy", "pre_mask")
    def ecm_copy_pre_mask(doc, ctx):
        doc.ECMCopyPreMask(ctx)

    @sig.connect(Document, "create", "pre_mask")
    def ecm_create_pre_mask(doc, ctx):
        doc.ECMCreatePreMask(ctx)

fAccompanyingDocumentReference = Forward(__name__ + ".AccompanyingDocumentReference")


class AccompanyingDocumentReference(Object):
    __maps_to__ = "cdbecm_ec2doc"
    __classname__ = "cdbecm_ec2doc"

    EC = Reference_1(EngineeringChange, fAccompanyingDocumentReference.cdb_ec_id)
    Document = Reference_1(Document,
                           fAccompanyingDocumentReference.z_nummer,
                           fAccompanyingDocumentReference.z_index)

    def AddToWorkflow(self, ctx):
        self.EC.addToRunningWorkflows(ACCOMPANYING_DOCUMENTS_BRIEFCASE_NAMES, self.Document)

    def RemoveFromWorkflow(self, ctx):
        self.EC.removeFromRunningWorkflows(ACCOMPANYING_DOCUMENTS_BRIEFCASE_NAMES, self.Document)

    event_map = {
        (('create'), 'post'): "AddToWorkflow",
        (('delete'), 'post'): "RemoveFromWorkflow"
    }


@classbody
class EngineeringChange(object):

    Documents = Reference_N(Document, Document.cdb_ec_id == EngineeringChange.cdb_ec_id)

    def _getAccompanying_Documents(self):
        return self.SimpleJoinQuery(Document, AccompanyingDocumentReference)

    AccompanyingDocuments = ReferenceMethods_N(Document, _getAccompanying_Documents)
    # AccompanyingDocumentReferences = Reference_N(
    #    AccompanyingDocumentReference, AccompanyingDocumentReference.cdb_ec_id == EngineeringChange.cdb_ec_id
    # )
    AccompanyingDocumentReferences = Reference_N(
        fAccompanyingDocumentReference, fAccompanyingDocumentReference.cdb_ec_id == EngineeringChange.cdb_ec_id
    )


for briefcase_name in BRIEFCASE_NAMES:
    EngineeringChange.registerManagedProcessBriefcase(briefcase_name, EngineeringChange.Documents)

for briefcase_name in ACCOMPANYING_DOCUMENTS_BRIEFCASE_NAMES:
    EngineeringChange.registerManagedProcessBriefcase(briefcase_name, EngineeringChange.AccompanyingDocuments)
