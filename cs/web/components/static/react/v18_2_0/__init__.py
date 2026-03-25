#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
"""

from __future__ import absolute_import
__revision__ = "$Id$"

import os
from cdb import rte
from cdb import sig
from cs.platform.web import static


__all__ = []


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("react", "15.6.1", os.path.dirname(__file__))
    lib.add_file("react-with-addons.min.js", "react-with-addons.js")
    lib.add_file("react-dom.min.js", "react-dom.js")
    static.Registry().add(lib)
