# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

import os

from cdb import rte
from cdb import sig

from cs.platform.web import static


__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

MAJOR = "2023"
SERVICE_PACK = "1"
UPDATE = "1"
VERSION = "%s.%s.%s" % (MAJOR, SERVICE_PACK, UPDATE)


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    def register_communicator(version):
        lib = static.Library("cs-threedlibs-communicator", version,
                            os.path.join(os.path.dirname(__file__), 'js', 'build'))
        lib.add_file("hoops_web_viewer.js")
        # Activate this when E050883 is fixed
        # lib.add_file("engine-wasm.js")
        # Activate this when E050878 is fixed
        # lib.add_file("engine.wasm")
        lib.add_file("engine-asmjs.js")
        lib.add_file("cs-threedlibs-communicator.js")
        lib.add_file("cs-threedlibs-communicator.js.map")
        static.Registry().add(lib)

    register_communicator(VERSION)
    register_communicator(MAJOR)
