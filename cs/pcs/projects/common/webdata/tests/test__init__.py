#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access


__revision__ = "$Id$"

import unittest

import mock
import pytest

from cs.pcs.projects.common import webdata


@pytest.mark.unit
class Utility(unittest.TestCase):
    @mock.patch.object(webdata, "get_url_patterns")
    @mock.patch.object(webdata.WebData, "get_app")
    def test_get_app_url_patterns(self, get_app, get_url_patterns):
        self.assertEqual(
            webdata.get_app_url_patterns("request"),
            get_url_patterns.return_value,
        )
        get_app.assert_called_once_with("request")
        get_url_patterns.assert_called_once_with(
            "request",
            get_app.return_value,
            [
                ("object_data", webdata.GenericAsyncDataModel, []),
                ("subject_thumbnails", webdata.SubjectThumbnailModel, []),
            ],
        )


@pytest.mark.unit
class WebData(unittest.TestCase):
    @mock.patch.object(webdata, "get_internal", autospec=True)
    @mock.patch.object(webdata, "APP", "APP")
    def test_get_app(self, get_internal):
        "returns app URL"
        self.assertEqual(
            webdata.WebData.get_app("request"),
            get_internal.return_value.child.return_value,
        )
        get_internal.assert_called_once_with("request")
        get_internal.return_value.child.assert_called_once_with("APP")

    @mock.patch.object(webdata, "WebData")
    def test__mount_app(self, WebData):
        "returns initialized app"
        self.assertEqual(webdata._mount_app(), WebData.return_value)
        WebData.assert_called_once_with()

    @mock.patch.object(webdata, "GenericAsyncDataModel", autospec=True)
    def test_get_model(self, GAModel):
        "returns initialized model"
        self.assertEqual(webdata.get_model("request"), GAModel.return_value)
        GAModel.assert_called_once_with()

    def test_get_data_via_post(self):
        "returns all requested data"
        model = mock.MagicMock(spec=webdata.GenericAsyncDataModel)
        self.assertEqual(
            webdata.get_data_via_post(model, "request"), model.get_data.return_value
        )
        model.get_data.assert_called_once_with("request")

    @mock.patch.object(webdata, "SubjectThumbnailModel", autospec=True)
    def test_get_thumbnail_model(self, STModel):
        "returns initialized thumbnail model"
        self.assertEqual(webdata.get_thumbnail_model("request"), STModel.return_value)
        STModel.assert_called_once_with()

    def test_get_thumbnail_via_post(self):
        "returns requested thumbnails"
        model = mock.MagicMock(spec=webdata.SubjectThumbnailModel)
        self.assertEqual(
            webdata.get_thumbnail_via_post(model, "request"),
            model.get_data.return_value,
        )
        model.get_data.assert_called_once_with("request")


if __name__ == "__main__":
    unittest.main()
