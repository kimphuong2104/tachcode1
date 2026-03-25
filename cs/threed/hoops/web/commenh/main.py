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


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-threed-commenh", "2019.0.0",
                         os.path.join(os.path.dirname(__file__), 'js'))
    lib.add_file("index.js")
    static.Registry().add(lib)
