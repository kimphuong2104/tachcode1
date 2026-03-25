#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from datetime import datetime

import mock

from cdb import testcase, util
from cdb.objects import org
from cdb.objects.operations import operation
from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task
from cs.pcs.resources import RessourceAssignment, RessourceDemand
from cs.pcs.resources.pools import ResourcePool
from cs.pcs.resources.pools.assignments.person import ResourcePoolAssignmentPerson

EMPTY = "### None ###"
PROJECT_PRESET = {
    "category": "Forschung",
    "calendar_profile_id": "1cb4cf41-0f40-11df-a6f9-9435b380e702",  # Standard
    "template": 0,
}
PROJECT_INPUT = {
    "cdb_project_id": "#",
    "ce_baseline_id": "",
    "project_name": "project name",
}
TASK_PRESET = {
    "mapped_subject_name": "Projektmitglied",
    "subject_id": "Projektmitglied",
    "subject_type": "PCS Role",
}
TASK_INPUT = {
    "task_id": "#",
    "ce_baseline_id": "",
    "task_name": "Task",
    "effort_fcast": 10.0,
    "effort_plan": 10.0,
    "start_time_fcast": "03.11.2022",
    "end_time_fcast": "03.11.2022",
    "days_fcast": 1,
    "constraint_type": "0",
}
FUTURE_TASK_INPUT = {
    "task_id": "#",
    "ce_baseline_id": "",
    "task_name": "Future Task",
    "effort_fcast": 10.0,
    "effort_plan": 10.0,
    "start_time_fcast": "01.01.2024",
    "end_time_fcast": "01.01.2024",
    "days_fcast": 1,
    "constraint_type": "0",
}
PERSON_PRESET = {
    "personalnummer": "*** mandatory stuff ***",
    "is_resource": True,
    "capacity": 8,
}
PERSON_INPUT = {
    "calendar_profile_id": "1cb4cf41-0f40-11df-a6f9-9435b380e702",  # Standard
    "abt_nummer": "IT",
}
POOL_PRESET = {}
POOL_INPUT = {"name": "resource pool name", "bookable": True}
POOL_ASSIGN_PRESET = {}
POOL_ASSIGN_INPUT = {}
DEMAND_PRESET = {}
DEMAND_INPUT = {"hours": 10.0, "hours_per_day": 10.0}
RESOURCE_PRESET = {}
RESOURCE_INPUT = {"hours": 10.0, "hours_per_day": 10.0}
ORG_PRESET = {}
ORG_INPUT = {}


def date_to_date_object(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def get_default(value, default):
    if value is None:
        return default
    if value == EMPTY:
        return None
    return value


def _create(obj_class, preset, user_input, preset_custom=None, user_input_custom=None):
    kwargs = dict(preset)

    if preset_custom:
        kwargs.update(preset_custom)

    kwargs.update(user_input)

    if user_input_custom:
        kwargs.update(user_input_custom)

    return operation("CDB_Create", obj_class, **kwargs)


class PluginIntegrationTestCase(testcase.RollbackTestCase):
    maxDiff = None
    EMPTY = EMPTY

    def setUp(self):
        super(PluginIntegrationTestCase, self).setUp()
        self.project = _create(Project, PROJECT_PRESET, PROJECT_INPUT, None)
        task_preset = dict(TASK_PRESET, cdb_project_id=self.project.cdb_project_id)
        self.task = _create(Task, task_preset, TASK_INPUT)
        self.future_task = _create(Task, task_preset, FUTURE_TASK_INPUT)
        self.person = self.new_person()
        self.pool = self.new_pool("pool_A", None)

    def new_person(self, persno=None, organization=None):
        personalnummer = persno or str(util.nextval("cs.resource.person"))
        user_input = dict(
            PERSON_INPUT,
            cdb_object_id=personalnummer,
            personalnummer=personalnummer,
            lastname=personalnummer,
            org_id=organization.org_id if organization else "131",  # CONTACT Software
        )
        return _create(org.Person, PERSON_PRESET, user_input)

    def new_organization(self, uuid, parent=None):
        return _create(
            org.Organization,
            ORG_PRESET,
            ORG_INPUT,
            {
                "cdb_object_id": uuid,
                "org_id": uuid,
                "org_id_head": parent.cdb_object_id if parent else ""
            }
        )

    def new_pool(self, uuid, parent):
        return _create(
            ResourcePool,
            POOL_PRESET,
            POOL_INPUT,
            {
                "cdb_object_id": uuid,
                "parent_oid": parent.cdb_object_id if parent else "",
            },
        )

    def assign_resource(self, uuid, pool=None, person=None, start_date=None, end_date=None):
        pool = get_default(pool, self.pool)
        person = get_default(person, self.person)
        resource = getattr(person, "Resource", None)
        resource_oid = resource.cdb_object_id if resource else ""

        preset = dict(
            POOL_ASSIGN_PRESET,
            person_id=person.personalnummer,
            pool_oid=pool.cdb_object_id,
            resource_oid=resource_oid,
            capacity=person.capacity,
        )
        user_input = dict(
            POOL_ASSIGN_INPUT,
            start_date=start_date if start_date else (resource.CalendarProfile.valid_from if resource else ""),
            end_date=end_date if end_date else (resource.CalendarProfile.valid_until if resource else ""),
        )

        return _create(
            ResourcePoolAssignmentPerson,
            preset,
            user_input,
            {"cdb_object_id": uuid},
        )

    def new_demand(self, uuid, pool=None, res=None, future=False):
        task = self.future_task if future else self.task
        pool = get_default(pool, self.pool)
        pool_oid = pool.cdb_object_id if pool else res.pool_oid if res else ""
        preset = dict(
            DEMAND_PRESET,
            cdb_project_id=self.project.cdb_project_id,
            task_id=task.task_id,
            pool_oid=pool_oid,
            assignment_oid=res.cdb_object_id if res else "",
            resource_oid=res.resource_oid if res else "",
        )
        user_input = dict(
            DEMAND_INPUT,
            project_name=self.project.project_name,
            task_name=task.task_name,
        )

        return _create(
            RessourceDemand,
            preset,
            user_input,
            {"cdb_object_id": uuid},
        )

    def new_alloc(self, uuid, demand, pool=None, res=None, future=False):
        task = self.future_task if future else self.task
        pool = get_default(pool, self.pool)
        pool_oid = pool.cdb_object_id if pool else res.pool_oid if res else ""
        preset = dict(
            RESOURCE_PRESET,
            cdb_project_id=self.project.cdb_project_id,
            task_id=task.task_id,
            cdb_demand_id=demand.cdb_demand_id,
            pool_oid=pool_oid,
            assignment_oid=res.cdb_object_id if res else "",
            resource_oid=res.resource_oid if res else "",
        )
        user_input = dict(
            RESOURCE_INPUT,
            project_name=self.project.project_name,
            task_name=task.task_name,
        )

        return _create(
            RessourceAssignment,
            preset,
            user_input,
            {"cdb_object_id": uuid},
        )

    def ResolveStructure(self, plugin_class, root, time_frame=None):
        json = {
            "extraDataProps": {
                'timeFrameStartQuarter': time_frame[0],
                'timeFrameStartYear': time_frame[1],
                'timeFrameUntilQuarter': time_frame[2],
                'timeFrameUntilYear': time_frame[3],
            },
        } if time_frame else {}
        return plugin_class.ResolveStructure(
            root.cdb_object_id, mock.Mock(json=json, params={})
        )
