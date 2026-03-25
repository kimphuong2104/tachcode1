#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from itertools import groupby
from operator import itemgetter

from cdb import sqlapi
from cdb.objects import Rule

from cs.pcs.checklists import Checklist, ChecklistItem


def query_checklists(cdb_project_id, task_id, checklist_id):
    query = [f"cdb_project_id = '{cdb_project_id}'"]

    if task_id:
        query.append(f"task_id = '{task_id}'")
    if checklist_id is not None:
        query.append(f"checklist_id = '{checklist_id}'")

    rset = Checklist.Query(
        " AND ".join(query), addtl="ORDER BY cdb_cdate", access="read"
    )
    return rset


def query_items(cdb_project_id, checklists):
    if not checklists:
        return []

    checklist_ids = ", ".join([str(checklist) for checklist in checklists])

    query = [
        f"cdb_project_id = '{cdb_project_id}'",
        f"checklist_id IN ({checklist_ids})",
    ]
    rset = ChecklistItem.Query(
        " AND ".join(query),
        addtl="ORDER BY position",
        access="read",
    )
    return rset


def group_by_item(sorted_list, item):
    key = itemgetter(item)
    result = {
        group: list(group_values) for group, group_values in groupby(sorted_list, key)
    }
    return result


def query_rules(cdb_project_id, checklists):
    if not checklists:
        return {}

    checklist_ids = ", ".join([str(checklist) for checklist in checklists])

    query = [
        f"cdb_project_id = '{cdb_project_id}'",
        f"checklist_id IN ({checklist_ids})",
    ]
    rule_refs = sqlapi.RecordSet2(
        "cdbpcs_deliv2rule", " AND ".join(query), addtl="ORDER BY rule_id"
    )
    rules_condition = "', '".join([x["rule_id"] for x in rule_refs])
    rules = Rule.Query(
        f"name IN ('{rules_condition}')",
        access="read",
    )
    return {
        "rules": rules,
        "refs": group_by_item(rule_refs, "rule_id"),
    }
