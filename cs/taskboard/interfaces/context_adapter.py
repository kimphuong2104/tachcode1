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


class ContextAdapter(object):
    """
    Defines the behavior of the board depending on the context object.
    You should use a context adapter always as a class.
    """

    @classmethod
    def get_header_dialog_name(cls, board):
        """
        Returns the name of a configured dialog.
        Usually, information of the Context Object is displayed in the header area of the Task Board.
        Content of the header area are configured by a dialog.

        :param board: current task board
        :type board: cs.taskboard.objects.Board
        :return: name of a dialog or empty string if dialog is not used
        :rtype: basestring or empty string
        """
        return ""
