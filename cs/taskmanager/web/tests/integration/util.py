#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from cs.taskmanager.userdata import ReadStatus, Tags

TEST_TASK_CUSTOM_OID = "bf529417-9ee6-11ec-93ed-334b6053520d"


def create_read_status(persno, task_oid=TEST_TASK_CUSTOM_OID, **kwargs):
    values = {
        "persno": persno,
        "task_object_id": task_oid,
        "read_status": 1,
    }
    if kwargs:
        values.update(**kwargs)
    return ReadStatus.Create(**values)


def create_task_tag(persno, task_oid=TEST_TASK_CUSTOM_OID, **kwargs):
    values = {
        "persno": persno,
        "task_object_id": task_oid,
        "tag": "foo_tag",
    }
    if kwargs:
        values.update(**kwargs)
    return Tags.Create(**values)
