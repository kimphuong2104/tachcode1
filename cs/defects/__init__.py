#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module Defects

This is the documentation for the Defects module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports

from cdb import sig
from cdb import util
from cdb.classbody import classbody
from cdb.objects import Object, Forward, State, ReferenceMethods_N, Reference_1
from cdb.objects import Reference_N
from cs.workflow import briefcases
from cs.actions import Action
from cs.tools import powerreports
from cs.currency import Currency
from cdb.platform.gui import CDBCatalog
from cdb.platform.gui import I18nCatalogEntry
from cs.sharing.groups import RecipientCollection
from cs.sharing.share_objects import WithSharing

fDefect2Action = Forward(__name__ + ".Defect2Action")
fDefect = Forward(__name__ + ".Defect")

__all__ = ['Defect',
           'Defect2Action']


class Defect(Object, briefcases.BriefcaseContent, powerreports.WithPowerReports, WithSharing):
    __maps_to__ = "cdb_defect"
    __classname__ = "cdb_defect"

    Subdefects = Reference_N(fDefect, fDefect.parent_object_id == fDefect.cdb_object_id)
    Parentdefect = Reference_1(fDefect, fDefect.parent_object_id)
    Currency = Reference_1(Currency, fDefect.currency_object_id)

    def _Actions(self):
        acts = []
        for ref in Defect2Action.KeywordQuery(defect_object_id=self.cdb_object_id):
            acts.append(ref.RelatedAction)
        return acts

    RelatedActions = ReferenceMethods_N(Action, _Actions)

    class EDITING(State):
        status = 0

    class EVALUATING(State):
        status = 10

        def Constraints(state, self):
            return [("MatchStateList", [self.Subdefects,
                                        [Defect.EVALUATING, Defect.DISCARDED,
                                         Defect.FINISHED, Defect.REJECTED],
                                        "cdb_defect_wf_rej_2"]),
                    ("MatchStateList", [[self.Parentdefect] if self.Parentdefect else [],
                                        [Defect.EDITING, Defect.EVALUATING, Defect.IN_WORK],
                                        "cdb_defect_wf_rej_2"]),
                    ]

    class IN_WORK(State):
        status = 20

        def Constraints(state, self):
            return [("MatchStateList", [[self.Parentdefect] if self.Parentdefect else [],
                                        [Defect.IN_WORK],
                                        "cdb_defect_wf_rej_2"]),
                    ]

    class DISCARDED(State):
        status = 100

        def FollowUpStateChanges(state, self):
            return [(Defect.DISCARDED,
                     [d for d in self.Subdefects
                      if d.status != Defect.DISCARDED.status], 0)]

    class REJECTED(State):
        status = 110

        def FollowUpStateChanges(state, self):
            return [(Defect.REJECTED,
                     [d for d in self.Subdefects
                      if d.status != Defect.DISCARDED.status and d.status != Defect.REJECTED.status], 0)]

    class FINISHED(State):
        status = 200

        def Constraints(state, self):
            return [("MatchStateList", [self.Subdefects,
                                        [Defect.FINISHED, Defect.DISCARDED, Defect.REJECTED],
                                        "cdb_defect_wf_rej_2"]),
                    ]

    def setDefectId(self, ctx):
        self.id = "%06d" % util.nextval('cdb_defect')

    def presetFromRelationship(self, ctx):
        if ctx.relationship_name == 'cdb_defect2subdefects':
            parent = Defect.ByKeys(ctx.parent.cdb_object_id)
            if parent:
                if not self.categ_id and parent.categ_id:
                    ctx.set("categ_id", parent.categ_id)
                    if not self.subcateg_id and parent.subcateg_id:
                        ctx.set("subcateg_id", parent.subcateg_id)
                if not self.cdb_project_id and parent.cdb_project_id:
                    ctx.set("cdb_project_id", parent.cdb_project_id)
                if not self.responsible and parent.responsible:
                    ctx.set("responsible", parent.responsible)
                if not self.product_object_id and parent.product_object_id:
                    ctx.set("product_object_id", parent.product_object_id)
                if not self.teilenummer and parent.teilenummer:
                    ctx.set("teilenummer", parent.teilenummer)
                    if parent.t_index:
                        ctx.set("t_index", parent.t_index)
                if parent.currency_object_id:
                    ctx.set("currency_object_id", parent.currency_object_id)

    def presetCurrency(self, ctx):
        if not self.currency_object_id:
            dft_curr = Currency.getDefaultCurrency()
            if dft_curr:
                self.currency_object_id = dft_curr.cdb_object_id

    def checkCurrency(self, ctx):
        if self.cost:
            self.presetCurrency(ctx)

    def getResponsibleSubjects(self, sharingGroup):
        "support for ObjectSharingGroup 'Responsible'"
        if not self.responsible:
            return []
        return RecipientCollection(
            subjects=[(self.responsible, "Person")]).subjects

    event_map = {
            (('create', 'copy'), 'pre'): 'setDefectId',
            (('copy', 'create'), 'pre_mask'): 'presetFromRelationship',
            (('copy', 'create', 'modify'), 'pre_mask'): 'presetCurrency',
            (('copy', 'create', 'modify'), 'pre'): 'checkCurrency',
            }


