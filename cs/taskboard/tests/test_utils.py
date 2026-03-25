#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import mock
import unittest
import pytest
from cs.taskboard import utils


@pytest.mark.unit
class TestUtils(unittest.TestCase):

    @mock.patch.object(utils.sqlapi, "quote", return_value="foo")
    def test_get_board_object_ids_by_task_object_ids_0(self, quote):
        "TestUtils 001: Determine board object ids by task object ids: " \
            "List of one object id is given"
        obj = mock.MagicMock()
        obj.board_object_id = "my board object id"
        with mock.patch.object(utils.sqlapi, "RecordSet2", return_value=[obj]):
            # call method for test
            result = utils.get_board_object_ids_by_task_object_ids(["bar"])

            # check calls on mocked methods
            quote.assert_called_once_with("bar")
            utils.sqlapi.RecordSet2.assert_called_once_with(
                table="cs_taskboard_card",
                condition="context_object_id IN ('foo')",
                columns=["board_object_id"]
            )
            # check return value
            self.assertEqual(result, set(["my board object id"]))

    @mock.patch.object(utils.sqlapi, "quote", return_value="foo")
    def test_get_board_object_ids_by_task_object_ids_1(self, quote):
        "TestUtils 002: Determine board object ids by task object ids: " \
            "Empty list is given"
        obj = mock.MagicMock()
        obj.board_object_id = "my board object id"
        with mock.patch.object(utils.sqlapi, "RecordSet2", return_value=[obj]):
            # call method for test
            result = utils.get_board_object_ids_by_task_object_ids([])

            # check calls on mocked methods
            quote.assert_not_called()
            utils.sqlapi.RecordSet2.assert_not_called()
            # check return value
            self.assertEqual(result, set())

    @mock.patch.object(utils, "clear_update_stack")
    def test_add_to_change_stack_0(self, clear_stack):
        "TestUtils 003: Add object to change stack: " \
            "valid object given, ctx given, not interactive"
        ctx = mock.MagicMock()
        ctx.batch = True
        ctx.interactive = False
        obj = mock.MagicMock()
        obj.cdb_object_id = "foo"
        utils.OBJECTS_CHANGING = set()
        utils.OBJECTS_CHANGED = set()

        # call method for test
        utils.add_to_change_stack(obj, ctx=ctx)

        # check calls on mocked methods
        clear_stack.assert_not_called()

        # check return value
        self.assertEqual(utils.OBJECTS_CHANGING, set(["foo"]))
        self.assertEqual(utils.OBJECTS_CHANGED, set(["foo"]))

    @mock.patch.object(utils, "clear_update_stack")
    def test_add_to_change_stack_1(self, clear_stack):
        "TestUtils 004: Add object to change stack: " \
            "valid object given, ctx given, interactive call"
        ctx = mock.MagicMock()
        ctx.batch = False
        ctx.interactive = True
        obj = mock.MagicMock()
        obj.cdb_object_id = "foo"
        utils.OBJECTS_CHANGING = set()
        utils.OBJECTS_CHANGED = set()

        # call method for test
        utils.add_to_change_stack(obj, ctx=ctx)

        # check calls on mocked methods
        clear_stack.assert_called_once_with()

        # check return value
        self.assertEqual(utils.OBJECTS_CHANGING, set(["foo"]))
        self.assertEqual(utils.OBJECTS_CHANGED, set(["foo"]))

    @mock.patch.object(utils, "clear_update_stack")
    def test_add_to_change_stack_2(self, clear_stack):
        "TestUtils 005: Add object to change stack: " \
            "valid object given, no ctx given"
        obj = mock.MagicMock()
        obj.cdb_object_id = "foo"
        utils.OBJECTS_CHANGING = set()
        utils.OBJECTS_CHANGED = set()

        # call method for test
        utils.add_to_change_stack(obj, ctx=None)

        # check calls on mocked methods
        clear_stack.assert_not_called()

        # check return value
        self.assertEqual(utils.OBJECTS_CHANGING, set(["foo"]))
        self.assertEqual(utils.OBJECTS_CHANGED, set(["foo"]))

    @mock.patch.object(utils, "clear_update_stack")
    def test_add_to_change_stack_3(self, clear_stack):
        "TestUtils 006: Add object to change stack: " \
            "no object given, ctx given, not interactive"
        ctx = mock.MagicMock()
        ctx.batch = True
        ctx.interactive = False
        utils.OBJECTS_CHANGING = set()
        utils.OBJECTS_CHANGED = set()

        # call method for test
        with self.assertRaises(AttributeError):
            utils.add_to_change_stack(None, ctx=ctx)

        # check calls on mocked methods
        clear_stack.assert_not_called()

        # check return value
        self.assertEqual(utils.OBJECTS_CHANGING, set([]))
        self.assertEqual(utils.OBJECTS_CHANGED, set([]))

    @mock.patch.object(utils, "clear_update_stack")
    def test_add_to_change_stack_4(self, clear_stack):
        "TestUtils 007: Add object to change stack: " \
            "no object given, ctx given, interactive call"
        ctx = mock.MagicMock()
        ctx.batch = False
        ctx.interactive = True
        utils.OBJECTS_CHANGING = set()
        utils.OBJECTS_CHANGED = set()

        # call method for test
        with self.assertRaises(AttributeError):
            utils.add_to_change_stack(None, ctx=ctx)

        # check calls on mocked methods
        clear_stack.assert_called_once_with()

        # check return value
        self.assertEqual(utils.OBJECTS_CHANGING, set([]))
        self.assertEqual(utils.OBJECTS_CHANGED, set([]))

    @mock.patch.object(utils, "clear_update_stack")
    def test_add_to_change_stack_5(self, clear_stack):
        "TestUtils 008: Add object to change stack: " \
            "no object given, no ctx given"
        utils.OBJECTS_CHANGING = set()
        utils.OBJECTS_CHANGED = set()

        # call method for test
        with self.assertRaises(AttributeError):
            utils.add_to_change_stack(None, ctx=None)

        # check calls on mocked methods
        clear_stack.assert_not_called()

        # check return value
        self.assertEqual(utils.OBJECTS_CHANGING, set([]))
        self.assertEqual(utils.OBJECTS_CHANGED, set([]))

    @mock.patch.object(utils, "clear_update_stack")
    def test_remove_from_change_stack_0(self, clear_stack):
        "TestUtils 009: Remove object from change stack: " \
            "valid object given, ctx given, not interactive"
        ctx = mock.MagicMock()
        ctx.batch = True
        ctx.interactive = False
        obj = mock.MagicMock()
        obj.cdb_object_id = "foo"
        utils.OBJECTS_CHANGING = set(["foo", "bass"])
        utils.OBJECTS_CHANGED = set(["foo", "bass"])
        with mock.patch.object(
                utils, "get_board_object_ids_by_task_object_ids",
                return_value="bar"):
            board_1 = mock.MagicMock()
            board_2 = mock.MagicMock()
            with mock.patch.object(utils.fBoard, "KeywordQuery",
                                   return_value=[board_1, board_2]):
                # call method for test
                utils.remove_from_change_stack(obj, ctx=ctx)

                # check calls for mocked methods
                utils.get_board_object_ids_by_task_object_ids.\
                    assert_not_called()
                utils.fBoard.KeywordQuery.assert_not_called()
                clear_stack.assert_not_called()

        # check return value
        self.assertEqual(utils.OBJECTS_CHANGING, set(["bass"]))
        self.assertEqual(utils.OBJECTS_CHANGED, set(["foo", "bass"]))

    @mock.patch.object(utils, "clear_update_stack")
    def test_remove_from_change_stack_1(self, clear_stack):
        "TestUtils 010: Remove object from change stack: " \
            "valid object given, ctx given, interactive call"
        ctx = mock.MagicMock()
        ctx.batch = False
        ctx.interactive = True
        obj = mock.MagicMock()
        obj.cdb_object_id = "foo"
        utils.OBJECTS_CHANGING = set(["foo", "bass"])
        utils.OBJECTS_CHANGED = set(["foo", "bass"])
        with mock.patch.object(
                utils, "get_board_object_ids_by_task_object_ids",
                return_value="bar"):
            board_1 = mock.MagicMock()
            board_2 = mock.MagicMock()
            with mock.patch.object(utils.fBoard, "KeywordQuery",
                                   return_value=[board_1, board_2]):
                # call method for test
                utils.remove_from_change_stack(obj, ctx=ctx)

                # check calls for mocked methods
                utils.get_board_object_ids_by_task_object_ids.\
                    assert_called_once_with(set(["foo", "bass"]))
                utils.fBoard.KeywordQuery.assert_called_once_with(
                    cdb_object_id="bar", is_aggregation=0, is_template=0
                )
                clear_stack.assert_called_once_with()

        # check return value
        self.assertEqual(utils.OBJECTS_CHANGING, set(["bass"]))
        self.assertEqual(utils.OBJECTS_CHANGED, set(["foo", "bass"]))

    @mock.patch.object(utils, "clear_update_stack")
    def test_remove_from_change_stack_2(self, clear_stack):
        "TestUtils 011: Remove object from change stack: " \
            "valid object given, no ctx given"
        obj = mock.MagicMock()
        obj.cdb_object_id = "foo"
        utils.OBJECTS_CHANGING = set(["foo", "bass"])
        utils.OBJECTS_CHANGED = set(["foo", "bass"])
        with mock.patch.object(
                utils, "get_board_object_ids_by_task_object_ids",
                return_value="bar"):
            board_1 = mock.MagicMock()
            board_2 = mock.MagicMock()
            with mock.patch.object(utils.fBoard, "KeywordQuery",
                                   return_value=[board_1, board_2]):
                # call method for test
                utils.remove_from_change_stack(obj, ctx=None)

                # check calls for mocked methods
                utils.get_board_object_ids_by_task_object_ids.\
                    assert_not_called()
                utils.fBoard.KeywordQuery.assert_not_called()
                clear_stack.assert_not_called()

        # check return value
        self.assertEqual(utils.OBJECTS_CHANGING, set(["bass"]))
        self.assertEqual(utils.OBJECTS_CHANGED, set(["foo", "bass"]))

    @mock.patch.object(utils, "clear_update_stack")
    def test_remove_from_change_stack_3(self, clear_stack):
        "TestUtils 012: Remove object from change stack: " \
            "no valid object given, ctx given, not interactive"
        ctx = mock.MagicMock()
        ctx.batch = True
        ctx.interactive = False
        utils.OBJECTS_CHANGING = set(["foo", "bass"])
        utils.OBJECTS_CHANGED = set(["foo", "bass"])
        with mock.patch.object(
                utils, "get_board_object_ids_by_task_object_ids",
                return_value="bar"):
            board_1 = mock.MagicMock()
            board_2 = mock.MagicMock()
            with mock.patch.object(utils.fBoard, "KeywordQuery",
                                   return_value=[board_1, board_2]):
                with self.assertRaises(AttributeError):
                    # call method for test
                    utils.remove_from_change_stack(None, ctx=ctx)

                # check calls for mocked methods
                utils.get_board_object_ids_by_task_object_ids.\
                    assert_not_called()
                utils.fBoard.KeywordQuery.assert_not_called()
                clear_stack.assert_not_called()

        # check return value
        self.assertEqual(utils.OBJECTS_CHANGING, set(["foo", "bass"]))
        self.assertEqual(utils.OBJECTS_CHANGED, set(["foo", "bass"]))

    @mock.patch.object(utils, "clear_update_stack")
    def test_remove_from_change_stack_4(self, clear_stack):
        "TestUtils 013: Remove object from change stack: " \
            "no valid object given, ctx given, interactive call"
        ctx = mock.MagicMock()
        ctx.batch = False
        ctx.interactive = True
        utils.OBJECTS_CHANGING = set(["foo", "bass"])
        utils.OBJECTS_CHANGED = set(["foo", "bass"])
        with mock.patch.object(
                utils, "get_board_object_ids_by_task_object_ids",
                return_value="bar"):
            board_1 = mock.MagicMock()
            board_2 = mock.MagicMock()
            with mock.patch.object(utils.fBoard, "KeywordQuery",
                                   return_value=[board_1, board_2]):
                with self.assertRaises(AttributeError):
                    # call method for test
                    utils.remove_from_change_stack(None, ctx=ctx)

                # check calls for mocked methods
                utils.get_board_object_ids_by_task_object_ids.\
                    assert_not_called()
                utils.fBoard.KeywordQuery.assert_not_called()
                clear_stack.assert_not_called()

        # check return value
        self.assertEqual(utils.OBJECTS_CHANGING, set(["foo", "bass"]))
        self.assertEqual(utils.OBJECTS_CHANGED, set(["foo", "bass"]))

    @mock.patch.object(utils, "clear_update_stack")
    def test_remove_from_change_stack_5(self, clear_stack):
        "TestUtils 014: Remove object from change stack: " \
            "no valid object given, no ctx given"
        utils.OBJECTS_CHANGING = set(["foo", "bass"])
        utils.OBJECTS_CHANGED = set(["foo", "bass"])
        with mock.patch.object(
                utils, "get_board_object_ids_by_task_object_ids",
                return_value="bar"):
            board_1 = mock.MagicMock()
            board_2 = mock.MagicMock()
            with mock.patch.object(utils.fBoard, "KeywordQuery",
                                   return_value=[board_1, board_2]):
                with self.assertRaises(AttributeError):
                    # call method for test
                    utils.remove_from_change_stack(None, ctx=None)

                # check calls for mocked methods
                utils.get_board_object_ids_by_task_object_ids.\
                    assert_not_called()
                utils.fBoard.KeywordQuery.assert_not_called()
                clear_stack.assert_not_called()

        # check return value
        self.assertEqual(utils.OBJECTS_CHANGING, set(["foo", "bass"]))
        self.assertEqual(utils.OBJECTS_CHANGED, set(["foo", "bass"]))

    @mock.patch.object(utils, "clear_update_stack")
    def test_remove_from_change_stack_6(self, clear_stack):
        "TestUtils 015: Remove last object from change stack: " \
            "valid object given, ctx given, not interactive"
        ctx = mock.MagicMock()
        ctx.batch = True
        ctx.interactive = False
        obj = mock.MagicMock()
        obj.cdb_object_id = "foo"
        utils.OBJECTS_CHANGING = set(["foo"])
        utils.OBJECTS_CHANGED = set(["foo", "bass"])
        with mock.patch.object(
                utils, "get_board_object_ids_by_task_object_ids",
                return_value="bar"):
            board_1 = mock.MagicMock()
            board_2 = mock.MagicMock()
            with mock.patch.object(utils.fBoard, "KeywordQuery",
                                   return_value=[board_1, board_2]):
                # call method for test
                utils.remove_from_change_stack(obj, ctx=ctx)

                # check calls for mocked methods
                utils.get_board_object_ids_by_task_object_ids.\
                    assert_called_once_with(set(["foo", "bass"]))
                utils.fBoard.KeywordQuery.assert_called_once_with(
                    cdb_object_id="bar", is_aggregation=0, is_template=0
                )
                clear_stack.assert_called_once_with()

        # check return value
        self.assertEqual(utils.OBJECTS_CHANGING, set())
        self.assertEqual(utils.OBJECTS_CHANGED, set(["foo", "bass"]))

    @mock.patch.object(utils, "clear_update_stack")
    def test_remove_from_change_stack_7(self, clear_stack):
        "TestUtils 016: Remove last object from change stack: " \
            "valid object given, ctx given, interactive call"
        ctx = mock.MagicMock()
        ctx.batch = False
        ctx.interactive = True
        obj = mock.MagicMock()
        obj.cdb_object_id = "foo"
        utils.OBJECTS_CHANGING = set(["foo"])
        utils.OBJECTS_CHANGED = set(["foo", "bass"])
        with mock.patch.object(
                utils, "get_board_object_ids_by_task_object_ids",
                return_value="bar"):
            board_1 = mock.MagicMock()
            board_2 = mock.MagicMock()
            with mock.patch.object(utils.fBoard, "KeywordQuery",
                                   return_value=[board_1, board_2]):
                # call method for test
                utils.remove_from_change_stack(obj, ctx=ctx)

                # check calls for mocked methods
                utils.get_board_object_ids_by_task_object_ids.\
                    assert_called_once_with(set(["foo", "bass"]))
                utils.fBoard.KeywordQuery.assert_called_once_with(
                    cdb_object_id="bar", is_aggregation=0, is_template=0
                )
                clear_stack.assert_called_once_with()

        # check return value
        self.assertEqual(utils.OBJECTS_CHANGING, set())
        self.assertEqual(utils.OBJECTS_CHANGED, set(["foo", "bass"]))

    @mock.patch.object(utils, "clear_update_stack")
    def test_remove_from_change_stack_8(self, clear_stack):
        "TestUtils 017: Remove last object from change stack: " \
            "valid object given, no ctx given"
        obj = mock.MagicMock()
        obj.cdb_object_id = "foo"
        utils.OBJECTS_CHANGING = set(["foo"])
        utils.OBJECTS_CHANGED = set(["foo", "bass"])
        with mock.patch.object(
                utils, "get_board_object_ids_by_task_object_ids",
                return_value="bar"):
            board_1 = mock.MagicMock()
            board_2 = mock.MagicMock()
            with mock.patch.object(utils.fBoard, "KeywordQuery",
                                   return_value=[board_1, board_2]):
                # call method for test
                utils.remove_from_change_stack(obj, ctx=None)

                # check calls for mocked methods
                utils.get_board_object_ids_by_task_object_ids.\
                    assert_called_once_with(set(["foo", "bass"]))
                utils.fBoard.KeywordQuery.assert_called_once_with(
                    cdb_object_id="bar", is_aggregation=0, is_template=0
                )
                clear_stack.assert_called_once_with()

        # check return value
        self.assertEqual(utils.OBJECTS_CHANGING, set())
        self.assertEqual(utils.OBJECTS_CHANGED, set(["foo", "bass"]))

    def test_clear_update_stack(self):
        "TestUtils 018: clear update stack: " \
            "very simple code --> skipped"

    def test_is_board_update_activated(self):
        "TestUtils 019: check if board update is active: " \
            "very simple code --> skipped"

    def test_NoBoardUpdate(self):
        "TestUtils 020: Tests deactivation of board update"
        self.assertEqual(utils.BOARD_UPDATE_ACTIVATED, True)
        with utils.NoBoardUpdate():
            self.assertEqual(utils.BOARD_UPDATE_ACTIVATED, False)
        self.assertEqual(utils.BOARD_UPDATE_ACTIVATED, True)
