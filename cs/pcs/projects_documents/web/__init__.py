#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id$"

import os

from cdb import rte, sig
from cs.platform.web import static

COMPONENT = "cs-pcs-projects-documents-web"


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        COMPONENT, "15.1.0", os.path.join(os.path.dirname(__file__), "js", "build")
    )
    lib.add_file(f"{COMPONENT}.js")
    lib.add_file(f"{COMPONENT}.js.map")
    static.Registry().add(lib)
