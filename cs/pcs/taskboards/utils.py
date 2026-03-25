#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import sqlapi
from cs.taskboard.constants import COLUMN_READY
from cs.taskboard.utils import auto_change_card_task_status

from cs.pcs.projects.common import partition
from cs.pcs.helpers import get_dbms_split_count


def on_iteration_start_post(board_adapter, iteration, card_adapter):
    # for both issues and project tasks: status 0 means "New"
    from_status = [0]
    to = card_adapter.COLUMN_MAPPER.COLUMN_TO_STATUS.get(COLUMN_READY, [])
    if not to:
        return
    to_status = to[0]
    cards = card_adapter.get_cards_for_iteration(board_adapter, iteration)
    auto_change_card_task_status(board_adapter, cards, from_status, to_status)


def get_objects(table, cdb_project_id, task_id, search_objects, ignore_objects):
    # basic statement
    # noinspection SqlDialectInspection
    sql = f"SELECT * FROM {table} WHERE cdb_project_id = '{cdb_project_id}' "

    # searching objects connected to ...
    task_id = "" if not task_id else task_id
    if task_id or search_objects:
        search_ids = []
        s_ids = [f"'{task_id}'"]
        # pylint: disable-next=consider-using-f-string
        s_ids += ["'%s'" % x["task_id"] for x in search_objects]
        for task_ids in partition(s_ids, get_dbms_split_count()):
            search_ids.append(f"task_id IN ({','.join(task_ids)})")
        if search_ids:
            sql += f" AND ({' OR '.join(search_ids)})"

    # ignoring objects connected to ...
    if ignore_objects:
        ignore_ids = []
        # pylint: disable-next=consider-using-f-string
        i_ids = ["'%s'" % x["task_id"] for x in ignore_objects]
        for task_ids in partition(i_ids, get_dbms_split_count()):
            ignore_ids.append(f"task_id NOT IN ({','.join(task_ids)})")
        if ignore_ids:
            sql += f" AND ({' AND '.join(ignore_ids)})"
    return sqlapi.RecordSet2(table=table, sql=sql)
