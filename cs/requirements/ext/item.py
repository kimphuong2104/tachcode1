#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from cdb import sig
from cdb.classbody import classbody
from cdb.objects import Forward, references
from cdb.objects import Object

from cs.requirements import fRQMSpecObject, RQMSpecObject, rqm_utils, fRQMSpecification, RQMSpecification
from cs.tools import semanticlinks
from cs.tools.semanticlinks import SemanticLink
from cs.vp.items import Item


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


fSemanticLink = Forward("cs.tools.semanticlinks.SemanticLink")


@classbody
class Item(object):

    def _SemanticLinks(self):
        return fSemanticLink.KeywordQuery(subject_object_id=self.cdb_object_id)

    SemanticLinks = references.ReferenceMethods_N(fSemanticLink, _SemanticLinks)

    def _Requirements(self):
        reqs = []
        for r2r_sl in semanticlinks.SemanticLink.KeywordQuery(subject_object_classname=self.GetClassname(),
                                                              subject_object_id=self.cdb_object_id,
                                                              object_object_classname=RQMSpecObject.__classname__):
            reqs.append(fRQMSpecObject.ByKeys(cdb_object_id=r2r_sl.object_object_id))
        return reqs

    Requirements = references.ReferenceMethods_N(fRQMSpecObject, _Requirements)

    @sig.connect(Item, "link_graph", "now")
    def showLinkGraph(self, ctx):
        ctx.url(rqm_utils.get_rqm_linkgraph_url(self.cdb_object_id))

    def copy_item_sem_links(self, ctx):
        if ctx is not None:
            if hasattr(ctx, 'cdbtemplate') and ctx.cdbtemplate:
                old_part = Item.ByKeys(ctx.cdbtemplate.teilenummer, ctx.cdbtemplate.t_index)
                sem_links = semanticlinks.SemanticLink.KeywordQuery(subject_object_id=old_part.cdb_object_id)
                for sem_link in sem_links:
                    args = {"subject_object_id": self.cdb_object_id,
                            "object_object_id": sem_link.object_object_id,
                            "link_type_object_id": sem_link.link_type_object_id,
                            "subject_object_classname": self.GetClassname(),
                            "object_object_classname": sem_link.Object.GetClassname()}
                    link = sem_link.Create(**args)
                    link.generateMirrorLink()

    @sig.connect(Item, "index", "post")
    def _rqm_items_index_post(self, ctx):
        self.copy_item_sem_links(ctx)


@classbody
class RQMSpecObject(object):
    Parts = references.ReferenceMethods_N(Item, lambda self: self._Parts())

    def _Parts(self):
        parts = []
        for r2p_sl in semanticlinks.SemanticLink.KeywordQuery(subject_object_classname=self.GetClassname(),
                                                              subject_object_id=self.cdb_object_id,
                                                              object_object_classname=Item.__classname__):
            parts.append(Item.KeywordQuery(cdb_object_id=r2p_sl.to_object_id)[0])
        return parts


@classbody
class RQMSpecification(object):
    MAXBOMs = references.ReferenceMethods_N(Item, lambda self: self._MaxBomItems())

    def _MaxBomItems(self):
        if self.Product:
            return self.Product.MaxBoms
        else:
            return []
