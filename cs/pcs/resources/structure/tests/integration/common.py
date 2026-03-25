#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import util
from cdb.objects import Object, org
from cdb.objects.operations import operation
from cdb.objects.org import Organization, Person
from cdb.validationkit.SwitchRoles import run_with_project_roles
from cs.calendar import CalendarProfile
from cs.pcs.projects import Project, ProjectCategory
from cs.pcs.projects.tasks import Task
from cs.pcs.resources import RessourceAssignment, RessourceDemand
from cs.pcs.resources.pools import ResourcePool
from cs.pcs.resources.pools.assignments.person import ResourcePoolAssignmentPerson
from cs.platform.org.user import AbsencePeriod


def generate_baseline_of_project(prj, **user_input):
    kwargs = {"ce_baseline_name": "", "ce_baseline_comment": ""}
    kwargs.update(**user_input)

    @run_with_project_roles(prj, ["Projektleiter"])
    def _create_baseline(prj, **kwargs):
        return operation("ce_baseline_create", prj, **kwargs)

    return _create_baseline(prj, **kwargs)


# OrganizationType can be replaced by cdb.org.OrganizationCategory
# if cs.resources does not support CE platform til 15.3 anymore
class OrganizationType(Object):
    __classname__ = "cdb_org_type"
    __maps_to__ = "cdb_org_type"


def getObligatoryForPerson(username):
    """
    Creates all fields needed to create a user with the given username and
    returns them as a dictionary.
    """
    caddok = org.User.ByKeys(personalnummer="caddok")
    orgname = calendar_profile_id = None
    if caddok is not None:
        orgname = caddok.orgname
        calendar_profile_id = caddok.calendar_profile_id
    else:
        # fallback to some organisation and the id of the standard calendar profile
        organization = Organization.Query()[0]
        orgname = organization.name
        calendar_profile_id = "1cb4cf41-0f40-11df-a6f9-9435b380e702"

    return {
        "personalnummer": username,
        "lastname": username,
        "orgname": orgname,
        "calendar_profile_id": calendar_profile_id,
        "abt_nummer": "IT",
    }


def get_resource_properties_for_person(**kwargs):
    """
    Creates all fields needed to make a person with the given username to a resource and
    returns them as a dictionary.
    """
    calendar_profile = CalendarProfile.Query()[0]
    resource_properties = {
        "is_resource": True,
        "capacity": 8,
        "calendar_profile_id": calendar_profile.cdb_object_id,
    }
    resource_properties.update(**kwargs)
    return resource_properties


def create(cls, preset, user_input):
    kwargs = dict(preset)
    kwargs.update(user_input)
    return operation("CDB_Create", cls, **kwargs)


def generateProject(presets_custom=None, user_input_custom=None):
    presets_custom = presets_custom or {}
    user_input_custom = user_input_custom or {}
    project_category = ProjectCategory.Query()[0]
    preset = {
        "cdb_project_id": "Ptest.integration",
        "ce_baseline_id": "",
        "category": project_category.name,
    }
    preset.update(presets_custom)
    user_input = {"project_name": "project name", "template": 0}
    user_input.update(user_input_custom)
    proj = create(Project, preset, user_input)
    generate_baseline_of_project(proj)
    return proj


def generateProjectTask(project, presets_custom=None, user_input_custom=None):
    presets_custom = presets_custom or {}
    user_input_custom = user_input_custom or {}
    preset = {
        "cdb_project_id": project.cdb_project_id,
        "ce_baseline_id": project.ce_baseline_id,
        "mapped_subject_name": "Projektmitglied",
        "subject_id": "Projektmitglied",
        "subject_type": "PCS Role",
        "constraint_type": "0",
    }
    preset.update(presets_custom)
    user_input = {
        "task_name": "Task",
        "effort_fcast": 10.0,
        "effort_plan": 10.0,
        "start_time_fcast": "03.11.2021",
        "end_time_fcast": "03.11.2021",
        "days_fcast": 1,
    }
    user_input.update(user_input_custom)
    project.Reload()
    return create(Task, preset, user_input)


def generate_organization(presets_custom=None, user_input_custom=None):
    presets_custom = presets_custom or {}
    user_input_custom = user_input_custom or {}
    organization_type = OrganizationType.Query()[0]
    preset = {
        "org_id": "cs.res.0",
        "org_type_name": "*** mandatory stuff ***",
        "org_type": organization_type.shorttext,
    }
    preset.update(presets_custom)
    user_input = {
        "name": "organization name",
        "is_resource": True,
        "is_resource_browsable": True,
    }
    user_input.update(user_input_custom)
    return create(org.Organization, preset, user_input)


def generate_person(presets_custom=None, user_input_custom=None):
    presets_custom = presets_custom or {}
    user_input_custom = user_input_custom or {}
    calendar_profile = CalendarProfile.Query()[0]
    organization = Organization.Query()[0]
    preset = {
        "personalnummer": "*** mandatory stuff ***",
        "org_id": organization.org_id,
    }
    preset.update(presets_custom)
    personalnummer = str(util.nextval("cs.resource.person"))
    user_input = {
        "personalnummer": personalnummer,
        "lastname": "last name {}".format(personalnummer),
        "calendar_profile_id": calendar_profile.cdb_object_id,
        "abt_nummer": "IT",
    }
    user_input.update(user_input_custom)
    return create(org.Person, preset, user_input)


