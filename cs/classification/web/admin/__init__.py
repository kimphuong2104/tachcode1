# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
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

COMPONENT_NAME = "cs-classification-web-admin"
COMPONENT_VERSION = "15.4.0"


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        COMPONENT_NAME,
        COMPONENT_VERSION,
        os.path.join(os.path.dirname(__file__), 'js', 'build')
    )
    lib.add_file(COMPONENT_NAME + ".js")
    lib.add_file(COMPONENT_NAME + ".js.map")
    static.Registry().add(lib)
