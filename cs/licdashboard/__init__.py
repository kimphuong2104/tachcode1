#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import

import os

from cdb import rte, sig
from cs.platform.web import static


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        "cs-licdashboard",
        "15.3.0",
        os.path.join(os.path.dirname(__file__), "js", "build"),
    )
    lib.add_file("cs-licdashboard.js")
    lib.add_file("cs-licdashboard.js.map")
    static.Registry().add(lib)
