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
from cs.vp.items import Item
from cs.vp.items import ProcessPartReference

fItemECN = Forward(__name__ + ".ItemECN")
fPlannedChangeItemReference = Forward(__name__ + ".PlannedChangeItemReference")

BRIEFCASE_NAMES = [
    "geänderte Artikel",
    "Geänderte Artikel",
    "Changed Items",
    "Changed Parts"
]

PLANNED_BRIEFCASE_NAMES = [
    "zu ändernde Artikel",
    "Zu ändernde Artikel",
    "Parts to be changed",
    "Items to be changed"
]


class ItemECN(Object):
    __maps_to__ = "cdb_part_mod"
    __classname__ = "cdbecm_item_ecn"

    # Attributmapping: cdbecm_ec: cdb_part_mod
    ECDefaultsMap = {"c_event": "event",
                     "c_source": "source"
                     }

    Item = Reference_1(Item, fItemECN.teilenummer, fItemECN.t_index)
    EC = ReferenceMethods_N(EngineeringChange,
                            lambda self: self.Item.EngineeringChange)


class PlannedChangeItemReference(Object):
    __maps_to__ = "cdbecm_ec2pitem"
    __classname__ = "cdbecm_ec2pitem"

    __accept_state_list__ = [200, 300]

    EC = Reference_1(EngineeringChange, fPlannedChangeItemReference.cdb_ec_id)
    Item = Reference_1(Item,
                       fPlannedChangeItemReference.teilenummer,
                       fPlannedChangeItemReference.t_index)

    def AcceptReference(self, ctx):
        # Keine Zuordnung zu Vorlagen
        if self.EC.template:
            raise ue.Exception("cdbecm_err_assign7")
        if self.Item.status not in self.__accept_state_list__:
            # Es können nur freigegebene Artikel zugeordnet werden
            raise ue.Exception("cdbecm_err_assign2")

    def AddToWorkflow(self, ctx):
        self.EC.addToRunningWorkflows(PLANNED_BRIEFCASE_NAMES, self.Item)

    def RemoveFromWorkflow(self, ctx):
        self.EC.removeFromRunningWorkflows(PLANNED_BRIEFCASE_NAMES, self.Item)

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
class Item(object):

    ChangeNotice = Reference_1(ItemECN, Item.teilenummer, Item.t_index)

    def CheckECReference(self, old_ec_id, new_ec_id):

        """Prüfung der EC Zuordnung beim Ändern (pre), Statuswechsel (pre) und Indizieren (post_mask).
        Exception, falls eine EC Zuordnung erforderlich ist und new_ec_id leer ist.
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

        """Prüfung, ob der Artikel dem EC als geplante Änderung zugeordnet ist."""

        ec = EngineeringChange.ByKeys(ec_id)
        if (
            ec and ec.Category.planned_changes_only and
            not PlannedChangeItemReference.KeywordQuery(teilenummer=self.teilenummer, cdb_ec_id=ec_id)
        ):
            # Der Artikel ist dem EC nicht als zu ändernder Artikel zugeordnet.\n
            # Die EC Kategorie verlangt die Zuordnung aller geplanten Änderungen im voraus.
            raise ue.Exception("cdbecm_err_assign8")

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
        """ Liefert True, wenn für den Artikel eine EC Zuordnung Pflicht ist.
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
        ctx.set("cdb::argument.old_ec_id", ctx.object.cdb_t_ec_id)
        self.CheckECReference(ctx.object.cdb_t_ec_id, self.cdb_t_ec_id)

    def ECMModifyPreMask(self, ctx):
        if not self.ECReferenceModifiable():
            ctx.set_readonly("cdb_t_ec_id")

    def ECMWFStepPreMask(self, ctx):
        if not self.ECReferenceModifiable() and self.cdb_t_ec_id:
            ctx.set_readonly("cdb_t_ec_id")

    def ECMStateChangePre(self, ctx):
        if not ctx.batch and \
                "cdb_t_ec_id" in ctx.dialog.get_attribute_names() and \
                ctx.dialog.cdb_t_ec_id and \
                self.cdb_t_ec_id != ctx.dialog.cdb_t_ec_id:
            # EC Zuordnung über Statuswechselmaske geändert:
            # Prüfung, ob der neue EC vom richtigen Typ ist
            self.MatchECType(ctx.dialog.cdb_t_ec_id)
            self.CheckPlannedChanges(ctx.dialog.cdb_t_ec_id)
            # EC Setzen
            self.cdb_t_ec_id = ctx.dialog.cdb_t_ec_id
        else:
            self.CheckECReference(ctx.object.cdb_t_ec_id, self.cdb_t_ec_id)

    def _getPCIReferences(self):
        return PlannedChangeItemReference.SQL("SELECT a.* FROM cdbecm_ec2pitem a, cdbecm_ec b"
                                              " WHERE a.cdb_ec_id = b.cdb_ec_id"
                                              " AND b.status IN (%s) AND a.teilenummer = '%s'" %
                                              ("40, 50", self.teilenummer))

    def _checkIndexAllowed(self):
        ec_numbers = []
        for plannedChangeItem in PlannedChangeItemReference.KeywordQuery(teilenummer=self.teilenummer, t_index=self.t_index):
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

        # Vorbelegung EC, wenn der Artikel als geplante Änderung
        # genau einem bereits genehmigten oder sich in arbeit befindlichen
        # EC zugeordnet ist.
        refs = self._getPCIReferences()
        if len(refs) == 1:
            ctx.set("index_ec_id", refs[0].cdb_ec_id)
            ctx.set_readonly("index_ec_id")

    def ECMIndexPre(self, ctx):
        if ctx.dialog:
            index_ec_id = getattr(ctx.dialog, "index_ec_id", "")
            self.CheckECReference("", index_ec_id)
        self._checkIndexAllowed()

        # Wenn wir im Kontext eines ECs Versionieren soll der neue Index nicht
        # in zu ändernde Artikel landen
        if ctx.relationship_name == "cdbecm_ec2pitems":
            ctx.skip_relationship_assignment()
        if not ctx.interactive and not ctx.uses_webui:
            refs = self._getPCIReferences()
            if len(refs) == 0:
                ctx.keep("temp_index_ec_id", getattr(ctx.dialog, "index_ec_id", ""))
            elif len(refs) == 1:
                ctx.keep("temp_index_ec_id", refs[0].cdb_ec_id)
            else:
                ctx.keep("temp_index_ec_id", "")

    def ECMIndexPost(self, ctx):
        if ctx.error:
            return
        # Set t_ec_id for new index
        # note: self.t_ec_id = ... has no effect, because
        #       ctx.set(...) does not modify the object on server side.
        # (ctx.set is only supported to set dialog values for index actions)
        item = Item.ByKeys(self.teilenummer, self.t_index)

        ec_id = ""
        if ctx.interactive or ctx.uses_webui:
            ec_id = ctx.dialog.index_ec_id
        else:
            ec_id = ctx.ue_args["temp_index_ec_id"]

        if item.cdb_t_ec_id != ec_id:
            item.cdb_t_ec_id = ec_id
            self.cdb_t_ec_id = ec_id

        # Artikeländerungsmitteilung erzeugen
        ItemECN.Create(teilenummer=self.teilenummer, t_index=self.t_index)
        EngineeringChange.ApplyDefaultsFromEC(self.ChangeNotice)

        # Add item to the running workflows
        ec = EngineeringChange.ByKeys(cdb_ec_id=item.cdb_t_ec_id)
        if ec:
            ec.addToRunningWorkflows(BRIEFCASE_NAMES, item)

    def ECMDeletePost(self, ctx):
        if self.ChangeNotice:
            # The cdb.objects-Framework does not delete texts
            for field_name in self.ChangeNotice.GetTextFieldNames():
                self.ChangeNotice.DeleteText(field_name)
            self.ChangeNotice.Delete()

    def ECMCopyPreMask(self, ctx):
        self.cdb_t_ec_id = ""


