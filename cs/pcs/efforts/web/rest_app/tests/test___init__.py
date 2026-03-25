#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

import unittest

import mock
import pytest

from cs.pcs.efforts.web import rest_app

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


@pytest.mark.unit
class Utility(unittest.TestCase):
    @mock.patch.object(rest_app.InternalMyEffortsApp, "get_app")
    @mock.patch.object(rest_app, "get_url_patterns")
    def test_get_app_url_patterns(self, get_url_patterns, get_app):
        self.assertEqual(
            rest_app.get_app_url_patterns("request"),
            get_url_patterns.return_value,
        )
        get_url_patterns.assert_called_once_with(
            "request",
            get_app.return_value,
            [
                ("efforts", rest_app.EffortsModel, []),
                ("recUsedTasks", rest_app.RecentlyUsedTasks, ["user_id"]),
            ],
        )
        get_app.assert_called_once_with("request")


if __name__ == "__main__":
    unittest.main()
