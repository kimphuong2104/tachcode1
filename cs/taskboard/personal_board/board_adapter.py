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


import logging
from cdb import auth
from cdb.fls import is_available
from cs.platform.org.user import UserSubstitute
from cs.taskboard.interfaces.board_adapter import BoardAdapter
from cs.taskboard.objects import Card


class PersonalBoardAdapter(BoardAdapter):

    def get_readonly_fields(self):
        return set(["interval_length", "interval_name",
                    "start_date", "auto_create_iteration"])

    def get_header_dialog_name(self):
        return "taskboard_personal_board_header"

    def adjust_new_card(self, task_object_id, **kwargs):
        # if the newly created card is not in active interval, assign it to
        # that interval
        board = self.get_board()
        for card in Card.KeywordQuery(context_object_id=task_object_id):
            if not card.Board.is_aggregation and card.Board != board:
                card.Board.getAdapter().adjust_new_card(task_object_id)
        cards = board.Cards.KeywordQuery(context_object_id=task_object_id)
        if not len(cards):
            return False
        return True

    def get_subjects(self):
        persons = [auth.persno]
        persons.extend(UserSubstitute.get_substituted_users(auth.persno, False))
        return persons, [], []

    @classmethod
    def get_filters(cls):
        if is_available("ORG_010"):
            return [{"name": "substitute_filter",
                     "label": "cs_taskboard_substitute_filter"}]
        else:
            logging.warning("Licence ORG_010 not available !")
            return []
