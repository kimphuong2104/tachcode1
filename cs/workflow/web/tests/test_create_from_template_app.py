#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from mock import MagicMock
import mock

from cdb import testcase
from cs.workflow.web import create_from_template_app


def setup_module():
    testcase.run_level_setup()


class WFTemplateCreateAppTestCase(testcase.RollbackTestCase):
    def test_update_app_setup(self):
        self.maxDiff = None
        x = create_from_template_app.WFTemplateCreateApp()
        request = mock.MagicMock()
        request.link.return_value = "link"
        request.class_link.return_value = "class link"
        app_setup = {}
        x.update_app_setup(app_setup, None, request)
        self.assertLessEqual({
            "catalogTableURL": "link",
            "itemsURL": "link",
            "queryFormURL": "link",
            "selectURL": "link",
            "typeAheadURL": "link",
            "userSettings": {
                "preview": u"",
                "settingKey": "cdbwf_process_templ",
            },
            "valueCheckURL": "link",
        }.items(), app_setup["template_catalog_config"].items())
        self.assertEqual(
            app_setup["create_link"],
            "link"
        )
        self.assertEqual(
            app_setup["wizard_labels"],
            [u'Vorlage ausw\xe4hlen', u'Datenblatt']
        )


class WFTemplateCreateModelTestCase(testcase.RollbackTestCase):
    def test_createFromTemplate_EmptyObject(self):
        x = create_from_template_app.WFTemplateCreateModel()

        with self.assertRaises(TypeError):
            x.createFromTemplate(None, None)

    @mock.patch.object(create_from_template_app, "ByID")
    def test_createFromTemplate(self, ByID):
        x = create_from_template_app.WFTemplateCreateModel()

        with self.assertRaises(AttributeError):
            x.createFromTemplate(None, ['foo'])
        ByID.assert_called_once_with('foo')

    @mock.patch.object(create_from_template_app, "ClassRegistry")
    @mock.patch.object(create_from_template_app, "ByID")
    def test_createFromTemplate(self, ByID, ClassRegistry):
        obj = MagicMock(
            __class__=MagicMock()
        )
        x = create_from_template_app.WFTemplateCreateModel()
        ByID.return_value = obj
        cls = MagicMock(
            __class__=MagicMock()
        )
        ClassRegistry.return_value.findByClassname.return_value = cls
        request = mock.Mock()
        request.json = {
            "template_id": "foo",
            "classname": "foo_bar",
            "ahwf_content": ["OID_1"],
            "rest_key": "foo@bar",
        }
        with mock.patch('cs.workflow.process_template.content_in_whitelist', return_value=True) as \
                mocked_content_in_whitelist:
            x.createFromTemplate(request)
        ByID.assert_called_with('OID_1')
        mocked_content_in_whitelist.assert_called_once_with('OID_1', False)
