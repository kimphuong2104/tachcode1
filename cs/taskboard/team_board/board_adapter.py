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


from cdb import ue
from cdb import sig
from cdb import util
from cdb import sqlapi
from cs.taskboard.interfaces.board_adapter import BoardAdapter
from cs.taskboard.objects import Interval
from cs.taskboard.objects import Sprint
from cs.taskboard.objects import Card
from cs.taskboard.team_board.objects import board_adjust_intervals


class TeamBoardAdapter(BoardAdapter):

    HAS_TEAM = True
    HAS_PREVIEW = True
    ITERATION_CLASS = Interval
    __TEAM_TASK_ITERATION_CACHE__ = {}

    def get_header_dialog_name(self):
        return "taskboard_team_header"

    def adjust_new_card(self, task_object_id, **kwargs):
        # if the newly created card is not in active interval, assign it to
        # that interval
        board = self.get_board()
        iteration = board.NextIteration
        for card in Card.KeywordQuery(context_object_id=task_object_id):
            if not card.Board.is_aggregation and card.Board != board:
                card.Board.getAdapter().adjust_new_card(task_object_id,
                                                        iteration=iteration)
        cards = iteration.Cards.KeywordQuery(context_object_id=task_object_id)
        if not len(cards):
            return False
        return True

    def change_card_iteration(self, card, iteration_id):
        super(TeamBoardAdapter, self).change_card_iteration(card, iteration_id)
        new_iter = self.ITERATION_CLASS.ByKeys(iteration_id)
        if new_iter:
            card_adapter = self.get_card_adapter(card)
            card_adapter.set_due_date(card.TaskObject, new_iter.end_date, overwrite=True)
            task = card.TaskObject
            card.Board.__class__.adjust_card_to_interval(task,
                                                         new_iter.start_date,
                                                         new_iter.end_date)

    def get_active_iteration(self):
        iterations = self.get_board().OpenIterations
        if len(iterations):
            return iterations[0]
        return None

    def get_last_open_iteration(self):
        iterations = self.get_board().OpenIterations
        if len(iterations):
            return iterations[-1]
        return None

    def update_board(self):
        board = self.get_board()
        # Ensure that team members can update previews
        with util.SkipAccessCheck(board.cdb_object_id):
            board_adjust_intervals(board, self)
        super(TeamBoardAdapter, self).update_board()

    def prepare_validation(self):
        super(TeamBoardAdapter, self).prepare_validation()
        # If some tasks are assigned to iterations on other boards,
        # cache the date ranges of the iterations to allocate the
        # corresponding cards in correct iteration on this board.
        self.__TEAM_TASK_ITERATION_CACHE__.clear()

        board = self.get_board()
        start, end = board.get_total_timeframe()
        # Only consider iterations in certain time frame
        if not start or not end:
            return
        start = sqlapi.SQLdbms_date(start)
        end = sqlapi.SQLdbms_date(end)

        tasks = self.get_available_tasks(refresh=False)
        task_ids = set(tasks.keys())
        card_exp = Card.context_object_id.one_of(*task_ids)
        card_exp = card_exp.qualify_names("c", "")
        stmt = u"""
            SELECT c.context_object_id,
              s.start_date, s.end_date, s.status, s.cdb_classname
            FROM cs_taskboard_card c
            INNER JOIN cs_taskboard_iteration s
            ON c.sprint_object_id = s.cdb_object_id
            WHERE (c.is_hidden = 0 OR c.is_hidden IS NULL)
            AND s.start_date <= {end}
            AND (s.end_date >= {start} OR s.status={open_status})
            AND c.board_object_id IN (
                  SELECT b.cdb_object_id
                  FROM cs_taskboard_board b
                  WHERE (b.is_aggregation = 0 OR b.is_aggregation IS NULL)
                )
            AND {card_exp}
            """.format(
            start=start, end=end, card_exp=card_exp.to_string(), open_status=50)
        results = sqlapi.RecordSet2(sql=stmt)
        # Cache the information for validation:
        # task id <=> (start, end, status, classname) of assigned interval
        for r in results:
            self.__TEAM_TASK_ITERATION_CACHE__[r.context_object_id] = \
                (r.start_date, r.end_date, r.status, r.cdb_classname)

    def get_task_iteration_timeframe(self, task_id):
        return self.__TEAM_TASK_ITERATION_CACHE__.get(task_id, (None, None, None, None))

    def get_working_view_title(self):
        return util.Labels()["web.cs-taskboard.current_period"]

    def validate_task(self, card_adapter, card, task):
        oid = card.context_object_id if card else task.cdb_object_id
        board = self.get_board()
        _, due_date, _, iter_classname = \
            self.get_task_iteration_timeframe(oid)
        if not iter_classname:
            # tasks not belong to board
            done = self.is_done(card_adapter, oid)
            if done:
                # Erledigte Aufgaben: Alle beendeten Aufgaben,
                # deren abstrakter Status zuletzt im aktuellen
                # Betrachtungszeitraum von Bearbeitung auf Beendet gesetzt wurde
                # FIXME:
                # return False if check status protocol date overdue
                pass
            else:
                isnew = card_adapter.is_new(task)
                due_date = card_adapter.get_due_date(oid)
                if due_date:
                    should_be = board.get_iteration_by_due_date(due_date)
                    if isnew and should_be == self.get_active_iteration():
                        # Aktueller Betrachtungszeitraum:
                        # Fällige und überfällige Aufgaben:
                        # Alle Aufgaben mit Fälligkeitstermin bis Ende der lfd.
                        # Team-Iteration, die nicht im Status Neu und nicht beendet
                        # (abstrakter Status != Beendet) sind.
                        return False
                elif isnew:
                    # Aktueller Betrachtungszeitraum:
                    # Alle Aufgaben ohne Fälligkeitstermin,
                    # die nicht im Status Neu und nicht beendet
                    # (abstrakter Status != Beendet) sind.
                    return False
        return True

    def _find_suitable_iteration(self, card_adapter, card, task):
        # If the task is assigned to an relevant iteration on other boards,
        # consider end date of that iteration
        oid = card.context_object_id if card else task.cdb_object_id
        board = self.get_board()
        should_be = None
        _, due_date, iter_status, iter_classname = \
            self.get_task_iteration_timeframe(oid)
        if iter_classname == Sprint.__classname__:
            if due_date:
                # task is not assigned to an iteration of an aggregated board
                should_be = board.get_iteration_by_due_date(due_date)
                if should_be:
                    return should_be
                if iter_status == 50:
                    # overdue active sprint: task assigned to active iteration
                    return self.get_active_iteration()
                # iteration at end of time frame: task assigned to last iteration
                return self.get_last_open_iteration()

        # task is not assigned to an iteration of an aggregated board
        # or assigned to an interval
        due_date = card_adapter.get_completion_date(oid)
        if not due_date:
            due_date = card_adapter.get_due_date(oid)
        if due_date:
            # task assigned by its due date
            return board.get_iteration_by_due_date(due_date)
        # Aktueller Betrachtungszeitraum:
        # Alle Aufgaben ohne Fälligkeitstermin,
        # die nicht im Status Neu und nicht beendet
        # (abstrakter Status != Beendet) sind.
        return self.get_active_iteration()

    def validate_iteration(self, card_adapter, card, task):
        should_be = self._find_suitable_iteration(card_adapter, card, task)
        if not should_be or card and card.sprint_object_id != should_be.cdb_object_id:
            return False
        return True

    def autoadjust_iteration(self, card_adapter, card, task):
        should_be = self._find_suitable_iteration(card_adapter, card, task)
        should_be_oid = should_be.cdb_object_id if should_be else ""
        if card.sprint_object_id != should_be_oid:
            card.sprint_object_id = should_be_oid
        return True
