# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com
#
# Version:  $Id$

import os

from cdb import rte
from cdb import sig

from cs.platform.web import static


__revision__ = "$Id$"
__docformat__ = "restructuredtext en"


COMPONENT_NAME = "cs-threed-hoops-web-tree"
COMPONENT_VERSION = "15.7.0"


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(COMPONENT_NAME, COMPONENT_VERSION,
                         os.path.join(os.path.dirname(__file__), 'js', 'build'))
    lib.add_file("cs-threed-hoops-web-tree.js")
    lib.add_file("cs-threed-hoops-web-tree.js.map")
    static.Registry().add(lib)
