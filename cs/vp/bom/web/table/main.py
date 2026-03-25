# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

"""
"""

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

import os

from cdb import rte
from cdb import sig

from cs.platform.web import static

from cs.vp.bom.web.table import VERSION


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-vp-bom-web-table", VERSION,
                         os.path.join(os.path.dirname(__file__), 'js', 'build'))
    lib.add_file("cs-vp-bom-web-table.js")
    lib.add_file("cs-vp-bom-web-table.js.map")
    static.Registry().add(lib)
