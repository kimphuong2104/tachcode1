#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Test Module test_taskboard templates

This is the documentation for the tests.
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest

from cdb import testcase
from cdb import util
from cdb import ElementsError
from cdb.platform.mom import entities
from cdb.constants import (kOperationNew,
                           kOperationModify,
                           kOperationCopy,
                           kOperationDelete)
from cdb.objects.operations import operation


class TestTaskBoardTemplateOperation(testcase.RollbackTestCase):
    """
    Test the Create, Modify, Copy and Delete operations for taskboard templates.
    """

    def setUp(self):
        self.cdef = entities.CDBClassDef("cs_taskboard_board")
        super(TestTaskBoardTemplateOperation, self).setUp()
        self.IntervalBoardAdapter = "cs.taskboard.interval_board.board_adapter.IntervalBoardAdapter"
        self.PersonalBoardAdapter = "cs.taskboard.personal_board.board_adapter.PersonalBoardAdapter"
        self.TeamBoardAdapter = \
            "cs.taskboard.team_board.board_adapter.TeamBoardAdapter"
        self.ContinuousBoardAdapter = \
            "cs.taskboard.continuous_board.board_adapter.ContinuousBoardAdapter"

    def tearDown(self):
        super(TestTaskBoardTemplateOperation, self).tearDown()

    def test_creation(self):
        """
        Test the creation operation of a taskboard. The creation should fail if
        the taskboard title already exists.
        """

        test_cases = [
            # Should be OK
            ("", self.PersonalBoardAdapter, "personal_board", False),
            # Should be OK
            ("title01", self.IntervalBoardAdapter, "interval_board", False),
            # Should be OK
            ("title02", self.TeamBoardAdapter, "team_board", False),
            # Should be OK
            ("title03", self.ContinuousBoardAdapter, "continuous_board", False),
            # Should fail - we have used "TestBoard" as title before, but success!
            ("title03", self.ContinuousBoardAdapter, "continuous_board", False),
            # Should be OK - test creation with undefined board_api
            ("title03", "Adapter", "continuous_board", False)
        ]
        for title, adapter, board_type, fails in test_cases:
            if fails:
                with self.assertRaises(ValueError):
                    operation(kOperationNew,
                              self.cdef,
                              is_template=1,
                              title=title,
                              board_type=board_type,
                              board_api=adapter)
            else:
                bd = operation(kOperationNew,
                               self.cdef,
                               is_template=1,
                               title=title,
                               board_type=board_type,
                               board_api=adapter)
                self.assertEqual(bd.is_template, 1)
                self.assertEqual(bd.title, title)
                self.assertEqual(bd.board_type, board_type)
                self.assertEqual(bd.board_api, adapter)

    def test_modification(self):
        """
        Test the modification operation of a taskboard. The modification should fail if
        the taskboard title already exists.
        """
        operation(kOperationNew,
                  self.cdef,
                  is_template=1,
                  title="TestBoard",
                  board_type="interval_board",
                  board_api=self.IntervalBoardAdapter)
        test_board = operation(kOperationNew,
                               self.cdef,
                               is_template=1,
                               title="TestBoardModify",
                               board_type="interval_board",
                               board_api=self.IntervalBoardAdapter)

        test_cases = [
            # Should fail - the title "TestBoard" is already used. But success.
            ("TestBoard", self.ContinuousBoardAdapter, "continuous_board", False),
            # Should be OK
            ("title01", self.ContinuousBoardAdapter, "continuous_board", False),
            # Should be OK
            ("title01", self.PersonalBoardAdapter, "personal_board", False),
            # Should be OK
            ("title02", self.IntervalBoardAdapter, "interval_board", False),
            # Should be OK
            ("title02", self.TeamBoardAdapter, "team_board", False),
            # Should be OK - test creation with undefined board_api
            ("title02", "Adapter", "continuous_board", False)
        ]
        for title, adapter, board_type, fails in test_cases:
            if fails:
                with self.assertRaises(ValueError):
                    operation(kOperationModify,
                              test_board,
                              is_template=1,
                              board_type=board_type,
                              title=title,
                              interval_length=test_board.interval_length,
                              interval_type=test_board.interval_type,
                              start_date=test_board.start_date,
                              board_api=adapter)
            else:
                bd = operation(kOperationModify,
                               test_board,
                               is_template=1,
                               board_type=board_type,
                               title=title,
                               interval_length=test_board.interval_length,
                               interval_type=test_board.interval_type,
                               start_date=test_board.start_date,
                               board_api=adapter)
                self.assertEqual(bd.is_template, 1)
                self.assertEqual(bd.title, title)
                self.assertEqual(bd.board_type, board_type)
                self.assertEqual(bd.board_api, adapter)
                self.assertEqual(bd.interval_length, test_board.interval_length)
                self.assertEqual(bd.interval_type, test_board.interval_type)
                self.assertEqual(bd.start_date, test_board.start_date)

    def test_coping(self):
        """
        Test the copying operation of a taskboard. The copying should fail if
        the taskboard title already exists.
        """

        test_board = operation(kOperationNew,
                               self.cdef,
                               is_template=1,
                               title="TestBoardCopy",
                               board_type="interval_board",
                               board_api=self.IntervalBoardAdapter)
        test_cases = [
            # Should fail - the title "TestBoardCopy" is already used. But success
            ("TestBoardCopy", self.ContinuousBoardAdapter, "continuous_board"),
            # Should be OK
            ("title01", self.ContinuousBoardAdapter, "continuous_board"),
            # Should fail - we have used the same title for the copy
            ("title01", self.PersonalBoardAdapter, "personal_board"),
            # Should be OK
            ("title03", self.IntervalBoardAdapter, "interval_board"),
            # Should be OK
            ("title04", self.TeamBoardAdapter, "team_board"),
            # Should be OK - test creation with undefined board_api
            ("title05", "Adapter", "continuous_board")
        ]
        for title, adapter, board_type in test_cases:
            bd = operation(kOperationCopy,
                            test_board,
                            is_template=1,
                            board_type=board_type,
                            title=title,
                            interval_length=test_board.interval_length,
                            interval_type=test_board.interval_type,
                            start_date=test_board.start_date,
                            board_api=adapter)
            self.assertEqual(bd.is_template, 1)
            self.assertEqual(bd.title, title)
            self.assertEqual(bd.board_type, board_type)
            self.assertEqual(bd.board_api, adapter)
            self.assertEqual(bd.interval_length, test_board.interval_length)
            # self.assertEqual(bd.interval_type, test_board.interval_type)
            self.assertEqual(bd.start_date, test_board.start_date)

    def test_delete(self):
        """
        Test the delete operation of a taskboard.
        """
        test_board = operation(kOperationNew,
                               self.cdef,
                               is_template=1,
                               title="TestBoardCopy",
                               board_type="interval_board",
                               board_api=self.IntervalBoardAdapter)
        operation(kOperationDelete, test_board)


if __name__ == "__main__":
    unittest.main()
