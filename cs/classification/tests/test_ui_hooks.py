# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
# Version:  $Id$

from datetime import datetime
from webtest import TestApp as Client

from cdb import auth, testcase
from cs.classification.tests import utils

import logging

from cdb import sig
from cs.platform.web.root import Root
from cs.documents import Document  # @UnresolvedImport

LOG = logging.getLogger(__name__)


@sig.connect(Document, "classification", "new_class")
@sig.connect(Document, "classification", "new_value")
def add_user_and_date(class_code, metadata, values):
    if 'TEST_CLASS_UI_HOOK_TEST_PROP_COMMENT' in values:
        comment_child_props = values["TEST_CLASS_UI_HOOK_TEST_PROP_COMMENT"][0]["value"]["child_props"]
        comment_child_props["TEST_PROP_DATE"][0]["value"] = datetime.utcnow().isoformat()
        comment_child_props["TEST_PROP_TEXT"][0]["value"] = auth.get_name()


class TestUiHooks(utils.ClassificationTestCase):

    def setUp(self):
        super(TestUiHooks, self).setUp()
        self.client = Client(Root())
        self.document_number = "CLASS000059"
        self.document = Document.ByKeys(z_nummer=self.document_number, z_index="")

    def test_ui_hook_for_adding_class_in_edit_mode(self):
        """  Test ci hook in edit mode. """

        with testcase.error_logging_disabled():
            url = "/internal/classification/class/TEST_CLASS_UI_HOOK"
            json_data = {
                "assignedClassCodes": [],
                "cdb_object_id": self.document.cdb_object_id,
                "dataDictionaryClassName": self.document.GetClassname(),
                "searchMode": False,
                "withDefaults": True,
                "activePropsOnly": True
            }

            result = self.client.post_json(url, json_data)
            assert result
            classification_data = result.json
            self.assertIsNotNone(
                auth.get_name(),
                classification_data["values"]["TEST_CLASS_UI_HOOK_TEST_PROP_COMMENT"][0]["value"]["child_props"]["TEST_PROP_DATE"][0]["value"]
            )
            self.assertEqual(
                auth.get_name(),
                classification_data["values"]["TEST_CLASS_UI_HOOK_TEST_PROP_COMMENT"][0]["value"]["child_props"]["TEST_PROP_TEXT"][0]["value"]
            )

            url = '/internal/classification/property_value'
            json_data = {
                "assignedClassCodes": [],
                "cdb_object_id": self.document.cdb_object_id,
                "clazzCode": "TEST_CLASS_UI_HOOK",
                "dataDictionaryClassName": self.document.GetClassname(),
                "propertyValue": classification_data["values"]["TEST_CLASS_UI_HOOK_TEST_PROP_COMMENT"][0],
                "searchMode": False
            }
            result = self.client.post_json(url, json_data)
            assert result
            classification_data = result.json
            self.assertIsNotNone(
                auth.get_name(),
                classification_data["TEST_CLASS_UI_HOOK_TEST_PROP_COMMENT"][0]["value"]["child_props"]["TEST_PROP_DATE"][0]["value"]
            )
            self.assertEqual(
                auth.get_name(),
                classification_data["TEST_CLASS_UI_HOOK_TEST_PROP_COMMENT"][0]["value"]["child_props"]["TEST_PROP_TEXT"][0]["value"]
            )

    def test_ui_hook_for_adding_class_in_search_mode(self):
        """  Test ci hook in search mode. """

        with testcase.error_logging_disabled():
            url = "/internal/classification/class/TEST_CLASS_UI_HOOK"
            json_data = {
                "assignedClassCodes": [],
                "cdb_object_id": self.document.cdb_object_id,
                "dataDictionaryClassName": self.document.GetClassname(),
                "searchMode": True,
                "withDefaults": False,
                "activePropsOnly": False
            }
            result = self.client.post_json(url, json_data)
            assert result
            classification_data = result.json
            self.assertIsNone(
                classification_data["values"]["TEST_CLASS_UI_HOOK_TEST_PROP_COMMENT"][0]["value"]["child_props"]["TEST_PROP_DATE"][0]["value"]
            )
            self.assertIsNone(
                classification_data["values"]["TEST_CLASS_UI_HOOK_TEST_PROP_COMMENT"][0]["value"]["child_props"]["TEST_PROP_TEXT"][0]["value"]
            )
            url = '/internal/classification/property_value'
            json_data = {
                "assignedClassCodes": [],
                "cdb_object_id": self.document.cdb_object_id,
                "clazzCode": "TEST_CLASS_UI_HOOK",
                "dataDictionaryClassName": self.document.GetClassname(),
                "propertyValue": classification_data["values"]["TEST_CLASS_UI_HOOK_TEST_PROP_COMMENT"][0],
                "searchMode": True
            }
            result = self.client.post_json(url, json_data)
            assert result
            classification_data = result.json
            self.assertIsNone(
                classification_data["TEST_CLASS_UI_HOOK_TEST_PROP_COMMENT"][0]["value"]["child_props"]["TEST_PROP_DATE"][0]["value"]
            )
            self.assertIsNone(
                classification_data["TEST_CLASS_UI_HOOK_TEST_PROP_COMMENT"][0]["value"]["child_props"]["TEST_PROP_TEXT"][0]["value"]
            )
