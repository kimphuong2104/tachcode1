#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import datetime

from cdb.objects import org
from cdb.objects.operations import SimpleArguments, operation
from cdb.validationkit.SwitchRoles import run_with_project_roles
from cs.actions import Action
from cs.taskboard.objects import Board

from cs.pcs import issues, projects, timeschedule
from cs.pcs.projects import tasks
from cs.pcs.projects.catalogs import CatalogProjectRoles

STANDARD_PROFILE = "1cb4cf41-0f40-11df-a6f9-9435b380e702"


def check_access_rights(obj, user):
    create = obj.CheckAccess("create", user.personalnummer)
    read = obj.CheckAccess("read", user.personalnummer)
    save = obj.CheckAccess("save", user.personalnummer)
    delete = obj.CheckAccess("delete", user.personalnummer)
    return create, read, save, delete


def assign_user_to_common_role(persno, role_id):
    org.CommonRoleSubject.CreateNoResult(
        role_id=role_id,
        subject_id=persno,
        subject_type="Person",
        exception_id="",
        cdb_classname="cdb_global_subject",
    )


def generate_user(login, **kwargs):
    if not login:
        login = "test_user_1"
    kwargs.update(personalnummer=login, lastname=login, login=login)
    assign_user_to_common_role(login, "public")
    return org.User.Create(**kwargs)


def generate_project(**user_input):
    project_category = projects.ProjectCategory.Query()[0]
    kwargs = {
        "calendar_profile_id": STANDARD_PROFILE,
        "category": project_category.name,
        "cdb_project_id": "project_id",
        "ce_baseline_id": "",
        "project_name": "project name",
        "template": 0,
    }
    kwargs.update(**user_input)
    prj = operation("CDB_Create", projects.Project, **kwargs)
    generate_baseline_of_project(prj)
    return prj


def generate_baseline_of_project(prj, **user_input):
    kwargs = {"ce_baseline_name": "", "ce_baseline_comment": ""}
    kwargs.update(**user_input)

    @run_with_project_roles(prj, ["Projektleiter"])
    def _create_baseline(prj, **kwargs):
        return operation("ce_baseline_create", prj, **kwargs)

    return _create_baseline(prj, **kwargs)


def generate_task(project, task_id, **user_input):
    kwargs = {
        "cdb_project_id": project.cdb_project_id,
        "task_id": task_id,
        "ce_baseline_id": "",
        "task_name": task_id,
        "subject_id": "caddok",
        "subject_type": "Person",
        "constraint_type": "0",
        "milestone": 0,
        "is_group": 0,
        "parent_task": "",
    }
    kwargs.update(**user_input)
    return operation("CDB_Create", tasks.Task, **kwargs)


def generate_task_relation(pred, succ, **user_input):
    kwargs = {
        "cdb_project_id": succ.cdb_project_id,
        "task_id": succ.task_id,
        "cdb_project_id2": pred.cdb_project_id,
        "task_id2": pred.task_id,
        "rel_type": "EA",
        "minimal_gap": 0,
        "violation": 0,
    }
    kwargs.update(**user_input)
    return operation("CDB_Create", tasks.TaskRelation, **kwargs)


def assign_person_to_project(role_id, project, subject_id):
    kwargs = {
        "role_id": role_id,
        "cdb_project_id": project.cdb_project_id,
        "subject_id": subject_id,
        "subject_id2": "",
        "subject_type": "Person",
        "exception_id": "",
    }
    return operation("CDB_Create", projects.PersonAssignment, **kwargs)


def assign_user_project_role(user, project, role_id, **user_input):
    kwargs = {
        "role_id": role_id,
        "subject_id2": "",
        "subject_id": user.personalnummer,
        "subject_type": "Person",
        "cdb_project_id": project.cdb_project_id,
        "exception_id": "",
    }
    kwargs.update(**user_input)
    return operation("CDB_Create", projects.PCSRoleAssignment, **kwargs)


def assign_project_role_to_project_role(
    role_id, cdb_project_id, subject_id, subject_id2, **user_input
):
    kwargs = {
        "role_id": role_id,
        "subject_id2": subject_id2,
        "subject_id": subject_id,
        "subject_type": "PCS Role",
        "cdb_project_id": cdb_project_id,
        "exception_id": "",
    }
    kwargs.update(**user_input)
    return operation("CDB_Create", projects.PCSRoleAssignment, **kwargs)


def assign_user_common_role(user, role_id, **user_input):
    org.CommonRoleSubject.Create(
        role_id=role_id,
        subject_id=user.personalnummer,
        subject_type="Person",
        exception_id="",
        cdb_classname="cdb_global_subject",
    )


