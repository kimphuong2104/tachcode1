#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id$"

import unittest

import mock
import pytest

from cs.pcs.substitute import main


@pytest.mark.unit
class Utility(unittest.TestCase):
    @mock.patch.object(main, "get_url_patterns")
    @mock.patch("cs.pcs.substitute.rest_app.App.get_app")
    def test_get_app_url_patterns(self, get_app, get_url_patterns):
        self.assertEqual(
            main.get_app_url_patterns("request"),
            get_url_patterns.return_value,
        )
        get_app.assert_called_once_with("request")
        get_url_patterns.assert_called_once_with(
            "request",
            get_app.return_value,
            [
                ("team", main.rest_app_model.ProjectTeamModel, ["rest_key"]),
                ("substitutes", main.rest_app_model.UserSubstitutesModel, ["persno"]),
                (
                    "substitution_info",
                    main.rest_app_model.SubstitutionInfoModel,
                    ["cdb_project_id"],
                ),
                (
                    "roles",
                    main.rest_app_model.RoleComparisonModel,
                    ["substitute_oid", "cdb_project_id"],
                ),
                (
                    "role_assignment",
                    main.rest_app_model.SubjectModel,
                    ["classname", "role_id", "persno"],
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
