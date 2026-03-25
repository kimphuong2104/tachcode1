# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os
from cdb import rte
from cdb import sig
from cs.platform.web import static

__all__ = []


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("momentjs", "2.18.1", os.path.join(os.path.dirname(__file__), "min"))
    lib.add_file("moment-with-locales.min.js", "moment-with-locales.js")
    static.Registry().add(lib)
