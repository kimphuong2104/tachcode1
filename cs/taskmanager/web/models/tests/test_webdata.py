#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest

import mock
import pytest

from cs.taskmanager.web.models import webdata


@pytest.mark.unit
class Webdata(unittest.TestCase):
    @mock.patch.object(webdata.logging, "error")
    def test_get_async_data_no_payload(self, error):
        request = mock.MagicMock(json=None)
        wd = webdata.Webdata()
        with self.assertRaises(webdata.HTTPBadRequest):
            wd.get_async_data(request)
        error.assert_called_once()

    @mock.patch.object(webdata.Webdata, "_get_async_data")
    def test_get_async_data(self, _get_async_data):
        request = mock.MagicMock(json={1: 2})
        wd = webdata.Webdata()
        rv = wd.get_async_data(request)
        _get_async_data.assert_called_once_with(request.json, request)
        self.assertEqual(rv, _get_async_data.return_value)

    def test__get_async_data_no_params(self):
        request = mock.MagicMock(json={"cdbtask": None})
        wd = webdata.Webdata()
        with self.assertRaises(webdata.HTTPBadRequest):
            # pylint: disable=protected-access
            wd._get_async_data(request.json, request)

    @mock.patch.object(webdata, "CDBClassDef")
    def test__get_async_data_no_class_def(self, CDBClassDef):
        CDBClassDef.return_value = None
        request = mock.MagicMock(
            json={"cdbtask": {"task_object_ids": [1], "propnames": ["p1"]}}
        )
        wd = webdata.Webdata()
        # pylint: disable=protected-access
        result = wd._get_async_data(request.json, request)
        CDBClassDef.assert_called_once_with("cdbtask")
        self.assertEqual(result, {})

    @mock.patch.object(webdata.tools, "getObjectByName")
    @mock.patch.object(webdata, "CDBClassDef")
    def test__get_async_data_no_klass(self, CDBClassDef, getObjectByName):
        CDBClassDef.return_value = mock.MagicMock(
            getFullQualifiedPythonName=mock.MagicMock(return_value="a")
        )
        getObjectByName.return_value = None
        request = mock.MagicMock(
            json={"cdbtask": {"task_object_ids": [1], "propnames": ["p1"]}}
        )
        wd = webdata.Webdata()
        # pylint: disable=protected-access
        result = wd._get_async_data(request.json, request)
        CDBClassDef.assert_called_once_with("cdbtask")
        getObjectByName.assert_called_once_with("a")
        self.assertEqual(result, {})

    @mock.patch.object(webdata, "evaluate")
    @mock.patch.object(webdata.Webdata, "get_rest_value")
    @mock.patch.object(webdata.tools, "getObjectByName")
    @mock.patch.object(webdata, "CDBClassDef")
    def test__get_async_data(
        self, CDBClassDef, getObjectByName, get_rest_value, evaluate
    ):
        CDBClassDef.return_value = mock.MagicMock(
            getFullQualifiedPythonName=mock.MagicMock(return_value="a")
        )
        tasks = [mock.MagicMock(p1="abc", cdb_object_id=1)]
        kwQuery = mock.MagicMock(return_value=tasks)

        getObjectByName.return_value = mock.MagicMock(KeywordQuery=kwQuery)
        request = mock.MagicMock(
            json={"cdbtask": {"task_object_ids": [1], "propnames": ["p1"]}}
        )

        get_rest_value.return_value = "abc"
        evaluate.return_value = "non-rest"

        wd = webdata.Webdata()
        # pylint: disable=protected-access
        result = wd._get_async_data(request.json, request)
        kwQuery.assert_called_once_with(cdb_object_id=[1])
        evaluate.assert_called_once_with(tasks[0], "p1")
        get_rest_value.assert_called_once_with(evaluate.return_value, request)

        self.assertEqual(result, {"cdbtask": {1: {"p1": "abc"}}})

    @mock.patch.object(webdata, "get_object_ui_link")
    def test_get_object_value(self, get_object_ui_link):
        obj = mock.MagicMock(
            GetDescription=mock.MagicMock(return_value="desc"),
            GetObjectIcon=mock.MagicMock(return_value="icon"),
        )
        request = mock.MagicMock()
        get_object_ui_link.return_value = "link"

        wd = webdata.Webdata()
        result = wd.get_object_value(obj, request)

        self.assertEqual(
            result,
            {
                "link": {"to": get_object_ui_link.return_value, "title": "desc"},
                "text": "desc",
                "icon": {"src": "icon", "size": "sm", "title": "desc"},
            },
        )
