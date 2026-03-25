#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

__revision__ = "$Id$"

import os

from cdb import sig
from cdb import rte

from cs.platform.web import static


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    weblib = static.Library("cs-requirements-web-weblib", "0.0.1",
                            os.path.join(os.path.dirname(__file__), "weblib", "build"))
    weblib.add_file('cs-requirements-web-weblib.js')
    weblib.add_file('cs-requirements-web-weblib.js.map')
    static.Registry().add(weblib)

    richtext = static.Library("cs-requirements-web-richtext", "0.0.1",
                              os.path.join(os.path.dirname(__file__), "richtext", "build"))
    richtext.add_file('cs-requirements-web-richtext.js')
    richtext.add_file('cs-requirements-web-richtext.js.map')
    static.Registry().add(richtext)
