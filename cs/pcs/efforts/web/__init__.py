#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id$"

import os

from cdb import rte, sig
from cs.platform.web import static
from cs.platform.web.root import Root, get_root
from cs.web.components.base.main import BaseApp, BaseModel

from cs.pcs.efforts import APP_MOUNT_PATH

APP = "cs-pcs-efforts-web"
VERSION = "15.1.0"


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        APP, VERSION, os.path.join(os.path.dirname(__file__), "js", "build")
    )
    lib.add_file(f"{APP}.js")
    lib.add_file(f"{APP}.js.map")
    static.Registry().add(lib)


class MyEffortsApp(BaseApp):
    @staticmethod
    def get_app(request):
        "Try to look up /myefforts"
        return get_root(request).child(APP_MOUNT_PATH)


@Root.mount(app=MyEffortsApp, path=APP_MOUNT_PATH)
def _mount_app():
    return MyEffortsApp()


@MyEffortsApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    from cs.pcs.projects.common import web

    request.app.include(web.APP, web.VERSION)
    request.app.include(APP, VERSION)
    return f"{APP}-MyEffortsApp"
