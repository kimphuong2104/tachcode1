#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import os

from cdb import rte, sig
from cs.platform.web import static

APP = "cs-pcs-resources-web"
VERSION = "15.1.0"


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        APP, VERSION, os.path.join(os.path.dirname(__file__), "js", "build")
    )
    lib.add_file("{}.js".format(APP))
    lib.add_file("{}.js.map".format(APP))
    static.Registry().add(lib)
