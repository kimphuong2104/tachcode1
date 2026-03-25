# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

from cdb.fls import get_license
from cdb.objects import Rule
from cdb import sig
from cdb.classbody import classbody

from cs.documents import Document
from cs.vp.items import Item

from cs.threed.hoops import _MODEL_RULE

_rule = None

PREVIEW_LICENSE = "3DSC_014"

# Add a random, but fixed __pageid__ parameter in order tp prevent cs.web
# from generating a new one and throwing away the anchor with the cdb_object_id
PREVIEW_URL = "/cs-threed-hoops-web-preview?__pageid__=0sf7qbu6#%s"


def _get_rule():
    global _rule
    if _rule is None:
        _rule = Rule.ByKeys(_MODEL_RULE)
    return _rule


@sig.connect(Document, "preview", "now")
@sig.connect(Item, "preview", "now")
def _threed_preview(self, ctx):
    self.threed_preview(ctx)


def _show_threed_preview(obj, ctx):
    if get_license(PREVIEW_LICENSE) and _get_rule().match(obj):
        ctx.setPreviewURL(PREVIEW_URL % obj.cdb_object_id)
    else:
        obj.on_preview_now(ctx)


@classbody
class Document(object):
    def threed_preview(self, ctx):
        _show_threed_preview(self, ctx)


@classbody
class Item(object):
    def threed_preview(self, ctx):
        model = self.get_3d_model_document()
        if model:
            _show_threed_preview(model, ctx)
        else:
            self.on_preview_now(ctx)
