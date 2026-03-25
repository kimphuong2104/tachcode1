#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from __future__ import absolute_import
__revision__ = "$Id$"

import os
from cdb import rte
from cdb import sig
from cs.platform.web import static

__all__ = []


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("immutable", "3.8.1",
                         os.path.join(os.path.dirname(__file__), "dist"))
    lib.add_file("immutable.min.js", "immutable.js")
    static.Registry().add(lib)
