#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
External libs for redux based react app development.
"""

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


import os
from cdb import rte
from cdb import sig
from cs.platform.web import static


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-web-components-externals", "15.2.0",
                         os.path.join(os.path.dirname(__file__), "js", "build"))
    lib.add_file('cs-web-components-externals.js')
    lib.add_file('cs-web-components-externals.js.map')
    static.Registry().add(lib)
