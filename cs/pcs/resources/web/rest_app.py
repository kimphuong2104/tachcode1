#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cs.pcs.resources.web.models.project_resource_schedules import (
    CreateResourceSchedule,
    ProjectResourceSchedules,
)
from cs.pcs.resources.web.models.resource_schedule_oids import ResourceScheduleOIDsModel
from cs.platform.web import JsonAPI
from cs.platform.web.root import Internal, get_internal

MOUNTED_PATH = "/pcs-resources"


class App(JsonAPI):
    @classmethod
    def get_app(cls, request):
        return get_internal(request).child(MOUNTED_PATH)


@Internal.mount(app=App, path=MOUNTED_PATH)
def _mount_app():
    return App()


@App.path(
    path="project-resource-schedules/{project_oid}", model=ProjectResourceSchedules
)
def _get_resources_model(project_oid):
    return ProjectResourceSchedules(project_oid)


@App.json(model=ProjectResourceSchedules)
def get_project_resource_schedule(model, request):
    return model.get_project_resource_schedules(request)


@App.path(path="create-resource", model=CreateResourceSchedule)
def _get_create_resources_model():
    return CreateResourceSchedule()


@App.json(model=CreateResourceSchedule, request_method="POST")
def create_resource_schedule(model, request):
    return model.create_resource_schedule(request)


@App.path(
    path="resource-schedule-ids/{resource_schedule_oid}", model=ResourceScheduleOIDsModel
)
def _get_resource_oids_model(resource_schedule_oid):
    return ResourceScheduleOIDsModel(resource_schedule_oid)


@App.json(model=ResourceScheduleOIDsModel, request_method="POST")
def get_resource_schedule_oids(model, request):
    return model.get_resource_schedule_oids(request)
