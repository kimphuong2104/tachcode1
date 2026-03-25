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
from cdb import auth
from cdb import ue
from cdb import util
from cs.taskboard.objects import Sprint
from cs.taskboard.interfaces.board_adapter import BoardAdapter


class SprintBoardAdapter(BoardAdapter):
    HAS_BACKLOG = True
    HAS_EVALUATION = True
    ITERATION_CLASS = Sprint

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
            e = ue.Exception("cs_taskboard_no_access_modify_sprint")
            raise HTTPForbidden(str(e))
        card.Update(sprint_object_id=iteration.cdb_object_id)
        return True

    def get_working_view_title(self):
        return util.Labels()["web.cs-taskboard.active_sprint"]

    def validate_iteration(self, card_adapter, card, task):
        oid = card.context_object_id if card else task.cdb_object_id
        if self.is_done(card_adapter, oid):
            if card and card.sprint_object_id:
                return True
            return False
        elif card and \
                card.Iteration and \
                card.Iteration.is_completed():
            # Ignore: not completed task from completed iteration
            return False
        return True

    def autoadjust_iteration(self, card_adapter, card, task):
        oid = card.context_object_id if card else task.cdb_object_id
        if self.is_done(card_adapter, oid):
            if card and card.sprint_object_id:
                return True
            return False
        elif card and \
                card.Iteration and \
                card.Iteration.is_completed():
            # Task not completed:
            # move card from completed iteration to next iteration or backlog
            next_iteration = card.Iteration.Board.NextIteration
            next_oid = ""
            if next_iteration:
                next_oid = next_iteration.cdb_object_id
            if card.sprint_object_id != next_oid:
                card.sprint_object_id = next_oid
        return True
