#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from cdb import util
from cdb.objects.org import CommonRoleSubject, User

from cs.pcs.checklists import Checklist, ChecklistItem, RuleReference
from cs.pcs.projects import Project, SubjectAssignment
from cs.pcs.projects.tests.common import generate_baseline_of_project

STANDARD_PROFILE = "1cb4cf41-0f40-11df-a6f9-9435b380e702"


# functions for setting up test data
def create_project(cdb_project_id, ce_baseline_id, *members, **kwargs):
    project = Project.Create(
        cdb_project_id=cdb_project_id,
        ce_baseline_id=ce_baseline_id,
        calendar_profile_id=STANDARD_PROFILE,
        **kwargs,
    )
    generate_baseline_of_project(project)
    for member in members:
        project.assignTeamMember(member)
    return project


def create_checklist(project, **kwargs):
    values = {
        "cdb_project_id": project.cdb_project_id,
        "checklist_id": "111111",
        "rating_scheme": "RedGreenYellow",
        "type": "Checklist",
        "cdb_objektart": "cdbpcs_checklist",
        "auto": 1,
        "rating_id": "clear",
        "status": Checklist.NEW.status,
    }
    if kwargs:
        values.update(**kwargs)
    return Checklist.Create(**values)


def create_checklist_item(person, project, checklist, **kwargs):
    values = {
        "cdb_project_id": project.cdb_project_id,
        "cl_item_id": "111111",
        "checklist_id": checklist.checklist_id,
        "crtierion": f"Checklist Item of {checklist.checklist_id}",
        "subject_id": person.personalnummer,
        "subject_type": "Person",
        "cdb_objektart": "cdbpcs_cl_item",
        "rating_id": "clear",
        "rating_scheme": "RedGreenYellow",
        "type": "Checklist",
        "status": ChecklistItem.NEW.status,
    }
    if kwargs:
        values.update(**kwargs)
    return ChecklistItem.Create(**values)


def create_rule_reference(project, checklist, rule_id, **kwargs):
    values = {
        "cdb_project_id": project.cdb_project_id,
        "checklist_id": checklist.checklist_id,
        "rule_id": rule_id,
    }
    if kwargs:
        values.update(**kwargs)
    return RuleReference.Create(**values)


def create_user(persno):
    # needs login, personalnummer
    user = User.Create(personalnummer=persno, login=persno, id=persno)
    return user


def get_user(persno):
    return User.ByKeys(personalnummer=persno)


def assign_user_role_public(user):
    # assign the global/common role "public" to user
    assign_global_role(user, "public")


def assign_user_role_administrator(user):
    # assign the global/common role "Administrator" to user
    assign_global_role(user, "Administrator")


def assign_global_role(user, role_id):
    # assign the global/common role to user
    CommonRoleSubject.Create(
        role_id=role_id,
        subject_id=user.personalnummer,
        subject_type="Person",
        cdb_classname="cdb_global_subject",
    )
    # clear cache, which elsewise would give back the
    # old state without the new data entry
    util.reload_cache(util.kCGRoleCaches, util.kLocalReload)


def assign_user_project_role(user, project, role_id):
    # assign project role "Projektmitglied" to the user
    SubjectAssignment.Create(
        role_id=role_id,
        subject_id2="",
        subject_id=user.personalnummer,
        subject_type="Person",
        cdb_project_id=project.cdb_project_id,
        cdb_classname="cdbpcs_subject_per",
    )
    # clear cache to allow role assignment
    util.reload_cache(util.kCGRoleCaches, util.kLocalReload)