if hasattr(Item, "cdb_t_ec_id"):
    Item.EngineeringChange = Reference_1(EngineeringChange, Item.cdb_t_ec_id)
    Item.__ec_ref_modifiable_rule__ = "cdbecm: EC Reference modifiable"

    # register user exits for ec handling
    # each user exit calls an instance method of Document,
    # customers can override these instance methods in subclasses of Document
    # e.g. instead of overriding ecm_state_change_pre, customers
    # should override Item.ECMStateChangePre

    @sig.connect(Item, "state_change", "pre")
    def ecm_state_change_pre(item, ctx):
        item.ECMStateChangePre(ctx)

    @sig.connect(Item, "modify", "pre_mask")
    def ecm_modify_pre_mask(item, ctx):
        item.ECMModifyPreMask(ctx)

    @sig.connect(Item, "wf_step", "pre_mask")
    def ecm_wf_step_pre_mask(item, ctx):
        item.ECMWFStepPreMask(ctx)

    @sig.connect(Item, "modify", "pre")
    def ecm_modify_pre(item, ctx):
        item.ECMModifyPre(ctx)

    @sig.connect(Item, "delete", "post")
    def ecm_delete_post(item, ctx):
        item.ECMDeletePost(ctx)

    @sig.connect(Item, "index", "pre")
    def ecm_index_pre(item, ctx):
        item.ECMIndexPre(ctx)

    @sig.connect(Item, "index", "post")
    def ecm_index_post(item, ctx):
        item.ECMIndexPost(ctx)

    @sig.connect(Item, "index", "pre_mask")
    def ecm_index_pre_mask(item, ctx):
        item.ECMIndexPreMask(ctx)

    @sig.connect(Item, "copy", "pre_mask")
    def ecm_copy_pre_mask(item, ctx):
        item.ECMCopyPreMask(ctx)


@classbody
class EngineeringChange(object):

    Items = Reference_N(Item, Item.cdb_t_ec_id == EngineeringChange.cdb_ec_id)
    PlannedChangesItemReferences = Reference_N(PlannedChangeItemReference,
                                               PlannedChangeItemReference.cdb_ec_id == EngineeringChange.cdb_ec_id)

    def _PlannedChangesItems(self):
        return [ref.Item for ref in self.PlannedChangesItemReferences]

    PlannedChangesItems = ReferenceMethods_N(Item, _PlannedChangesItems)


for briefcase_name in BRIEFCASE_NAMES:
    EngineeringChange.registerManagedProcessBriefcase(briefcase_name, EngineeringChange.Items)

for briefcase_name in PLANNED_BRIEFCASE_NAMES:
    EngineeringChange.registerManagedProcessBriefcase(briefcase_name, EngineeringChange.PlannedChangesItems)
