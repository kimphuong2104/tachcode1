#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

"""
Registration of JavaScript libs for PDF viewer
"""

from __future__ import absolute_import
__revision__ = "$Id$"

import os

from cdb import rte
from cdb import sig
from cs.platform.web import static
from cs.web.components import configurable_ui


def setup_worker_url(_model, _request, settings):
    """ The JavaScript code needs the path where the dynamically loaded code can
        be found. This function must be called for every page that uses the PDF
        viewer.
    """
    liburl = static.Registry().get("cs-web-components-pdf-lib", "15.1.0").url()
    settings["cs-web-components-pdf"] = {
        "lib-src": "%s/pdf.min.js" % liburl,
        "worker-src": "%s/pdf.worker.min.js" % liburl
    }


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    pth = os.path.join(os.path.dirname(__file__), "js", "build")
    lib = static.Library("cs-web-components-pdf", "15.1.0", pth)
    lib.add_file("cs-web-components-pdf.js")
    lib.add_file("cs-web-components-pdf.js.map")
    static.Registry().add(lib)

    # Register dynamically loaded stuff as a separate lib, so that they can be
    # loaded, but will not load on startup.
    lib = static.Library("cs-web-components-pdf-lib", "15.1.0", pth)
    lib.add_file("pdf.min.js")
    lib.add_file("pdf.worker.min.js")
    static.Registry().add(lib)
