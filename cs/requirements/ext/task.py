# !/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from cdb import sig
from cdb import ue
from cdb.classbody import classbody
from cdb.objects import Forward, references

from cs.requirements import fRQMSpecObject, RQMSpecObject, rqm_utils
from cs.tools import semanticlinks
from cs.tools.semanticlinks import SemanticLink
from cs.pcs.projects.tasks import Task


fSemanticLink = Forward("cs.tools.semanticlinks.SemanticLink")
fTask = Forward("cs.pcs.projects.tasks.Task")


@classbody
class Task(object):

    def _SemanticLinks(self):
        return fSemanticLink.KeywordQuery(subject_object_id=self.cdb_object_id)

    SemanticLinks = references.ReferenceMethods_N(fSemanticLink, _SemanticLinks)
    Requirements = references.ReferenceMethods_N(fRQMSpecObject, lambda self: self._Requirements())

    def _Requirements(self):
        reqs = []
        for r2r_sl in semanticlinks.SemanticLink.KeywordQuery(subject_object_classname=self.GetClassname(),
                                                              subject_object_id=self.cdb_object_id,
                                                              object_object_classname=RQMSpecObject.__classname__):
            reqs.append(fRQMSpecObject.ByKeys(cdb_object_id=r2r_sl.object_object_id))
        return reqs

    @sig.connect(Task, "link_graph", "now")
    def showLinkGraph(self, ctx):
        ctx.url(rqm_utils.get_rqm_linkgraph_url(self.cdb_object_id))


@sig.connect(SemanticLink, "create", "pre_mask")
@sig.connect(SemanticLink, "create", "pre")
def _ensure_only_reqs_in_req_relation(self, ctx):
    if ctx and hasattr(ctx, u'relationship_name') and ctx.relationship_name and \
            ctx.relationship_name == u'cdbrqm_task2requirements':
        if not isinstance(self.Object, RQMSpecObject):
            raise ue.Exception('cdbrqm_pcs_req_only')


@classbody
class RQMSpecObject(object):
    Tasks = references.ReferenceMethods_N(fTask, lambda self: self._Tasks())

    def _Tasks(self):
        tasks = []
        for r2t_sl in semanticlinks.SemanticLink.KeywordQuery(subject_object_classname=self.GetClassname(),
                                                              subject_object_id=self.cdb_object_id,
                                                              object_object_classname=Task.__classname__):
            tasks.append(Task.ByKeys(cdb_object_id=r2t_sl.object_object_id))
        return tasks
