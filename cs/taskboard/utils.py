#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import datetime
from cdb import util
from cdb import ue
from cdb import sqlapi
from cdb.platform import olc
from cdb.objects import Forward

fBoard = Forward("cs.taskboard.objects.Board")

OBJECTS_CHANGING = set()
OBJECTS_CHANGED = set()
BOARD_UPDATE_ACTIVATED = True
SPLIT_COUNT = 999


def auto_change_card_task_status(board_adapter, cards, from_status_list, to_status):
    errors = {}
    for card in cards:
        task_wrapper = board_adapter.get_card_task(card)
        if task_wrapper.status not in from_status_list:
            continue
        task = card.TaskObject
        try:
            task.ChangeState(to_status)
        except Exception:
            pass
        if task.status != to_status:
            task_wrapper.Reload()
            task_title = task_wrapper.GetClassDef().getTitle()
            status_title_from = task_wrapper.ToObjectHandle().getStateLabel()
            status_title_to = olc.StateDefinition.ByKeys(to_status,
                                                         task.cdb_objektart).StateText['']
            fset = frozenset([task_title, status_title_from, status_title_to])
            errors[fset] = errors[fset] + 1 if fset in errors else 1
    error_msg = []
    for key, value in errors.items():
        key = list(key)
        error_msg.append(
            util.get_label("taskboard_state_unchanged") % (key[0], value, key[1], key[2]))
    if error_msg:
        error_msg.append(util.get_label("taskboard_state_unchanged_end"))
        raise ue.Exception(1024, "\n".join(error_msg))


def get_board_object_ids_by_task_object_ids(task_object_ids):
    """
    This method uses the passed object ids to determine
    which taskboards contain cards for these objects

    :param task_object_ids: set of object ids
    :return: set of board object ids
    """
    if not task_object_ids:
        return set()
    result = set()
    for task_oids in partition(list(task_object_ids), SPLIT_COUNT):
        object_ids = ','.join(["'%s'" % sqlapi.quote(i)
                               for i in task_oids])
        for r in sqlapi.RecordSet2(
            table="cs_taskboard_card",
            condition="context_object_id IN ({})".format(object_ids),
            columns=["board_object_id"]
        ):
            result.add(r.board_object_id)
    return result


def add_to_change_stack(obj, ctx=None):
    # if context is called directly by user always reset stack
    # because it must to be the first one to stack
    # (and the last to remove)
    if ctx and (hasattr(ctx, "batch") and not ctx.batch or
                hasattr(ctx, "interactive") and ctx.interactive):
        clear_update_stack()

    # add object to stack of changed objects
    oid = obj.cdb_object_id
    OBJECTS_CHANGING.add(oid)

    # add project board of the object to the boards, that have
    # been effected by changes
    # board has to be refreshed after all changes have been applied
    OBJECTS_CHANGED.add(oid)


def remove_from_change_stack(obj, ctx=None):
    # remove object from stack of changed objects
    if obj.cdb_object_id in OBJECTS_CHANGING:
        OBJECTS_CHANGING.remove(obj.cdb_object_id)

    # if stack of changed objects gets empty, all changes are made
    # now all effected boards have to be updated
    if not OBJECTS_CHANGING or ctx and not ctx.batch:
        board_object_ids = get_board_object_ids_by_task_object_ids(
            OBJECTS_CHANGED)
        boards = fBoard.KeywordQuery(cdb_object_id=board_object_ids,
                                     is_aggregation=0, is_template=0)
        for board in boards:
            board.updateBoard()
        clear_update_stack()


def clear_update_stack(*args, **kwargs):
    OBJECTS_CHANGING.clear()
    OBJECTS_CHANGED.clear()


def is_board_update_activated():
    return BOARD_UPDATE_ACTIVATED


class NoBoardUpdate(object):

    def __enter__(self):
        global BOARD_UPDATE_ACTIVATED
        BOARD_UPDATE_ACTIVATED = False

    def __exit__(self, exception_type, exception_value, traceback):
        global BOARD_UPDATE_ACTIVATED
        BOARD_UPDATE_ACTIVATED = True


def partition(list_to_partition, n):
    for i in range(0, len(list_to_partition), n):
        yield list_to_partition[i:i + n]


def ensure_date(value):
    if isinstance(value, datetime.datetime):
        return value.date()
    return value
