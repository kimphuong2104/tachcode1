#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import

from cdb.classbody import classbody
from cdb.objects import Forward, Object, Reference_1, Reference_N, ReferenceMethods_N
from cs.actions import Action
from cs.documents import Document

fAction2Document = Forward(__name__ + ".Action2doc")


class Action2doc(Object):
    __maps_to__ = "cdb_action2doc"
    __classname__ = "cdb_action2doc"

    RelatedAction = Reference_1(
        Action, Action.cdb_object_id == fAction2Document.action_object_id
    )
    RelatedDocument = Reference_1(
        Document,
        Document.z_nummer == fAction2Document.z_nummer,
        Document.z_index == fAction2Document.z_index,
    )


@classbody
class Action(object):
    DocumentLinks = Reference_N(
        Action2doc, Action2doc.action_object_id == Action.cdb_object_id
    )

    def _getDocuments(self):
        import operator

        return reduce(
            operator.add, [[dl.RelatedDocument] for dl in self.DocumentLinks], []
        )

    Documents = ReferenceMethods_N(Document, _getDocuments)
