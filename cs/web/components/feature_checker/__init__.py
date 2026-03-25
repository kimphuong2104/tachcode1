#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Web App to check for capabilities of the browser. When the app is shown, it
does ist checks, and POSTs the result back to the server. The POST handler will
then emit a signal with the result, and the HTTP variables coming with it.
The results take the form of a dictionary, currently of the form:
{
    'canvas': {
        'webgl': 'hardware' | 'software' | 'none',
        'webgl2': 'hardware' | 'software' | 'none'
    }
}

Customer code can connect to the signal as follows:

from cdb import sig
from cs.web.components.feature_checker import FEATURE_CHECK_RESULT

@sig.connect(FEATURE_CHECK_RESULT)
def _test(headers, features):
    pass

See example attached to E043591: Detection of WebGL capabilities of the client
for a concrete usage scenario.

"""

from __future__ import absolute_import
__revision__ = "$Id$"

import os
from webob.exc import HTTPNoContent

from cdb import misc
from cdb import rte
from cdb import sig

from cs.platform.web import PlatformApp
from cs.platform.web import static
from cs.platform.web.root import Internal


class FeatureCheckerApp(PlatformApp):
    pass


@Internal.mount(path="feature-checker", app=FeatureCheckerApp)
def _mount():
    return FeatureCheckerApp()


@FeatureCheckerApp.path(path="")
class FeatureCheckerModel(object):
    pass


_LIBNAME = "cs-web-components-feature-checker"
_LIBVERSION = "1.0.0"
_TEMPLATE_FNAME = os.path.join(os.path.dirname(__file__),
                               "resources", "feature_checker.html")


@FeatureCheckerApp.html(model=FeatureCheckerModel)
def _html(model, request):
    with open(_TEMPLATE_FNAME, "rb") as f:
        template = f.read()
    lib = static.Registry().get(_LIBNAME, _LIBVERSION)
    return template.format(script=lib.render(),
                           result_link=request.link(model))


# Marker object for signal
FEATURE_CHECK_RESULT = object()


@FeatureCheckerApp.json(model=FeatureCheckerModel, request_method="POST")
def _post(_model, request):
    headers = {k: request.headers[k]
               for k in list(request.headers)}
    sig.emit(FEATURE_CHECK_RESULT)(headers, request.json)
    return HTTPNoContent()


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(_LIBNAME, _LIBVERSION,
                         os.path.join(os.path.dirname(__file__), "resources"))
    lib.add_file('%s.js' % _LIBNAME)
    static.Registry().add(lib)
