# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import unittest

import mock
import pytest

from cs.pcs.projects import web


@pytest.mark.unit
class Utility(unittest.TestCase):
    @mock.patch(
        "cs.pcs.projects.web.rest_app.project_structure.get_app_url_patterns",
        return_value={"structure": 1},
    )
    @mock.patch(
        "cs.pcs.projects.web.rest_app.milestones.get_app_url_patterns",
        return_value={"milestones": 1},
    )
    @mock.patch(
        "cs.pcs.projects.web.rest_app.get_app_url_patterns",
        return_value={"rest_app": 1},
    )
    def test_get_app_url_patterns(self, rest_app, milestones, structure):
        self.assertEqual(
            web.get_app_url_patterns("request"),
            {
                "rest_app": 1,
                "milestones": 1,
                "structure": 1,
            },
        )
        rest_app.assert_called_once_with("request")
        milestones.assert_called_once_with("request")
        structure.assert_called_once_with("request")

    @mock.patch.object(web.util, "PersonalSettings")
    @mock.patch.object(web, "auth")
    def test_setup_settings(self, auth, p_s):
        p_s.return_value.getValueOrDefaultForUser.return_value = "42"
        app_setup = mock.MagicMock()
        self.assertIsNone(web.setup_settings(None, None, app_setup))
        app_setup.merge_in.assert_called_once_with(
            ["pcs-table-default-settings"],
            {"thumbnails": 42},
        )
        p_s.assert_called_once_with()
        p_s.return_value.getValueOrDefaultForUser.assert_called_once_with(
            "cs.pcs.table.project.thumbnails",
            "",
            auth.persno,
            "",
        )

    @mock.patch.object(web.static, "Registry")
    @mock.patch.object(web.static, "Library")
    @mock.patch.object(web.os.path, "join", return_value="/js/build")
    @mock.patch.object(web, "VERSION", "VERSION")
    @mock.patch.object(web, "APP", "APP")
    def test_register_libraries(self, join, Library, Registry):
        self.assertIsNone(web.register_libraries())
        Library.assert_called_once_with("APP", "VERSION", "/js/build")
        Library.return_value.add_file.assert_has_calls(
            [
                mock.call("APP.js"),
                mock.call("APP.js.map"),
            ]
        )
        Registry.assert_called_once_with()
        Registry.return_value.add.assert_called_once_with(Library.return_value)


if __name__ == "__main__":
    unittest.main()
