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


from webob.exc import HTTPForbidden
from cdb import ue
from cdb import auth
from cdb import util
from cdb import sig
from cs.platform.web.rest.generic import convert
from cs.taskboard.interfaces.board_adapter import BoardAdapter
from cs.taskboard.constants import COLUMN_DOING
from cs.taskboard.objects import Interval


class IntervalBoardAdapter(BoardAdapter):

    HAS_BACKLOG = True
    HAS_EVALUATION = True
    ITERATION_CLASS = Interval

    def get_change_position_followup(self, card, row, column):
        asprint = card.Board.ActiveIteration
        if card.Iteration and \
           card.Iteration == asprint and \
           self.get_column_type(column) == COLUMN_DOING:
            args = {
                "cdb::argument.valid_start": convert.dump_datetime(asprint.start_date),
                "cdb::argument.valid_end": convert.dump_datetime(asprint.end_date)
            }
            return dict(name="cs_taskboard_move_card",
                        arguments=args)
        return None

    def adjust_new_card(self, task_object_id, **kwargs):
        # if the newly created card is not in active interval, assign it to
        # that interval
        board = self.get_board()
        card = board.Cards.KeywordQuery(context_object_id=task_object_id)
        if len(card):
            card = card[0]
        else:
            return False
        iteration = board.ActiveIteration
        if not iteration:
            compare_iter = kwargs.get("iteration", None)
            if compare_iter and compare_iter.overlap(board.NextIteration):
                iteration = board.NextIteration
        # No active interval or card is already assigned to an interval,
        # nothing should be changed
        if not iteration or card.sprint_object_id:
            return False
        # Otherwise assign the card to active interval if possible
        if not iteration.CheckAccess("save", auth.persno):
            e = ue.Exception("cs_taskboard_no_access_modify_interval")
            raise HTTPForbidden(str(e))
        card.Update(sprint_object_id=iteration.cdb_object_id)
        return True

    def change_card_iteration_pre(self, card, iteration):
        super(IntervalBoardAdapter, self).change_card_iteration_pre(card, iteration)
        card_adapter = self.get_card_adapter(card)
        due_date = card_adapter.get_due_date(card.context_object_id)
        if iteration and due_date and \
            (iteration.end_date < due_date or due_date < iteration.start_date):
            raise ue.Exception("cs_taskboard_due_date_does_not_fit")

    def change_card_iteration(self, card, iteration_id):
        super(IntervalBoardAdapter, self).change_card_iteration(card, iteration_id)
        new_iter = self.ITERATION_CLASS.ByKeys(iteration_id)
        start = None
        end = None
        if new_iter:
            start = new_iter.start_date
            end = new_iter.end_date
        task = card.TaskObject.getPersistentObject()
        card.Board.__class__.adjust_card_to_interval(task, start, end)

    def get_working_view_title(self):
        return util.Labels()["web.cs-taskboard.active_interval"]

    def validate_iteration(self, card_adapter, card, task):
        oid = card.context_object_id if card else task.cdb_object_id
        if self.is_done(card_adapter, oid):
            if card and card.sprint_object_id:
                return True
            return False
        elif card and \
                card.sprint_object_id and \
                card.Iteration and \
                card.Iteration.is_completed():
            # Ignore: not completed task from completed iteration
            return False
        due_date = card_adapter.get_due_date(oid)
        if due_date:
            iteration = self.get_board().get_iteration_by_due_date(due_date)
            iteration_oid = getattr(iteration, "cdb_object_id", "")
            if not card or card.sprint_object_id != iteration_oid:
                return False
        return True

    def autoadjust_iteration(self, card_adapter, card, task):
        oid = card.context_object_id if card else task.cdb_object_id
        done = self.is_done(card_adapter, oid)
        due_date = card_adapter.get_completion_date(oid)
        if not due_date:
            due_date = card_adapter.get_due_date(oid)
        iteration = None
        if due_date:
            iteration = self.get_board().get_iteration_by_due_date(due_date)
        elif not done and card.Iteration and card.Iteration.is_completed():
            # move card from completed iteration to next iteration or backlog
            iteration = card.Board.NextIteration

        iteration_oid = getattr(iteration, "cdb_object_id", "")
        if card.sprint_object_id != iteration_oid:
            card.sprint_object_id = iteration_oid
        return not done or iteration
