#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cs.pcs.resources.resourceschedule import CombinedResourceSchedule, ResourceSchedule


class ResourceScheduleOIDsModel:
    def __init__(self, resource_schedule_oid):
        self.resource_schedule_oid = resource_schedule_oid
        self.resource_schedule = ResourceSchedule.ByKeys(cdb_object_id=resource_schedule_oid)

    def get_resource_schedule_oids(self, request):

        time_schedule_oid = None
        project_oid = self.resource_schedule.cdb_project_id
        if self.resource_schedule.cdb_project_id:
            combined_schedule = CombinedResourceSchedule.ByKeys(resource_schedule_oid=self.resource_schedule_oid)
            time_schedule_oid = combined_schedule.time_schedule_oid

        return {
            "resource_schedule_oid": self.resource_schedule_oid,
            "time_schedule_oid": time_schedule_oid,
            "project_oid": project_oid
        }
