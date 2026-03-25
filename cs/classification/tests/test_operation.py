# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
# Version:  $Id$

import copy
import json
import logging

from cdb.objects.operations import operation
from cdb import constants
from cs import documents  # @UnresolvedImport

from cs.classification import api, ClassificationConstants
from cs.classification.operation import _multiple_edit_classification, \
    ClassificationOperation, _multiple_edit_classification_pre_mask

from cs.classification.tests import utils

LOG = logging.getLogger(__name__)


class TestOperationContext():

    class Parent():

        def __init__(self, cdb_object_id):
            self.cdb_object_id = cdb_object_id

    class SysArgs():

        def __init__(self, classification_web_ctrl):
            classification_web_ctrl["values"] = classification_web_ctrl["properties"]
            self.classification_web_ctrl = json.dumps(classification_web_ctrl)

    def __init__(self, cdb_object_id, classification_web_ctrl, relationship_name=""):
        self.classname = "document"
        self.elink_attr = ""
        self.elink_url = ""
        self.operation_id = ""
        self.parent = self.Parent(cdb_object_id)
        self.relationship_name = relationship_name
        self.sys_args = self.SysArgs(classification_web_ctrl)
        self.uses_webui = False

    def set_elink_url(self, attr_name, url):
        self.elink_attr = attr_name
        self.elink_url = url

    def url(self, url):
        self.operation_id = url.split("=")[-1]


