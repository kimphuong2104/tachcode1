# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id: __init__.py 186586 2018-11-12 07:58:38Z tst $"

import os
from cdb import rte
from cdb import sig
from cs.platform.web import static


__all__ = []


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    base_path = os.path.dirname(__file__)
    lib = static.Library("cs-font", "15.0", base_path)
    lib.add_file("font.css")
    static.Registry().add(lib)
