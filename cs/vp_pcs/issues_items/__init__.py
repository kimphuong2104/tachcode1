#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from cdb import auth, sig, ue
from cdb.classbody import classbody
from cdb.objects import Forward, Object, Reference_1, Reference_Methods, Reference_N
from cs.pcs.issues import Issue
from cs.vp.items import Item

fIssuePartReference = Forward(__name__ + ".IssuePartReference")


class IssuePartReference(Object):
    __maps_to__ = "cdbpcs_part2iss"
    __classname__ = "cdbpcs_part2iss"

    Item = Reference_1(
        Item, fIssuePartReference.teilenummer, fIssuePartReference.t_index
    )


@classbody
class Issue(object):
    def _getItems(self):
        return self.SimpleJoinQuery(Item, IssuePartReference)

    Items = Reference_Methods(Item, _getItems)
    PartReferences = Reference_N(
        IssuePartReference,
        IssuePartReference.cdb_project_id == Issue.cdb_project_id,
        IssuePartReference.issue_id == Issue.issue_id,
    )

    @sig.connect(Issue, "create", "pre_mask")
    @sig.connect(Issue, "copy", "pre_mask")
    def setDefaultsByItem(self, ctx):
        self.division = auth.get_department()
        # ggf. Projektnummer aus Beziehungskontext uebernehmen
        if ctx.relationship_name == "cdbpcs_part2issues":
            self.cdb_project_id = Item.ByKeys(
                ctx.parent.teilenummer, ctx.parent.t_index
            ).cdb_t_project_id


@classbody
class Item(object):
    def _getIssues(self):
        return self.SimpleJoinQuery(Issue, IssuePartReference)

    Issues = Reference_Methods(Issue, _getIssues)

    @sig.connect(Item, "delete", "pre")
    def check_issues(self, ctx):
        if len(self.Issues) > 0:  # pylint: disable=C1801
            raise ue.Exception("pcs_err_del_part2")
