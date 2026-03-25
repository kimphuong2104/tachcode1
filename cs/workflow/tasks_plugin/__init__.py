#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import functools
import pathlib

from cdb import rte
from cdb import sig
from cdb import util
from cdb.objects.org import User

from cs.platform.web import static
from cs.taskmanager.mixin import WithTasksIntegration
from cs.workflow.briefcases import BriefcaseContentWhitelist

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

PLUGIN = "cs-tasks-workflow-plugin"
VERSION = "15.1.0"
APPDIR = pathlib.Path(__file__, "..").resolve()
BUILD_DIR = str(APPDIR / "js" / "build")


class WorkflowBaseWithCsTasks(WithTasksIntegration):
    "shared base implementation for tasks and info messages"
    __icon__ = "/resources/icons/byname/cdbwf_status?status={}"

    def getCsTasksContexts(self):
        return [self.Process, self.Project]

    def csTasksDelegate_get_default(self):
        subj_id = self.Process.started_by
        if subj_id:
            user = User.ByKeys(subj_id)
            if user:
                return (subj_id, "Person", user.name)

        return ("", "", "")

    def getCsTasksStatusData(self):
        result = super(WorkflowBaseWithCsTasks, self).getCsTasksStatusData()
        result["icon"] = self.__icon__.format(self.status)
        return result

    def getCsTasksNextStatuses(self):
        result = [
            target for target in
            super(WorkflowBaseWithCsTasks, self).getCsTasksNextStatuses()
            if target["status"] in self.__status_whitelist__
        ]
        for target in result:
            target["icon"] = self.__icon__.format(target["status"])
            target["dialog"]["zielstatus_int"] = target["status"]
        return result


def extended(func):
    "decorator for calling methods on the extension object (if present)"
    @functools.wraps(func)
    def delegate_to_extension(self, *args, **kwargs):
        extension_obj = self.getExtensionObject()
        if extension_obj:
            delegate = getattr(extension_obj, func.__name__, None)
            if delegate:
                return delegate(*args, **kwargs)
        return func(self, *args, **kwargs)
    return delegate_to_extension


class WorkflowTaskWithCsTasks(WorkflowBaseWithCsTasks):
    "implementation for tasks with extension support for public tasks API"
    @extended
    def csTasksDelegate(self, ctx):
        return super(WorkflowTaskWithCsTasks, self).csTasksDelegate(ctx)

    @extended
    def csTasksDelegate_get_default(self):
        return super(WorkflowTaskWithCsTasks, self).csTasksDelegate_get_default()

    @extended
    def csTasksDelegate_get_project_manager(self):
        return super(WorkflowTaskWithCsTasks, self).csTasksDelegate_get_project_manager()

    @extended
    def getCsTasksContexts(self):
        return super(WorkflowTaskWithCsTasks, self).getCsTasksContexts()

    @extended
    def getCsTasksNextStatuses(self):
        return super(WorkflowTaskWithCsTasks, self).getCsTasksNextStatuses()

    @extended
    def getCsTasksResponsible(self):
        return super(WorkflowTaskWithCsTasks, self).getCsTasksResponsible()

    @extended
    def getCsTasksStatusData(self):
        return super(WorkflowTaskWithCsTasks, self).getCsTasksStatusData()


class WorkflowInfoMessageWithCsTasks(WorkflowBaseWithCsTasks):
    "implementation for info messages"
    __status_cache__ = None
    __icon__ = "/resources/icons/byname/cdbwf_info_message_obj?is_active={}"

    def getCsTasksContexts(self):
        return [self.Process, self.Project]

    @classmethod
    def getStatusCache(cls):
        if not cls.__status_cache__:
            cls.__status_cache__ = {
                1: {
                    "dialog": {},
                    "label": util.get_label("cdbwf_info_message_unread"),
                    "color": "?",
                    "icon": cls.__icon__.format(1),
                },
                0: {
                    "dialog": {},
                    "label": util.get_label("cdbwf_info_message_read"),
                    "color": "#00FF00",
                    "icon": cls.__icon__.format(0),
                },
            }
        return cls.__status_cache__

    def getCsTasksStatusData(self):
        return self.getStatusCache()[self.is_active]

    def getCsTasksNextStatuses(self):
        if self.is_active:
            return [self.getStatusCache()[0]]
        return []


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(PLUGIN, VERSION, BUILD_DIR)
    lib.add_file("{}.js".format(PLUGIN))
    lib.add_file("{}.js.map".format(PLUGIN))
    static.Registry().add(lib)

    # include briefcase whitelist
    from cs.taskmanager.web.main import TasksApp
    original_setup = TasksApp.update_app_setup

    def add_cs_tasks_library(app, app_setup, model, request):
        original_setup(app, app_setup, model, request)
        whitelisted = BriefcaseContentWhitelist.Classnames()
        app_setup.merge_in(
            ["cs-tasks-workflow-plugin"],
            {"BriefcaseWhitelist": list(whitelisted)},
        )

    TasksApp.update_app_setup = add_cs_tasks_library
