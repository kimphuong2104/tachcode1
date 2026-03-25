#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import mock

from cs.taskmanager import context


class Utility(unittest.TestCase):
    @mock.patch.object(context, "get_cdbpc_url")
    @mock.patch.object(context.misc, "CDBApplicationInfo")
    def test_get_ui_link_pc(self, CDBApplicationInfo, get_cdbpc_url):
        CDBApplicationInfo.return_value = mock.MagicMock(
            rootIsa=mock.MagicMock(return_value=True)
        )
        get_cdbpc_url.return_value = "pc_url"
        oh = mock.MagicMock()
        self.assertEqual(
            context.get_ui_link(oh, "cdef", "restkey", None),
            get_cdbpc_url.return_value,
        )

    @mock.patch.object(context.misc, "CDBApplicationInfo")
    def test_get_ui_link_web(self, CDBApplicationInfo):
        CDBApplicationInfo.return_value = mock.MagicMock(
            rootIsa=mock.MagicMock(return_value=False)
        )
        oh = mock.MagicMock()
        cdef = mock.MagicMock()
        request = mock.MagicMock(application_url="app_url")
        cdef.getRESTName.return_value = "rest_name"

        self.assertEqual(
            context.get_ui_link(oh, cdef, "restkey", request),
            context.SYSTEM_LINK_PATTERN.format(
                base=request.application_url, restName="rest_name", restKey="restkey"
            ),
        )

    @mock.patch.object(context, "get_object_icon")
    @mock.patch.object(context, "get_ui_link")
    @mock.patch.object(context, "get_restkey")
    def test_update_objects(self, get_restkey, get_ui_link, get_object_icon):
        get_restkey.return_value = "restkey"
        get_ui_link.return_value = "link"
        get_object_icon.return_value = "icon"

        oh = mock.MagicMock()
        oh.getClassDef.return_value = "classdef"
        oh.getDesignation.return_value = "description"

        objects = {}

        self.assertEqual(
            context.update_objects(objects, oh, None),
            get_restkey.return_value,
        )
        self.assertIn(get_restkey.return_value, objects)

        obj = {
            "description": oh.getDesignation.return_value,
            "system:ui_link": get_ui_link.return_value,
            "icon": get_object_icon.return_value,
        }
        self.assertDictEqual(objects[get_restkey.return_value], obj)

    @mock.patch.object(context.logging, "info")
    @mock.patch.object(context, "get_relship_def")
    def test_navigate_relship(self, get_relship_def, info):
        get_relship_def.return_value = mock.MagicMock(
            is_one_on_one=mock.MagicMock(return_value=False)
        )
        navigate_OneOnOne_Relship = mock.MagicMock(return_value=[])
        navigate_Relship = mock.MagicMock(return_value=[])
        obj_handle = mock.MagicMock(
            navigate_OneOnOne_Relship=navigate_OneOnOne_Relship,
            navigate_Relship=navigate_Relship,
        )
        relship = mock.MagicMock(parent_relship_name="parent", fallback_relship_name="")

        self.assertEqual(context.navigate_relship(obj_handle, relship)[0], [])
        navigate_OneOnOne_Relship.assert_not_called()
        navigate_Relship.assert_called_once_with("parent")
        info.assert_called_once()

    @mock.patch.object(context, "get_relship_def")
    def test_navigate_relship_one_on_one(self, get_relship_def):
        get_relship_def.return_value = mock.MagicMock(
            is_one_on_one=mock.MagicMock(return_value=True)
        )
        navigate_OneOnOne_Relship = mock.MagicMock(return_value=[])
        navigate_Relship = mock.MagicMock(return_value=[])
        obj_handle = mock.MagicMock(
            navigate_OneOnOne_Relship=navigate_OneOnOne_Relship,
            navigate_Relship=navigate_Relship,
        )
        relship = mock.MagicMock(
            parent_relship_name="parent", fallback_relship_name="fallback"
        )

        self.assertEqual(context.navigate_relship(obj_handle, relship)[0], [])
        navigate_OneOnOne_Relship.assert_has_calls(
            [
                mock.call("parent"),
                mock.call("fallback"),
            ]
        )
        navigate_Relship.assert_not_called()

    @mock.patch.object(context, "navigate_relship")
    def test_resolve_contexts_exit_cond(self, navigate_relship):
        navigate_relship.return_value = [], False
        oh = mock.MagicMock()

        result = ["abc"]
        relship_mock = mock.MagicMock(parent_classname="c1", source_classname="c2")
        self.assertEqual(
            context.resolve_contexts(None, [relship_mock], {}, None, result),
            [],
        )
        self.assertEqual(
            context.resolve_contexts(oh, [], {}, None, result),
            result,
        )
        self.assertEqual(
            context.resolve_contexts(oh, [relship_mock], {}, None, result),
            [],
        )
        navigate_relship.assert_called_once_with(oh, relship_mock)

    @mock.patch.object(context, "update_objects")
    @mock.patch.object(context, "navigate_relship")
    def test_resolve_contexts(self, navigate_relship, update_objects):
        oh1 = mock.MagicMock()
        oh2 = mock.MagicMock()
        relship_mock = mock.MagicMock(parent_classname="c1", source_classname="c2")
        navigate_relship.return_value = [oh2], False
        update_objects.return_value = "oh2"
        r_input = [["oh1"]]
        result = context.resolve_contexts(oh1, [relship_mock], {}, None, r_input)

        navigate_relship.assert_called_once_with(oh1, relship_mock)
        update_objects.assert_called_once_with({}, oh2, None)
        self.assertEqual(result, [["oh1", "oh2"]])

    def test_get_redundant_none(self):
        with self.assertRaises(TypeError):
            context.get_redundant(123, 456, None, None)

    def test_get_redundant_empty(self):
        self.assertIsNone(
            context.get_redundant(123, 456, [], []),
        )

    def test_get_redundant_no_overlap(self):
        self.assertIsNone(
            context.get_redundant(123, 456, ["a", "b", "c"], ["b", "a", "c"]),
        )

    def test_get_redundant_overlap_0(self):
        self.assertEqual(
            context.get_redundant(123, 456, ["a", "b", "c", "d"], ["a", "b", "c"]),
            456,
        )

    def test_get_redundant_overlap_1(self):
        self.assertEqual(
            context.get_redundant(123, 456, ["b", "c", "d"], ["a", "b", "c", "d"]),
            123,
        )

    def test_filter_redundant_none(self):
        with self.assertRaises(TypeError):
            context.filter_redundant(None)

    def test_filter_redundant_empty(self):
        self.assertEqual(context.filter_redundant([]), [])

    def test_filter_redundant_empty_paths(self):
        with self.assertRaises(IndexError):
            context.filter_redundant([[], []])

    def test_filter_redundant_single_path(self):
        self.assertEqual(context.filter_redundant([["foo"]]), [["foo"]])

    def test_filter_redundant(self):
        self.assertEqual(
            context.filter_redundant(
                [
                    ["a", "b", "c", "d"],
                    ["a", "c", "d"],
                    ["a", "b", "d"],
                    ["b", "c"],
                ]
            ),
            [
                ["a", "b", "c", "d"],
                ["a", "c", "d"],
            ],
        )
