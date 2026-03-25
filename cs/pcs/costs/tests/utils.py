# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import sqlapi
from cdb.validationkit.op import operation as interactive_operation
from cs.currency import Currency
from cs.pcs.costs.sheets import CostPosition, CostSheet, CostSheetFolder
from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task


def create_project():
    user_input = {"project_name": f"TEST PROJECT"}
    preset = {
        "category": "Entwicklung",
        "currency_object_id": Currency.getDefaultCurrency().cdb_object_id,
    }
    return interactive_operation("CDB_Create", Project, user_input, preset)


def create_task(cdb_project_id):
    user_input = {"task_name": f"TEST TASK"}
    preset = {
        "cdb_project_id": cdb_project_id,
        "subject_id": "caddok",
        "subject_type": "Person",
    }
    return interactive_operation("CDB_Create", Task, user_input, preset)


def delete_project(p):
    interactive_operation("CDB_Delete", p)


def create_costsheet(project_id, significance):
    rs = sqlapi.RecordSet2("cdbpcs_cost_significance", f"name_de = '{significance}'")
    cs = None
    if len(rs):
        cs = rs[0]
    user_input = {}
    preset = {
        "cdb_project_id": project_id,
        "costsignificance_object_id": cs.cdb_object_id,
    }
    return interactive_operation("CDB_Create", CostSheet, user_input, preset)


def create_costposition(type, **user_input):
    rs = sqlapi.RecordSet2("cdbpcs_cost_type", f"code = '{type}'")
    cs = None
    if len(rs):
        cs = rs[0]
    user_input["costtype_object_id"] = cs.cdb_object_id
    costsheet_object_id = user_input["costsheet_object_id"]
    del user_input["costsheet_object_id"]
    preset = {"costsheet_object_id": costsheet_object_id}
    return interactive_operation("CDB_Create", CostPosition, user_input, preset)


def create_folder(costsheet_object_id, parent_id="", name="Test"):
    user_input = {"name_de": name, "parent_object_id": parent_id}
    preset = {"costsheet_object_id": costsheet_object_id}
    return interactive_operation("CDB_Create", CostSheetFolder, user_input, preset)


def create_structure(
    project_id, depth=3, positions=2, significance="Budget", type="Sachkosten"
):
    cost_sheet = create_costsheet(project_id, significance)
    level = 1
    parent = ""
    while depth != level:
        folder = create_folder(
            cost_sheet.cdb_object_id, parent_id=parent, name=f"Test {level}"
        )
        parent = folder.cdb_object_id
        pos_count = 1
        while positions != pos_count:
            create_costposition(
                cost_sheet.cdb_object_id, type, f"Test {level}/{pos_count}"
            )

            pos_count += 1
        level += 1
