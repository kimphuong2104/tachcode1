#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
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
    lib = static.Library("d3", "3.5.17", os.path.dirname(__file__))
    lib.add_file("d3.min.js", "d3.js")
    static.Registry().add(lib)
