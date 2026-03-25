# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
"""
Common column mapper of |cs.taskboard|
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class ColumnMapper(object):
    """
    The Column Mapper maps the behavior of a card on the Task Board to the master data of the
    business object that the card represents.
    """

    @classmethod
    def validate(cls, board_adapter, card_adapter, card, task):
        """
        Check whether the card's data is out of date.

        :param board_adapter: the current board adapter
        :type board_adapter: cs.taskboard.interfaces.board_adapter.BoardAdapter
        :param card_adapter: the current card adapter
        :type card_adapter: cs.taskboard.interfaces.card_adapter.CardAdapter
        :param card: the card to be validated
        :type card: cs.taskboard.objects.Card
        :param task: the task represented by the card
        :type task: cs.taskboard.interfaces.task_object_wrapper.TaskObjectWrapper
        :rtype:  bool
        """
        return True

    @classmethod
    def init_column(cls, board_adapter, card_adapter, task):
        """
        Returns the column of the board on which the card of the given task
        is to be displayed, immediately after the task has been newly created.

        :param board_adapter: the current board adapter
        :type board_adapter: cs.taskboard.interfaces.board_adapter.BoardAdapter
        :param card_adapter: the current card adapter
        :type card_adapter: cs.taskboard.interfaces.card_adapter.CardAdapter
        :param task: the task represented by the card
        :type task: cs.taskboard.interfaces.task_object_wrapper.TaskObjectWrapper
        :return: the column of the board on which the card of the given task
                 is to be displayed (Default: first column of the board)
        :rtype: cs.taskboard.objects.Column
        """
        board = board_adapter.get_board()
        return board.Columns[0] if len(board.Columns) else None

    @classmethod
    def auto_change(cls, board_adapter, card_adapter, card, task):
        """
        Called for each card when the board is being updated.

        Checks the properties and position of the card on the board.

        If necessary, the properties and position of the card will be updated.

        :param board_adapter: the current board adapter
        :type board_adapter: cs.taskboard.interfaces.board_adapter.BoardAdapter
        :param card_adapter: the current card adapter
        :type card_adapter: cs.taskboard.interfaces.card_adapter.CardAdapter
        :param card: the current card
        :type card: cs.taskboard.objects.Card
        :param task: the task represented by the card
        :type task: cs.taskboard.interfaces.task_object_wrapper.TaskObjectWrapper
        :return: True, if the card is valid

                 False,  if something is wrong with the card
        :rtype: bool
        """
        return True

    @classmethod
    def change_to(cls, board_adapter, card_adapter, card, column):
        """
        Is called for a card when it is moved on the board by the user.

        Checks the properties and position of the card on the board.

        If necessary, the properties and position of the card will be updated.

        :param board_adapter: the current board adapter
        :type board_adapter: cs.taskboard.interfaces.board_adapter.BoardAdapter
        :param card_adapter: the current card adapter
        :type card_adapter: cs.taskboard.interfaces.card_adapter.CardAdapter
        :param card: the card to be moved
        :type card: cs.taskboard.objects.Card
        :param column: the target column
        :type column: cs.taskboard.objects.Column
        :return: Nothing
        """
        pass