class TestOperation(utils.ClassificationTestCase):

    def setUp(self):
        super(TestOperation, self).setUp()

    def test_operation(self):
        doc_1 = self.create_document("test doc 1")
        doc_2 = self.create_document("test doc 1")
        doc_3 = self.create_document("test doc 1")
        docs = [doc_1, doc_2, doc_3]
        doc_ids = [doc_1.cdb_object_id, doc_2.cdb_object_id, doc_3.cdb_object_id]

        assigned_classes = ["TEST_CLASS_BLOCK_PROPERTIES_MULTIPLE_UPDATE"]
        prop_code = "TEST_CLASS_BLOCK_PROPERTIES_MULTIPLE_UPDATE_TEST_PROP_BLOCK_NESTED_SINGLE"
        prop_code_sub_block_multiple = "TEST_PROP_BLOCK_MULTIVALUE"
        prop_code_sub_block_single = "TEST_PROP_BLOCK_SINGLE"
        prop_code_text = "TEST_PROP_TEXT"

        data = api.get_new_classification(assigned_classes, with_defaults=False)
        data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_text][0][ClassificationConstants.VALUE] = "test text level 1"
        data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block_multiple][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_text][0][ClassificationConstants.VALUE] = "test text level 2 multiple"
        data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block_single][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_text][0][ClassificationConstants.VALUE] = "test text level 2 single"
        data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block_single][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_sub_block_multiple][0][ClassificationConstants.VALUE][ClassificationConstants.BLOCK_CHILD_PROPS][prop_code_text][0][ClassificationConstants.VALUE] = "test text level 3 multiple"

        # inital classification should work without errors and warnings ...
        ctx = TestOperationContext('', data)
        _multiple_edit_classification(docs, ctx)

        operation = ClassificationOperation.ByKeys(cdb_object_id=ctx.operation_id)
        self.assertIsNotNone(operation)
        self.assertEqual(3, operation.exec_state)
        self.assertEqual(3, operation.successes)
        self.assertEqual(0, operation.warnings)
        self.assertEqual(0, operation.failures)

        results = []
        for result in operation.Results:
            results.append(result)
            self.assertEqual(3, result.exec_state)
            self.assertIn(result.ref_object_id, doc_ids)

        ctx = TestOperationContext(operation.cdb_object_id, data, "cs_classification_op2result")
        _multiple_edit_classification_pre_mask(results, ctx)
        self.assertEqual("cdb::argument.classification_web_ctrl", ctx.elink_attr)
        self.assertEqual(
            "/byname/update_classification/cs_classification_operation?operation_id={}".format(
                operation.cdb_object_id
            ),
            ctx.elink_url
        )

        # updating classification should lead to warnings ...
        _multiple_edit_classification(results, ctx)

        operation = ClassificationOperation.ByKeys(cdb_object_id=ctx.operation_id)
        self.assertIsNotNone(operation)
        self.assertEqual(2, operation.exec_state)
        self.assertEqual(0, operation.successes)
        self.assertEqual(3, operation.warnings)
        self.assertEqual(0, operation.failures)

        results = []
        for result in operation.Results:
            results.append(result)
            self.assertEqual(2, result.exec_state)
            self.assertIn(result.ref_object_id, doc_ids)

        # updating classification should lead to mandatory errors ...
        assigned_classes = ["COMPUTER"]
        data = api.get_new_classification(assigned_classes, with_defaults=False)

        ctx = TestOperationContext(operation.cdb_object_id, data, "cs_classification_op2result")
        _multiple_edit_classification(results, ctx)

        operation = ClassificationOperation.ByKeys(cdb_object_id=ctx.operation_id)
        self.assertIsNotNone(operation)
        self.assertEqual(1, operation.exec_state)
        self.assertEqual(0, operation.successes)
        self.assertEqual(0, operation.warnings)
        self.assertEqual(3, operation.failures)

        results = []
        for result in operation.Results:
            results.append(result)
            self.assertEqual(1, result.exec_state)
            self.assertIn(result.ref_object_id, doc_ids)

    def test_pattern_validation(self):
        doc_1 = self.create_document("test doc 1")
        doc_2 = self.create_document("test doc 1")
        doc_3 = self.create_document("test doc 1")
        docs = [doc_1, doc_2, doc_3]
        doc_ids = [doc_1.cdb_object_id, doc_2.cdb_object_id, doc_3.cdb_object_id]

        assigned_classes = ["TEST_PATTERN_CLASS"]
        prop_code = "TEST_PATTERN_CLASS_TEST_PATTERN_PROP"

        data = api.get_new_classification(assigned_classes, with_defaults=False)
        data[ClassificationConstants.PROPERTIES][prop_code][0][ClassificationConstants.VALUE] = "test text"

        ctx = TestOperationContext('', data)
        _multiple_edit_classification(docs, ctx)

        operation = ClassificationOperation.ByKeys(cdb_object_id=ctx.operation_id)
        self.assertIsNotNone(operation)
        self.assertEqual(1, operation.exec_state)
        self.assertEqual(0, operation.successes)
        self.assertEqual(0, operation.warnings)
        self.assertEqual(3, operation.failures)

        for result in operation.Results:
            self.assertEqual(1, result.exec_state)
            self.assertEqual(
                "Merkmalwerte stimmen nicht mit dem Format der Schablone überein.", result.message_de
            )
            self.assertIn(result.ref_object_id, doc_ids)

    def test_identifying_block_prop_validation(self):

        def create_docs():
            doc_operating = self.create_document("test doc 1")
            doc_storage = self.create_document("test doc 1")
            doc_no_classification = self.create_document("test doc 1")
            docs = [doc_operating, doc_storage, doc_no_classification]

            data = api.get_new_classification(assigned_classes, with_defaults=True)
            data["properties"]["TEST_CLASS_BLOCK_IDENTIFYING_PROPERTIES_TEST_PROP_BLOCK_IDENTIFYING_TEXT"][0][ClassificationConstants.VALUE]["child_props"]["TEST_PROP_IDENTIFYING_TEXT"][0]["value"] = "Text 1"
            api.update_classification(doc_operating, data)

            data["properties"]["TEST_CLASS_BLOCK_IDENTIFYING_PROPERTIES_TEST_PROP_BLOCK_IDENTIFYING_TEXT"][0][ClassificationConstants.VALUE]["child_props"]["TEST_PROP_IDENTIFYING_TEXT"][0]["value"] = "Text 2"
            api.update_classification(doc_storage, data)

            return docs

        assigned_classes = ["TEST_CLASS_BLOCK_IDENTIFYING_PROPERTIES"]

        # set/update min temp for all
        docs = create_docs()
        update_data = api.get_new_classification(assigned_classes, create_all_blocks=False, with_defaults=False)
        update_data["properties"]["TEST_CLASS_BLOCK_IDENTIFYING_PROPERTIES_TEST_PROP_BLOCK_IDENTIFYING_TEXT"][0]["value"]["child_props"]["TEST_PROP_IDENTIFYING_TEXT"][0]["value"] = "Text 1"
        update_data["properties"]["TEST_CLASS_BLOCK_IDENTIFYING_PROPERTIES_TEST_PROP_BLOCK_IDENTIFYING_TEXT"][0]["value"]["child_props"]["TEST_PROP_INT"][0]["value"] = 4711

        ctx = TestOperationContext('', update_data)
        _multiple_edit_classification(docs, ctx)

        operation = ClassificationOperation.ByKeys(cdb_object_id=ctx.operation_id)
        self.assertIsNotNone(operation)
        self.assertEquals(3, operation.exec_state)
        self.assertEquals(3, operation.successes)
        self.assertEquals(0, operation.warnings)
        self.assertEquals(0, operation.failures)

        for doc in docs:
            data = api.get_classification(doc)
            for child_props in data["properties"]["TEST_CLASS_BLOCK_IDENTIFYING_PROPERTIES_TEST_PROP_BLOCK_IDENTIFYING_TEXT"]:
                if "Text 1" == child_props["value"]["child_props"]["TEST_PROP_IDENTIFYING_TEXT"][0]["value"]:
                    self.assertEqual(
                        4711,
                        child_props["value"]["child_props"]["TEST_PROP_INT"][0]["value"]
                    )

        # duplicate temp type, second value wins
        docs = create_docs()
        update_data = api.get_new_classification(assigned_classes, create_all_blocks=False, with_defaults=False)
        update_data["properties"]["TEST_CLASS_BLOCK_IDENTIFYING_PROPERTIES_TEST_PROP_BLOCK_IDENTIFYING_TEXT"][0]["value"]["child_props"]["TEST_PROP_IDENTIFYING_TEXT"][0]["value"] = "Text 1"
        update_data["properties"]["TEST_CLASS_BLOCK_IDENTIFYING_PROPERTIES_TEST_PROP_BLOCK_IDENTIFYING_TEXT"][0]["value"]["child_props"]["TEST_PROP_INT"][0]["value"] = 4711

        update_data["properties"]["TEST_CLASS_BLOCK_IDENTIFYING_PROPERTIES_TEST_PROP_BLOCK_IDENTIFYING_TEXT"].append(
            copy.deepcopy(
                update_data["properties"]["TEST_CLASS_BLOCK_IDENTIFYING_PROPERTIES_TEST_PROP_BLOCK_IDENTIFYING_TEXT"][0]
            )
        )
        update_data["properties"]["TEST_CLASS_BLOCK_IDENTIFYING_PROPERTIES_TEST_PROP_BLOCK_IDENTIFYING_TEXT"][1]["value"]["child_props"]["TEST_PROP_INT"][0]["value"] = 444

        ctx = TestOperationContext('', update_data)
        _multiple_edit_classification(docs, ctx)

        operation = ClassificationOperation.ByKeys(cdb_object_id=ctx.operation_id)
        self.assertIsNotNone(operation)
        self.assertEquals(3, operation.exec_state)
        self.assertEquals(3, operation.successes)
        self.assertEquals(0, operation.warnings)
        self.assertEquals(0, operation.failures)

        for doc in docs:
            data = api.get_classification(doc)
            for child_props in data["properties"]["TEST_CLASS_BLOCK_IDENTIFYING_PROPERTIES_TEST_PROP_BLOCK_IDENTIFYING_TEXT"]:
                if "Text 1" == child_props["value"]["child_props"]["TEST_PROP_IDENTIFYING_TEXT"][0]["value"]:
                    self.assertEqual(
                        444,
                        child_props["value"]["child_props"]["TEST_PROP_INT"][0]["value"]
                    )
