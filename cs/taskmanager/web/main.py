#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
cs.taskmanager web app backend
"""

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

import pathlib

from cdb import fls, rte, sig, util
from cs.platform.web import static
from cs.platform.web.root import Root
from cs.web.components.base.main import BaseApp, BaseModel

APPNAME = "cs-tasks"
APPVERSION = "15.5.0"
MOUNTEDPATH = "/tasks"


class TasksApp(BaseApp):
    client_favicon = "cs_tasks"

    def update_app_setup(self, app_setup, model, request):
        super(TasksApp, self).update_app_setup(app_setup, model, request)
        app_setup["appSettings"].update(
            {
                "useSubstitutes": fls.is_available("ORG_010"),
            }
        )
        self.include(APPNAME, APPVERSION)


@Root.mount(app=TasksApp, path=MOUNTEDPATH)
def _mount_tasks_app(request):
    return TasksApp()


class TasksModel(BaseModel):
    page_name = "cs-tasks"


@TasksApp.path(path="", model=TasksModel)
def _get_tasks_model():
    return TasksModel()


@TasksApp.view(model=TasksModel, name="document_title", internal=True)
@TasksApp.view(model=TasksModel, name="application_title", internal=True)
def _tasks_app_title(self, request):
    return util.get_label("cs_task_manager_title")


@TasksApp.view(model=TasksModel, name="app_component")
def _tasks_app_component(model, request):
    return "cs-tasks-App"


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def register():
    build_dir = pathlib.Path(__file__, "..", "js", "build").resolve()
    lib = static.Library(APPNAME, APPVERSION, str(build_dir))
    lib.add_file("{}.js".format(APPNAME))
    lib.add_file("{}.js.map".format(APPNAME))

    static.Registry().add(lib)
