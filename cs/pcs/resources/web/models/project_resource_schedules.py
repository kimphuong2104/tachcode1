#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging
from collections import defaultdict

from webob.exc import HTTPBadRequest, HTTPForbidden, HTTPNotFound

from cdb import auth
from cs.pcs.projects import Project
from cs.pcs.resources.resourceschedule import CombinedResourceSchedule
from cs.pcs.timeschedule import TimeSchedule


def create_rest_obj(obj):
    return {"description": obj.GetDescription(), "cdb_object_id": obj.cdb_object_id}


class CreateResourceSchedule(object):
    def get_ts_object_id(self, request):
        if request.json:
            return request.json
        return None

    def create_resource_schedule(self, request):
        ts_object_id = self.get_ts_object_id(request)
        if not ts_object_id:
            logging.error(
                "Create Resource Schedule: No timeschedule object id provided",
            )
            raise HTTPBadRequest
        timeschedule = TimeSchedule.KeywordQuery(cdb_object_id=ts_object_id)
        resource_schedule_rest_obj = None
        if timeschedule:
            resource_schedule = timeschedule[0].create_resource_schedule()
            resource_schedule_rest_obj = create_rest_obj(resource_schedule)
        return resource_schedule_rest_obj


class ProjectResourceSchedules(object):
    def __init__(self, project_oid):
        """
        Initialize model by resolving project object.
        """
        self.project_oid = project_oid
        projects = Project.KeywordQuery(cdb_object_id=project_oid)
        if not projects:
            raise HTTPNotFound

        self.project = projects[0]
        if not self.project.CheckAccess("read", auth.persno):
            logging.error(
                "User %s doesn't have access to project %s.",
                auth.persno,
                self.project.cdb_project_id,
            )
            raise HTTPForbidden

    def get_resource_schedules(self, timeschedule_oids):
        """
        Returns resource schedules combined to a timeschedule.
        """
        resource_schedules = defaultdict(list)
        combined_resource_schedules = CombinedResourceSchedule.KeywordQuery(
            time_schedule_oid=timeschedule_oids
        )
        for combined_rs in combined_resource_schedules:
            rs = combined_rs.ResourceSchedule
            resource_schedules[combined_rs.time_schedule_oid].append(
                create_rest_obj(rs)
            )
        return resource_schedules

    def get_data(self):
        timeschedule_objects = []
        timeschedule_oids = []
        for ts in self.project.PrimaryTimeSchedule:
            timeschedule_oids.append(ts.cdb_object_id)
            timeschedule = create_rest_obj(ts)
            timeschedule_objects.append(timeschedule)

        resource_schedules = self.get_resource_schedules(timeschedule_oids)

        return {
            "timeschedules": timeschedule_objects,
            "resource_schedules": resource_schedules,
        }

    def get_project_resource_schedules(self, request):
        data = self.get_data()
        return data
