# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

import os
from cdb import rte
from cdb import sig
from cs.platform.web import static
from cs.platform.web.root import Root
from cs.web.components.base.main import BaseApp
from cs.web.components.base.main import BaseModel

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

MOUNTEDPATH = "/cs-workflow-forms"
PLUGIN = "cs-workflow-forms"
VERSION = "15.2.0"
FILE = __file__
BUILD_DIR = os.path.join(os.path.dirname(FILE), 'js', 'build')
REGISTER_LIBRARY = sig.signal()


class AbsorbModel(BaseModel):
    def __init__(self, absorb):
        super(AbsorbModel, self).__init__()
        self.absorb = absorb


class FormsApp(BaseApp):
    """
    Web application to render workflow forms.

    If you want to use custom components in forms,
    you have to register their respective libraries like this:

    .. code-block :: python

        from cs.workflow.webforms.main import REGISTER_LIBRARY
        from cdb import sig

        @sig.connect(REGISTER_LIBRARY)
        def register_webforms_library():
            return ("cs-activitystream-web", "15.1.0")

    """
    pass


@Root.mount(app=FormsApp, path=MOUNTEDPATH)
def _mount_app():
    return FormsApp()


@FormsApp.path(path="", model=AbsorbModel, absorb=True)
def _get_model(absorb):
    return AbsorbModel(absorb)


@FormsApp.view(model=AbsorbModel, name="document_title", internal=True)
def default_document_title(self, request):
    return "Forms"


@FormsApp.view(model=AbsorbModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include(PLUGIN, VERSION)

    for library, version in sig.emit(REGISTER_LIBRARY)():
        request.app.include(library, version)

    return "{}-App".format(PLUGIN)


@FormsApp.view(model=AbsorbModel, name="base_path", internal=True)
def get_base_path(model, request):
    if not model.absorb:
        return request.path
    else:
        return request.path[:-(len(model.absorb) + 1)]


@FormsApp.view(model=AbsorbModel, name="application_title", internal=True)
def get_application_title(self, request):
    return "Forms"


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(PLUGIN, VERSION, BUILD_DIR)
    lib.add_file("{}.js".format(PLUGIN))
    lib.add_file("{}.js.map".format(PLUGIN))
    static.Registry().add(lib)