class DefectStatusProtocol(Object):
    __maps_to__ = "cdb_defect_prot"
    __classname__ = "cdb_defect_prot"


class Defect2Document(Object):
    __maps_to__ = "cdb_defect2doc"
    __classname__ = "cdb_defect2doc"


class DefectCategory(Object):
    __maps_to__ = "cdb_defect_categ"
    __classname__ = "cdb_defect_categ"


class DefectCode(Object):
    __maps_to__ = "cdb_defect_code"
    __classname__ = "cdb_defect_code"


class DefectType(Object):
    __maps_to__ = "cdb_defect_type"
    __classname__ = "cdb_defect_type"


class DefectTypeCatalog(CDBCatalog):
    """
    Implements a CDB Catalog/Browser that returns the list which will appear
    in the 'defect type' Combobox.
    """

    def __init__(self):
        CDBCatalog.__init__(self)

    def handlesI18nEnumCatalog(self):
        return True

    def getI18nEnumCatalogEntries(self):
        defects = DefectType.Query()
        result = []
        for defect in defects:
            if not defect.obsolete:
                result.append(I18nCatalogEntry(defect.name, defect.type))
        return result


class DefectPriority(Object):
    __maps_to__ = "cdb_defect_priority"
    __classname__ = "cdb_defect_priority"


class DefectPriorityCatalog(CDBCatalog):
    """
    Implements a CDB Catalog/Browser that returns the list which will appear
    in the 'defect priority' Combobox.
    """

    def __init__(self):
        CDBCatalog.__init__(self)

    def handlesI18nEnumCatalog(self):
        return True

    def getI18nEnumCatalogEntries(self):
        priorities = DefectPriority.Query()
        result = []
        for priority in priorities:
            if not priority.obsolete:
                result.append(I18nCatalogEntry(priority.priority, priority.name))
        return result


class DefectSource(Object):
    __maps_to__ = "cdb_defect_source"
    __classname__ = "cdb_defect_source"


class DefectSourceCatalog(CDBCatalog):
    """
    Implements a CDB Catalog/Browser that returns the list which will appear
    in the 'defect source' Combobox.
    """

    def __init__(self):
        CDBCatalog.__init__(self)

    def handlesI18nEnumCatalog(self):
        return True

    def getI18nEnumCatalogEntries(self):
        sources = DefectSource.Query()
        result = []
        for source in sources:
            if not source.obsolete:
                result.append(I18nCatalogEntry(source.name, source.source))
        return result


class Defect2Action(Object):
    __maps_to__ = "cdb_defect2action"
    __classname__ = "cdb_defect2action"

    RelatedAction = Reference_1(Action, Action.cdb_object_id == fDefect2Action.action_object_id)
    RelatedDefect = Reference_1(Defect, Defect.cdb_object_id == fDefect2Action.defect_object_id)


def _presetActionFromRelationship(self, ctx):
    if ctx.relationship_name == 'cdb_defect2actions':
        defect = Defect.ByKeys(ctx.parent.cdb_object_id)
        if defect:
            if defect.cdb_project_id:
                ctx.set("cdb_project_id", defect.cdb_project_id)
            if defect.teilenummer:
                ctx.set("teilenummer", defect.teilenummer)
                ctx.set("t_index", defect.t_index)
            if defect.product_object_id:
                ctx.set("product_object_id", defect.product_object_id)


sig.connect(Action, "create", "pre_mask")(_presetActionFromRelationship)
sig.connect(Action, "copy", "pre_mask")(_presetActionFromRelationship)


@classbody
class Action(object):
    DefectLinks = Reference_N(Defect2Action, Defect2Action.action_object_id == Action.cdb_object_id)

    def _getDefects(self):
        defects = []
        for defect_link in self.DefectLinks:
            defects.append(defect_link.RelatedDefect)
        return defects

    Defects = ReferenceMethods_N(Defect, _getDefects)


if __name__ == '__main__':
    pass
