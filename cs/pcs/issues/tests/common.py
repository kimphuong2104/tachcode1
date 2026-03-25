#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import datetime

from cdb.objects.operations import operation

from cs.pcs import issues


def generate_issue(project, issue_id, **user_input):
    kwargs = {
        "cdb_project_id": project.cdb_project_id,
        "issue_id": f"{issue_id}",
        "issue_name": f"Test Issue {issue_id}",
        "reported_by": "Administrator",
        "reported_at": datetime.date.today(),
        "subject_id": "caddok",
        "subject_type": "Person",
        "category": "offen",
        "priority": "offen",
    }
    kwargs.update(**user_input)
    return operation("CDB_Create", issues.Issue, **kwargs)
