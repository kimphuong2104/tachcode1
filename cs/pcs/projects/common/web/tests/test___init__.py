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

from cs.pcs.projects.common import web


@pytest.mark.unit
class Utility(unittest.TestCase):
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

    @mock.patch.object(web, "unquote")
    def test_get_url_patterns(self, unquote):
        request = mock.MagicMock()
        models = [
            ("foo", "foo_model", ["f", "oo"]),
            ("bar", "bar_model", ["ba", "r"]),
        ]
        self.assertEqual(
            web.get_url_patterns(request, "app", models),
            {
                "foo": unquote.return_value,
                "bar": unquote.return_value,
            },
        )
        request.class_link.assert_has_calls(
            [
                mock.call("foo_model", {"f": "${f}", "oo": "${oo}"}, app="app"),
                mock.call("bar_model", {"ba": "${ba}", "r": "${r}"}, app="app"),
            ]
        )
        unquote.assert_has_calls(2 * [mock.call(request.class_link.return_value)])

    @mock.patch.object(web, "get_ui_app")
    @mock.patch.object(web, "ClassViewModel")
    def test_get_app_url_patterns(self, ClassViewModel, get_ui_app):
        request = mock.MagicMock()
        request.link.return_value = "/..."
        self.assertEqual(
            web.get_app_url_patterns(request),
            {
                "Person": "/.../${subject_id}",
                "PCS Role": "/.../${subject_id}@${cdb_project_id}",
                "Common Role": "/.../${subject_id}",
            },
        )
        ClassViewModel.assert_has_calls(
            [
                mock.call("person", None),
                mock.call("cdbpcs_prj_role", None),
                mock.call("global_role", None),
            ]
        )
        request.link.assert_has_calls(
            [
                mock.call(ClassViewModel.return_value, app=get_ui_app.return_value),
            ]
        )
        get_ui_app.assert_called_once_with(request)


if __name__ == "__main__":
    unittest.main()
