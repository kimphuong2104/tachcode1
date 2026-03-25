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

from cs.taskboard import column_mappers as cm


@pytest.mark.unit
class TestColumnMappers(unittest.TestCase):

    def test_change_to_01(self):
        "TestColumnMappers 001: BasicOLCColumnMapper.change_to: "\
            "status not changed"
        board_adapter = mock.Mock()
        column = mock.Mock()
        card = mock.Mock()
        task = mock.Mock()
        card.TaskObject = task

        # set values
        board_adapter.get_status.return_value = "a valid status"
        column.column_name = "valid_colmn_name"
        column_dict = dict(valid_colmn_name=[
            "a valid status", "another valid status"
        ])
        card.context_object_id = "foo"

        # call method
        with mock.patch.object(cm.BasicOLCColumnMapper,
                               "COLUMN_TO_STATUS",
                               new_callable=mock.PropertyMock,
                               return_value=column_dict):
            cm.BasicOLCColumnMapper.change_to(
                board_adapter, None, card, column)

        # check called methods
        task.ChangeState.assert_not_called()
        board_adapter.get_status.assert_called_once_with('foo')

    def test_change_to_02(self):
        "TestColumnMappers 002: BasicOLCColumnMapper.change_to: "\
            "status changed from valid status to some other valid status"
        board_adapter = mock.Mock()
        column = mock.Mock()
        card = mock.Mock()
        task = mock.Mock()
        card.TaskObject = task

        # set values
        board_adapter.get_status.return_value = "a valid status"
        column.column_name = "valid_colmn_name"
        column_dict = dict(valid_colmn_name=[
            "some other valid status", "another valid status"
        ])
        card.context_object_id = "foo"

        # call method
        with mock.patch.object(cm.BasicOLCColumnMapper,
                               "COLUMN_TO_STATUS",
                               new_callable=mock.PropertyMock,
                               return_value=column_dict):
            cm.BasicOLCColumnMapper.change_to(
                board_adapter, None, card, column)

        # check called methods
        task.ChangeState.assert_called_once_with(
            "some other valid status")
        board_adapter.get_status.assert_called_once_with('foo')

    def test_change_to_03(self):
        "TestColumnMappers 003: BasicOLCColumnMapper.change_to: "\
            "trying status change without status list"
        board_adapter = mock.Mock()
        column = mock.Mock()
        card = mock.Mock()
        task = mock.Mock()
        card.TaskObject = task

        # set values
        board_adapter.get_status.return_value = "a valid status"
        column.column_name = "valid_colmn_name"
        column_dict = dict(valid_colmn_name=None)
        card.context_object_id = "foo"

        # call method
        with mock.patch.object(cm.BasicOLCColumnMapper,
                               "COLUMN_TO_STATUS",
                               new_callable=mock.PropertyMock,
                               return_value=column_dict):
            cm.BasicOLCColumnMapper.change_to(
                board_adapter, None, card, column)

        # check called methods
        task.ChangeState.assert_not_called()
        board_adapter.get_status.assert_called_once_with('foo')

    def test_validate_04(self):
        "TestColumnMappers 004: OLCColumnMapper.validate: "\
            "status list contains status and "\
            "list of columns contains column"
        board_adapter = mock.Mock()
        card = mock.Mock()

        # set values
        board_adapter.get_status.return_value = "valid_status"
        board_adapter.get_column_type.return_value = "a valid column"
        column_dict = dict(valid_status=[
            "another valid column", "a valid column"
        ])
        card.context_object_id = "foo"
        card.Column = "bass"

        # call method
        with mock.patch.object(cm.OLCColumnMapper,
                               "STATUS_TO_COLUMN",
                               new_callable=mock.PropertyMock,
                               return_value=column_dict):
            result = cm.OLCColumnMapper.validate(
                board_adapter, None, card, None)

        # check called methods
        self.assertTrue(result)
        board_adapter.get_status.assert_called_once_with("foo")
        board_adapter.get_column_type.assert_called_once_with("bass")

    def test_validate_05(self):
        "TestColumnMappers 005: OLCColumnMapper.validate: "\
            "status list contains status and "\
            "list of columns does not contain column"
        board_adapter = mock.Mock()
        card = mock.Mock()

        # set values
        board_adapter.get_status.return_value = "valid_status"
        board_adapter.get_column_type.return_value = "a valid column"
        column_dict = dict(valid_status=[
            "another valid column"
        ])
        card.context_object_id = "foo"
        card.Column = "bass"

        # call method
        with mock.patch.object(cm.OLCColumnMapper,
                               "STATUS_TO_COLUMN",
                               new_callable=mock.PropertyMock,
                               return_value=column_dict):
            result = cm.OLCColumnMapper.validate(
                board_adapter, None, card, None)

        # check called methods
        self.assertFalse(result)
        board_adapter.get_status.assert_called_once_with("foo")
        board_adapter.get_column_type.assert_called_once_with("bass")

    def test_validate_06(self):
        "TestColumnMappers 006: OLCColumnMapper.validate: "\
            "status list does not contain status and "\
            "list of columns contains column"
        board_adapter = mock.Mock()
        card = mock.Mock()

        # set values
        board_adapter.get_status.return_value = "valid_status"
        board_adapter.get_column_type.return_value = "a valid column"
        column_dict = dict(another_valid_status=[
            "a valid column", "another valid column"
        ])
        card.context_object_id = "foo"
        card.Column = "bass"

        # call method
        with mock.patch.object(cm.OLCColumnMapper,
                               "STATUS_TO_COLUMN",
                               new_callable=mock.PropertyMock,
                               return_value=column_dict):
            result = cm.OLCColumnMapper.validate(
                board_adapter, None, card, None)

        # check called methods
        self.assertFalse(result)
        board_adapter.get_status.assert_called_once_with("foo")
        board_adapter.get_column_type.assert_not_called()

    def test_validate_07(self):
        "TestColumnMappers 007: OLCColumnMapper.validate: "\
            "status list does not contain status and "\
            "list of columns does not contain column"
        board_adapter = mock.Mock()
        card = mock.Mock()

        # set values
        board_adapter.get_status.return_value = "valid_status"
        board_adapter.get_column_type.return_value = "a valid column"
        column_dict = dict(another_valid_status=[
            "another valid column"
        ])
        card.context_object_id = "foo"
        card.Column = "bass"

        # call method
        with mock.patch.object(cm.OLCColumnMapper,
                               "STATUS_TO_COLUMN",
                               new_callable=mock.PropertyMock,
                               return_value=column_dict):
            result = cm.OLCColumnMapper.validate(
                board_adapter, None, card, None)

        # check called methods
        self.assertFalse(result)
        board_adapter.get_status.assert_called_once_with("foo")
        board_adapter.get_column_type.assert_not_called()
