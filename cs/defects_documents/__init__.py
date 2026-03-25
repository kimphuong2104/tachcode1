#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#

from cdb import sig
from cdb.objects import ByID
from cs.documents import Document  # @UnresolvedImport
from cs.defects import Defect


@sig.connect(Document, "index", "pre")
def defects_index_pre(doc, ctx):
    if ctx.relationship_name == "cdb_defect2docs":
        defect = ByID(ctx.parent.cdb_object_id)
        if not defect.CheckAccess('save'):
            ctx.skip_relationship_assignment()
