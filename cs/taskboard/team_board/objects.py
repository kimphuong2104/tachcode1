#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


import datetime
import logging
from cdb import sig
from cdb.constants import kOperationModify
from cdb.constants import kOperationNew
from cdb.constants import kOperationDelete
from cdb.util import SkipAccessCheck
from cdb.objects import Object
from cdb.objects.operations import operation
from cs.taskboard.objects import Board
from cs.taskboard.team_board import TEAM_BOARD_TYPE


@sig.connect(Object, "cs_taskboard_create_team_board", "pre_mask")
def on_create_team_board_pre_mask(self, ctx):
    # for now the team interval team board is the default
    templates = Board.KeywordQuery(board_type=TEAM_BOARD_TYPE,
                                   is_template=True,
                                   available=True)
    if len(templates) < 1:
        return
    template = templates[0]
    try:
        contents = template.getBoardContentTypesAndNames()
    except ValueError as err:
        logging.error("Error while setting default board template: %s", err)
        return
    ctx.set("content_types", contents["content_types"])
    ctx.set("content_types_names", contents["content_types_names"])
    ctx.set("template_object_id", template.cdb_object_id)
    ctx.set("description", template.description)
    ctx.set("auto_create_iteration", template.auto_create_iteration)

    fields = ["interval_length", "interval_name",
              "start_date", "auto_create_iteration"]
    ctx.set_fields_writeable(fields)
    ctx.set_fields_mandatory(fields)

    if template.TimeUnit:
        ctx.set("interval_length", template.interval_length)
        ctx.set("interval_type", template.interval_type)
        ctx.set("interval_name", template.interval_name)


@sig.connect(Board, "copyBoard")
@sig.connect(Board, "create", "post")
@sig.connect(Board, "copy", "post")
def init_interval(self, ctx=None):
    if self.board_type == TEAM_BOARD_TYPE and not self.is_template:
        board_adjust_intervals(self)

@sig.connect(Board, "copy", "pre_mask")
def mark_start_date_mandatory(self, ctx):
    if self.board_type == TEAM_BOARD_TYPE:
        ctx.set_mandatory("start_date")

def board_adjust_intervals(board, adapter=None):
    if board.board_type != TEAM_BOARD_TYPE:
        return
    if adapter is None:
        adapter = board.getAdapter()
    iter_cls = adapter.get_iteration_class()
    if not iter_cls:
        return

    iterations = board.Iterations
    today = datetime.date.today()
    start_date = board.start_date
    if start_date < today:
        # find active iteration
        current = next(
            (i for i in iterations
             if i.start_date <= today <= i.end_date), None)
        if not current:
            # no active iteration found, try to determine the date for it
            should_be = board._calc_next_timeframe(start_date)
            # repeat to find the active iteration date range
            while should_be.get("end_date") and should_be.get("end_date") < today:
                should_be = board._calc_next_timeframe(
                    should_be["end_date"] + datetime.timedelta(days=1))
            if should_be.get("start_date"):
                start_date = should_be.get("start_date")
        else:
            start_date = current.start_date

    curr_len = len(iterations)
    # How many iterations are required
    # auto_create_iteration: number of future iteration
    # +1 = active iteration
    should_len = (board.auto_create_iteration or 0) + 1
    if curr_len > should_len:
        # delete spare iterations
        for iteration in iterations[should_len:]:
            iteration.deleteIteration()

    if start_date != board.start_date:
        # start date should be changed, iterations would be
        # adjusted automatically, s. Board#adjust_interval
        board = Board.ByKeys(board.cdb_object_id)
        board.modifyBoard(start_date=start_date)
        iterations = board.Iterations

    curr_len = len(iterations)
    if curr_len < should_len:
        # create missing iterations
        last = iterations[-1] if curr_len else None
        for _ in range(should_len - curr_len):
            with SkipAccessCheck():
                last = operation(kOperationNew,
                                 iter_cls._getClassDef(),
                                 board_object_id=board.cdb_object_id,
                                 **board._next_iteration_timeframe(last))