def generate_project_task(project, **user_input):
    kwargs = {
        "cdb_project_id": project.cdb_project_id,
        "ce_baseline_id": project.ce_baseline_id,
        "task_id": "task_id",
        "task_name": "Task#1",
        "parent_task": "",
        "subject_id": "Projektmitglied",
        "subject_type": "PCS Role",
        "constraint_type": "0",
        "automatic": 0,
    }
    kwargs.update(**user_input)
    return operation("CDB_Create", tasks.Task, **kwargs)


def generate_taskschedule(**user_input):
    kwargs = {"name": "Testplan"}
    kwargs.update(**user_input)
    return operation("CDB_Create", timeschedule.TimeSchedule, **kwargs)


def link_project_to_taskschedule(project, schedule):
    kwargs = {
        "time_schedule_oid": schedule.cdb_project_id,
        "cdb_project_id": project.cdb_project_id,
    }
    return operation("CDB_Create", timeschedule.Project2TimeSchedule, **kwargs)


def create_taskboard(context_object, board_type, **kwargs):
    template = Board.KeywordQuery(
        board_type=board_type, is_template=True, available=True
    )
    if not template:
        return None
    op_args = {"template_object_id": template[0].cdb_object_id}
    op_args.update(
        interval_type=3, interval_length=1, start_date=datetime.date(2020, 9, 1)
    )
    op_args.update(**kwargs)
    operation("cs_taskboard_create_board", context_object, SimpleArguments(**op_args))
    context_object.Taskboard.updateBoard()
    return context_object.Taskboard


def generate_project_role(project, role, **user_input):
    kwargs = {"cdb_project_id": project.cdb_project_id, "role_id": role}
    kwargs.update(**user_input)
    return operation("CDB_Create", projects.Role, **kwargs)


def generate_project_role_def(name, **user_input):
    kwargs = {"name": name, "name_ml_de": name, "obsolete": False}
    kwargs.update(**user_input)
    return operation("CDB_Create", CatalogProjectRoles, **kwargs)


def generate_common_role(role, **user_input):
    kwargs = {"role_id": role}
    kwargs.update(**user_input)
    return operation("CDB_Create", org.CommonRole, **kwargs)


def assign_common_role_to_project(role_id, subject_id, cdb_project_id, **user_input):
    kwargs = {
        "role_id": role_id,
        "cdb_project_id": cdb_project_id,
        "subject_id": subject_id,
        "subject_id2": "",
        "subject_type": "Common Role",
        "exception_id": "",
    }
    kwargs.update(**user_input)
    return operation("CDB_Create", projects.CommonRoleAssignment, **kwargs)


def assign_role_to_task(task, role, **user_input):
    kwargs = {"subject_id": role, "subject_type": "PCS Role"}
    kwargs.update(**user_input)
    return operation("CDB_Modify", task, **kwargs)


def generate_issue(cdb_project_id, task_id, issue_name, **user_input):
    kwargs = {
        "cdb_project_id": cdb_project_id,
        "task_id": task_id,
        "issue_name": issue_name,
        "subject_id": "caddok",
        "subject_type": "Person",
    }
    kwargs.update(**user_input)
    return operation("CDB_Create", issues.Issue, **kwargs)


def generate_action(context_object=None, **user_input):
    kwargs = {
        "subject_id": "caddok",
        "subject_type": "Person",
    }
    if context_object:
        context_object_keys = {}
        context_class_name = context_object.GetClassname()
        if context_class_name == "cdbpcs_project":
            context_object_keys = {
                "cdb_project_id": context_object.cdb_project_id,
            }
        elif context_class_name == "cdbpcs_task":
            context_object_keys = {
                "cdb_project_id": context_object.cdb_project_id,
                "task_id": context_object.task_id,
            }
        kwargs.update(**context_object_keys)
    kwargs.update(**user_input)
    return operation("CDB_Create", Action, **kwargs)


def generate_checklist(project, **user_input):
    from cs.pcs.checklists import Checklist

    # Note: Primary key checklist_id cannot be set programmatically
    kwargs = {
        "cdb_project_id": project.cdb_project_id,
        "checklist_name": "Test Checklist",
        "subject_id": "caddok",
        "subject_type": "Person",
        "category": "Function",
        "rating_scheme": "RedGreenYellow",
        "rating": "clear",
        "division": "IT",
    }
    kwargs.update(**user_input)
    return operation("CDB_Create", Checklist, **kwargs)


def generate_checklist_item(cl, **user_input):
    from cs.pcs.checklists import ChecklistItem

    # Note: Primary key checklist_id cannot be set programmatically
    kwargs = {
        "cdb_project_id": cl.cdb_project_id,
        "checklist_id": cl.checklist_id,
        "criterion": "Spam and Eggs",
        "category": "Function",
    }
    kwargs.update(**user_input)
    return operation("CDB_Create", ChecklistItem, **kwargs)
