#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

"""
Morepath app for the dashboard page
"""

__revision__ = "$Id$"

import os
import json
import morepath

from urllib.parse import unquote
from cdb import rte
from cdb import sig
from cs.platform.web import static
from cs.platform.web import PlatformApp
from cs.platform.web.root import Root
from cs.platform.web.uisupport import get_webui_link
from cs.web.components.ui_support.user_settings import SettingsModel
from cs.taskboard.internal import InternalTaskboardApp
from cs.taskboard.internal import MyTaskBoards
from cs.taskboard.internal import TaskLongTextModel
from cs.taskboard.constants import SETTING_ID
from cs.taskboard.objects import Board


def taskboard_app_setup(model, request, app_setup):
    # Setup to access the taskboard
    internal_app = InternalTaskboardApp.get_app(request)
    taskboard = model.get_object()

    app_setup.merge_in(["cs-taskboard"], {
        "dataURL": unquote(
            request.class_link(
                Board, {"cdb_object_id": "${cdb_object_id}"}, app=internal_app)),
        "headerURL": request.link(taskboard, "+header", app=internal_app),
        "boardSettings": json.loads(
            SettingsModel(SETTING_ID, taskboard.cdb_object_id).get_setting()),
        "detailOutlets": taskboard.get_detail_outlets(),
        "boardId": taskboard.cdb_object_id,
        "taskLongTextURL": unquote(
            request.class_link(
                TaskLongTextModel,
                {
                    "cdb_object_id": "${cdb_object_id}",
                    "text_name": "${text_name}"
                },
                app=internal_app))
    })


def my_task_boards_setup(model, request, app_setup):
    # Setup to access my task boards
    internal_app = InternalTaskboardApp.get_app(request)
    app_setup.merge_in(["cs-taskboard"], {
        "myTaskBoardsDataURL": unquote(
            request.link(MyTaskBoards(), app=internal_app))
    })


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-taskboard", "15.1.0",
                         os.path.join(os.path.dirname(__file__), "js", "build"))
    lib.add_file("cs-taskboard.js")
    lib.add_file("cs-taskboard.js.map")
    static.Registry().add(lib)


class PersonalBoardApp(PlatformApp):
    """
    To allow visiting Personal Board via a special fixed URL.
    Personal Board for each user has different ID, use this fixed URL
    to share the common entry.
    """
    pass


@Root.mount(app=PersonalBoardApp, path="cs-taskboard/personal_board")
def mount_personal_board():
    return PersonalBoardApp()


@PersonalBoardApp.path(path="")
class PersonalBoardAppModel(object):
        pass


@PersonalBoardApp.html(model=PersonalBoardAppModel)
def personal_board_page(self, request):
    return morepath.redirect(
        get_webui_link(request, Board.get_personal_board()))
