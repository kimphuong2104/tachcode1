#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


import pathlib

from cdb import rte, sig
from cs.platform.web import static

LIB = "cs-tasks-documents-plugin"
VERSION = "15.6.0"


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    build_dir = pathlib.Path(__file__, "..", "js", "build").resolve()
    lib = static.Library(LIB, VERSION, str(build_dir))
    lib.add_file("{}.js".format(LIB))
    lib.add_file("{}.js.map".format(LIB))
    static.Registry().add(lib)

    # include lib when opening taskmanager,
    # so custom briefcase dropzone is available for workflow details
    from cs.taskmanager.web.main import TasksApp

    original_setup = TasksApp.update_app_setup

    def add_cs_tasks_library(app, app_setup, model, request):
        original_setup(app, app_setup, model, request)
        # inject relship name to use for briefcase operation toolbars
        app_setup.merge_in(
            ["cs-tasks-workflow-plugin"],
            {"BriefcaseRelshipName": "Documents"},
        )
        # include frontend library to customize briefcase content dropzones
        request.app.include(LIB, VERSION)

    TasksApp.update_app_setup = add_cs_tasks_library
