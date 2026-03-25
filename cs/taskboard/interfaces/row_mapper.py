#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Common interface of |cs.taskboard|
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class RowMapper(object):
    """
    A row mapper defines some behaviours of a card in a row.
    You should use a row mapper always as a class.
    """

    @classmethod
    def validate(cls, board_adapter, card_adapter, card, task):
        """
        Check whether the card is in the correct row.

        :param board_adapter: the current board adapter
        :param card_adapter: the current card adapter class
        :param card: the checking card object
        :type card: cs.taskboard.objects.Card
        :param task: the referenced task of the card
        :type task: cs.taskboard.interfaces.task_object_wrapper.TaskObjectWrapper
        :rtype:  bool
        """
        return True

    @classmethod
    def init_row(cls, board_adapter, card_adapter, task):
        """
        Return the initial row for a new adding card on a board.
        Default is the first row of that board.

        :param board_adapter: the current board adapter
        :param card_adapter: the current card adapter class
        :param task: the referenced task of the card
        :type task: cs.taskboard.interfaces.task_object_wrapper.TaskObjectWrapper
        :return: A row object existing on that board.
        :rtype: cs.taskboard.objects.Row
        """
        board = board_adapter.get_board()
        return board.Rows[0] if len(board.Rows) else None

    # @classmethod
    # def can_change(cls, card_adapter, row):
    #     """
    #     Check whether the card can be change to the specified row.
    #     """
    #     pass
    #
    @classmethod
    def auto_change(cls, board_adapter, card_adapter, card, task):
        """
        Automatically move card to a corresponding row if necessary.
        Return whether the card is in the proper row thereafter.

        :param board_adapter: the current board adapter
        :param card_adapter: the current card adapter class
        :param card: the checking card object
        :type card: cs.taskboard.objects.Card
        :param task: the referenced task of the card
        :type task: cs.taskboard.interfaces.task_object_wrapper.TaskObjectWrapper
        :rtype: bool
        """
        return True

    @classmethod
    def change_to(cls, board_adapter, card_adapter, card, row):
        """
        Move given card into specified row.

        :param board_adapter: the current board adapter
        :param card_adapter: the current card adapter class
        :param card: the checking card object
        :type card: cs.taskboard.objects.Card
        :param row: the target row
        :type row: cs.taskboard.objects.Row
        """
        pass
