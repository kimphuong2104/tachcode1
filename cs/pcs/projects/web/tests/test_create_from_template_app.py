#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


import unittest

import mock
from cdb import testcase
from cs.web.components.base.main import SettingDict

from cs.pcs.projects.web import create_from_template_app


class ProjectTemplateCreateAppTest(testcase.RollbackTestCase):
    app = create_from_template_app.ProjectTemplateCreateApp

    @mock.patch.object(
        create_from_template_app.FormInfoBase,
        "get_catalog_config",
        return_value="catalog_config",
    )
    @mock.patch.object(create_from_template_app.entities, "CDBClassDef")
    @mock.patch.object(
        create_from_template_app.util, "get_label", return_value="wizard_label"
    )
    @mock.patch.object(create_from_template_app.operations, "OperationInfo")
    @mock.patch.object(create_from_template_app.BaseApp, "update_app_setup")
    def test_update_app_setup(
        self, mock_super, OperationInfo, get_label, CDBClassDef, get_catalog_config
    ):
        self.maxDiff = None
        # mock all external functions and their results

        # if the model is used in a future version
        # it needs to be properly mocked
        model = None
        app_setup = SettingDict()
        request = mock.MagicMock()
        request.class_link.return_value = "class_link"
        # operations = mock.MagicMock()
        oi = mock.MagicMock()
        oi.get_icon_urls.return_value = ["icon_url"]
        oi.get_label.return_value = "operation_label"
        OperationInfo.return_value = oi
        # entities = mock.MagicMock()
        cdef = mock.MagicMock()
        cdef.getDesignation.return_value = "class_def_designation"
        CDBClassDef.return_value = cdef
        self.app().update_app_setup(app_setup, model, request)

        # assert that all external functions are called correctly
        mock_super.assert_called_with(app_setup, model, request)
        get_catalog_config.assert_called_with(
            request,
            create_from_template_app.TEMPLATE_CATALOG,
            is_combobox=False,
            as_objs=True,
        )
        OperationInfo.assert_called_with(
            create_from_template_app.CLASSNAME, "cdbpcs_create_project"
        )
        oi.get_icon_urls.assert_called_once()
        oi.get_label.assert_called_once()
        cdef.getDesignation.assert_called_once()
        get_label.assert_has_calls(
            [
                mock.call(create_from_template_app.WIZARD_LABEL_1),
                mock.call(create_from_template_app.WIZARD_LABEL_2),
            ]
        )
        # assert that the result is correct
        self.assertEqual(
            app_setup,
            {
                "template_catalog_config": "catalog_config",
                "wizard_labels": ["wizard_label", "wizard_label"],
                "header_icon": "/icon_url",
                "header_title": "class_def_designation: operation_label",
            },
        )


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
