#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
"""

import os

from cdb import rte
from cdb import sig
from cdb import version
from cs.documents import Document
from cs.vp.items import Item

from cs.platform.web import static

from cs.web.components.generic_ui.class_view import CLASS_VIEW_SETUP
from cs.web.components.generic_ui.detail_view import DETAIL_VIEW_SETUP


COMPONENT_NAME = "cs-vp-items-components"


def ensure_csp_header_set(request):
    try:
        from cs.threed.hoops.web.utils import add_csp_header
        request.after(add_csp_header)
    except ImportError:
        pass


@sig.connect(Item, CLASS_VIEW_SETUP)
def _item_class_view_app_setup(clsname, request, app_setup):
    ensure_csp_header_set(request)
    if COMPONENT_NAME not in app_setup:
        app_setup[COMPONENT_NAME] = {}
    app_setup[COMPONENT_NAME].update({
        "ceVersion": version.getVersionDescription()
    })


@sig.connect(Item, DETAIL_VIEW_SETUP)
def _item_detail_view_app_setup(clsname, request, app_setup):
    ensure_csp_header_set(request)


@sig.connect(Document, DETAIL_VIEW_SETUP)
def _document_detail_view_app_setup(clsname, request, app_setup):
    ensure_csp_header_set(request)


@sig.connect(Document, CLASS_VIEW_SETUP)
def _document_class_view_app_setup(clsname, request, app_setup):
    ensure_csp_header_set(request)


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(COMPONENT_NAME, "15.1.0",
                         os.path.join(os.path.dirname(__file__), "components", "build"))
    lib.add_file('cs-vp-items-components.js')
    lib.add_file('cs-vp-items-components.js.map')
    static.Registry().add(lib)
