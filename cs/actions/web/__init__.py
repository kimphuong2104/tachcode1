# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

"""
Interface for web related setup of cs.actions.
"""

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

import os

from cdb import rte, sig
from cs.platform.web import static


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        "cs-actions-web",
        "15.1.0",
        os.path.join(os.path.dirname(__file__), "js", "build"),
    )
    lib.add_file("cs-actions-web.js")
    lib.add_file("cs-actions-web.js.map")
    static.Registry().add(lib)
