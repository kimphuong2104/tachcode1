# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

"""
The sole purpose of the cs-vp-bom-web-operations library is to make the frontend function
handleCopyAndReplaceBomItem() available in arbitrary (global) contexts.

See handleCopyAndReplaceBomItem for details.
"""

import os

from cdb import rte
from cdb import sig

from cs.platform.web import static

from cs.web.components.base.main import GLOBAL_CUSTOMIZATION_HOOK

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

LIB_NAME = "cs-vp-bom-web-operations"
LIB_VERSION = "15.10.0"


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(LIB_NAME, LIB_VERSION,
                         os.path.join(os.path.dirname(__file__), 'js', 'build'))
    lib.add_file(LIB_NAME + ".js")
    lib.add_file(LIB_NAME + ".js.map")
    static.Registry().add(lib)


@sig.connect(GLOBAL_CUSTOMIZATION_HOOK)
def _add_lib(request):
    # We need to load lib globally because we don't know in advance in which context
    # handleCopyAndReplaceBomItem() is needed (relship table, xBOM manager, product structure, ...).
    request.app.include(LIB_NAME, LIB_VERSION)
