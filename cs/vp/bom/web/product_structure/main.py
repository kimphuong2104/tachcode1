# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id: main.py 142800 2016-06-17 12:53:51Z js $"

import os

from cdb import rte
from cdb import sig
from cs.platform.web import static

from cs.vp.bom.web.product_structure import VERSION


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        "cs-vp-bom-web-product_structure",
        VERSION,
        os.path.join(os.path.dirname(__file__), "js", "build"),
    )
    lib.add_file("cs-vp-bom-web-product_structure.js")
    lib.add_file("cs-vp-bom-web-product_structure.js.map")
    static.Registry().add(lib)
