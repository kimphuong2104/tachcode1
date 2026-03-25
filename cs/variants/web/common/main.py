# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

import os

from cdb import rte, sig
from cs.platform.web import static
from cs.variants.web.common import COMPONENT_NAME, VERSION


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        COMPONENT_NAME, VERSION, os.path.join(os.path.dirname(__file__), "js", "build")
    )
    lib.add_file("cs-variants-web-common.js")
    lib.add_file("cs-variants-web-common.js.map")
    static.Registry().add(lib)