def generate_absence(person, period_start, period_end):
    user_input = {
        "personalnummer": person.personalnummer,
        "period_start": period_start,
        "period_end": period_end,
    }
    return create(AbsencePeriod, {}, user_input)


def generate_resource_pool(presets_custom=None, user_input_custom=None):
    presets_custom = presets_custom or {}
    user_input_custom = user_input_custom or {}
    preset = dict(presets_custom)
    user_input = {"name": "resource pool name", "bookable": True}
    user_input.update(user_input_custom)
    return create(ResourcePool, preset, user_input)


def generate_resource_pool_assignment_person(
    resource_pool, person, presets_custom=None, user_input_custom=None
):
    presets_custom = presets_custom or {}
    user_input_custom = user_input_custom or {}
    resource_oid = (
        person.Resource.cdb_object_id if getattr(person, "Resource", None) else ""
    )
    preset = {
        "person_id": person.personalnummer,
        "mapped_person": "*** mandatory stuff ***",
        "pool_oid": resource_pool.cdb_object_id,
        "resource_oid": resource_oid,
        "capacity": person.capacity,
    }
    if "start_date" not in user_input_custom:
        preset["start_date"] = (
            person.Resource.CalendarProfile.valid_from
            if getattr(person, "Resource", None)
            else ""
        )
    preset.update(presets_custom)
    user_input = dict(user_input_custom)
    return create(ResourcePoolAssignmentPerson, preset, user_input)


def generate_resource_demand(
    project,
    task,
    resource_pool=None,
    resource_pool_assignment=None,
    presets_custom=None,
    user_input_custom=None,
):
    presets_custom = presets_custom or {}
    user_input_custom = user_input_custom or {}
    pool_oid = (
        resource_pool.cdb_object_id
        if resource_pool
        else resource_pool_assignment.pool_oid
        if resource_pool_assignment
        else ""
    )
    preset = {
        "cdb_project_id": project.cdb_project_id,
        "task_id": task.task_id,
        "pool_oid": pool_oid,
        "assignment_oid": resource_pool_assignment.cdb_object_id
        if resource_pool_assignment
        else "",
        "resource_oid": resource_pool_assignment.resource_oid
        if resource_pool_assignment
        else "",
        "hours": 10.0,
        "hours_per_day": 10.0,
    }
    preset.update(presets_custom)
    user_input = {
        "project_name": project.project_name,
        "task_name": task.task_name,
        "hours": 10.0,
        "hours_per_day": 10.0,
    }
    user_input.update(user_input_custom)
    return create(RessourceDemand, preset, user_input)


def generate_resource_assignment(
    project,
    task,
    resource_demand,
    resource_pool=None,
    resource_pool_assignment=None,
    presets_custom=None,
    user_input_custom=None,
):
    presets_custom = presets_custom or {}
    user_input_custom = user_input_custom or {}
    pool_oid = (
        resource_pool.cdb_object_id
        if resource_pool
        else resource_pool_assignment.pool_oid
        if resource_pool_assignment
        else ""
    )
    preset = {
        "cdb_project_id": project.cdb_project_id,
        "task_id": task.task_id,
        "cdb_demand_id": resource_demand.cdb_demand_id,
        "pool_oid": pool_oid,
        "assignment_oid": resource_pool_assignment.cdb_object_id
        if resource_pool_assignment
        else "",
        "resource_oid": resource_pool_assignment.resource_oid
        if resource_pool_assignment
        else "",
    }
    preset.update(presets_custom)
    user_input = {
        "project_name": project.project_name,
        "task_name": task.task_name,
        "hours": 10.0,
        "hours_per_day": 10.0,
    }
    user_input.update(user_input_custom)
    return create(RessourceAssignment, preset, user_input)


def create_person(person_id, **kwargs):
    """
    Creating a person using cdb.objects.Object.Create
    """
    args = {"visibility_flag": True, "name": person_id}
    args.update(getObligatoryForPerson(person_id))
    args.update(Person.MakeChangeControlAttributes())
    args.update(get_resource_properties_for_person())
    args.update(**kwargs)
    return Person.Create(**args)


def create_resource_pool(**kwargs):
    """
    Creating a resource pool using cdb.objects.Object.Create
    """
    args = ResourcePool.MakeChangeControlAttributes()
    args.update(**kwargs)
    return ResourcePool.Create(**args)


def create_resource_pool_person_assignment(**kwargs):
    """
    Creating a resource pool person assignment using cdb.objects.Object.Create
    """
    args = ResourcePoolAssignmentPerson.MakeChangeControlAttributes()
    args.update(**kwargs)
    return ResourcePoolAssignmentPerson.Create(**args)
