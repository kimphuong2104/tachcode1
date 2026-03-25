#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Module __init__
This is the documentation for the __init__ module.
"""

import os

from cdb import rte
from cdb import sig

from cs.platform.web import static

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    components_path = os.path.join(os.path.dirname(__file__), "components")

    base_path = os.path.dirname(__file__)
    jquery_lib = static.Library("jquery", "2.1.0", os.path.join(base_path, "../resources/jquery/v2_1_0/dist"))
    jquery_lib.add_file("jquery.min.js", "jquery.js")
    jquery_lib.add_file("jquery.min.map", )
    static.Registry().add(jquery_lib)

    def add_lib(name, cdir, version):
        lib = static.Library(
            name, version,
            os.path.join(components_path, cdir, "build")
        )
        lib.add_file("%s.js" % name)
        lib.add_file("%s.js.map" % name)
        static.Registry().add(lib)

    add_lib("cs-vp-tree-component", "tree", "15.5.0")
    add_lib("cs-vp-rest-tree-component", "rest-tree", "15.5.0")
    add_lib("cs-vp-list-component", "list", "15.5.0")
    add_lib("cs-vp-table-component", "table", "15.5.0")
    add_lib("cs-vp-utils", "utils", "15.5.0")

    wizard = static.Library(
        "cs-vp-variants-apps-instance_wizard", "15.5.0",
        os.path.join(os.path.dirname(__file__), "instance_wizard", "webapp", "build")
    )
    wizard.add_file("bundle.js")
    wizard.add_file("bundle.js.map")
    static.Registry().add(wizard)

    matrix = static.Library(
        "cs-vp-variant-matrix", "15.5.0",
        os.path.join(os.path.dirname(__file__), "variant_matrix", "webapp", "build")
    )
    matrix.add_file("bundle.js")
    matrix.add_file("bundle.js.map")
    static.Registry().add(matrix)
