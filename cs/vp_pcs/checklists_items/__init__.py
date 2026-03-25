#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import sig, ue
from cdb.classbody import classbody
from cdb.objects import Forward, Object, Reference_1, ReferenceMethods_N
from cs.pcs.checklists import Checklist
from cs.vp.items import Item

fItemReference = Forward(__name__ + ".PartReference")


class PartReference(Object):
    __maps_to__ = "cdbpcs_part2cl"
    __classname__ = "cdbpcs_part2cl"

    Item = Reference_1(Item, fItemReference.teilenummer, fItemReference.t_index)


@classbody
class Item(object):
    def _getChecklists(self):
        return self.SimpleJoinQuery(Checklist, PartReference)

    Checklists = ReferenceMethods_N(Checklist, _getChecklists)

    def create_relationship_object(self, cdb_project_id, checklist_id):
        PartReference.Create(
            teilenummer=self.teilenummer,
            t_index=self.t_index,
            cdb_project_id=cdb_project_id,
            checklist_id=checklist_id,
        )

    @sig.connect(Item, "cdbpcs_checklist_assign", "now")
    def _assign_item_checklist(self, ctx):
        (cdb_project_id, checklist_id) = Checklist.cdbpcs_checklist_assign(self, ctx)
        self.create_relationship_object(cdb_project_id, checklist_id)

    @sig.connect(Item, "delete", "pre")
    def check_checklists(self, ctx):
        if len(self.Checklists) > 0:  # pylint: disable=C1801
            raise ue.Exception("pcs_err_del_part1")


@classbody
class Checklist(object):
    def _get_Items(self):
        return self.SimpleJoinQuery(Item, PartReference)

    Items = ReferenceMethods_N(Item, _get_Items)
    Items.isCollection = 1

    def _preset_project_from_item(self, ctx):
        self.cdb_project_id = Item.ByKeys(
            ctx.parent.teilenummer, ctx.parent.t_index
        ).cdb_t_project_id
