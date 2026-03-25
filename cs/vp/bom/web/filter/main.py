# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id: main.py 142800 2016-06-17 12:53:51Z js $"

import os

from cdb import rte, sig

from cs.platform.web import static

from cs.vp.bom.web.filter import COMPONENT_NAME, VERSION

from cs.vp.utils import add_bom_mode


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        COMPONENT_NAME,
        VERSION,
        os.path.join(os.path.dirname(__file__), "js", "build"),
    )
    lib.add_file("{0}.js".format(COMPONENT_NAME))
    lib.add_file("{0}.js.map".format(COMPONENT_NAME))
    static.Registry().add(lib)


def setup_component_join_plugin(_model, _request, settings):
    add_bom_mode(settings)
