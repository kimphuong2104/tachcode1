# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module util

This module contains test methods for the utility functions.
"""

import copy
import datetime

from webtest import TestApp as Client


from cdb import constants, cdbuuid, sig
from cdb.objects.operations import operation, system_args
from cs.platform.web.root import Root
from cs.documents import Document
from cs.classification import api, ObjectPropertyValue, ObjectClassification, solr, tools
from cs.classification.tests import utils


class TestConnects(utils.ClassificationTestCase):

    def setUp(self):
        super(TestConnects, self).setUp()

    def _create_document(self, create_data=None):
        if not create_data:
            class_codes = ["TEST_CLASS_ALL_PROPERTY_TYPES"]
            create_data = api.get_new_classification(class_codes)
            create_data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"] = "testtext"
        doc = operation(
            constants.kOperationNew,
            Document,
            system_args(
                classification_web_ctrl=tools.preset_mask_data(create_data)
            ),
            titel="test doc",
            z_categ1="142",
            z_categ2="153",
        )
        return doc

    def _create_classified_object(
        self, class_codes, prop_codes=None, release_document=False, release_classification=False
    ):
        doc = operation(
            constants.kOperationNew,
            Document,
            titel="test doc",
            z_categ1="142",
            z_categ2="153"
        )
        classification_data = api.get_new_classification(class_codes)
        if prop_codes:
            classification_data["properties"].update(api.create_additional_props(prop_codes)["properties"])

        self._set_property_values(doc, classification_data["properties"])
        api.update_classification(doc, classification_data)

        if release_document:
            doc.ChangeState(200)

        if release_classification:
            object_classification = ObjectClassification.ByKeys(
                ref_object_id=doc.cdb_object_id, class_code="TEST_CLASS_RIGHTS_OLC"
            )
            object_classification.ChangeState(200)

        return doc

    def _check_property_values(self, doc, properties):
        for prop_code in list(properties.keys()):
            prop_value = properties[prop_code][0]
            prop_type = prop_value["property_type"]
            if "block" == prop_type:
                self._check_property_values(doc, prop_value["value"]["child_props"])
            elif "float" == prop_type:
                self.assertAlmostEqual(123.456, prop_value["value"]["float_value"])
            elif "float_range" == prop_type:
                self.assertAlmostEqual(123.456, prop_value["value"]["min"]["float_value"])
                self.assertAlmostEqual(456.789, prop_value["value"]["max"]["float_value"])
            elif "boolean" == prop_type:
                self.assertEqual(True, prop_value["value"])
            elif "date" == prop_type:
                self.assertEqual(datetime.datetime(2002, 3, 11, 0, 0), prop_value["value"])
            elif "integer" == prop_type:
                self.assertEqual(123, prop_value["value"])
            elif "multilang" == prop_type:
                self.assertEqual(prop_code + "_de", prop_value["value"]["de"]["text_value"])
                self.assertEqual(prop_code + "_en", prop_value["value"]["en"]["text_value"])
            elif "objectref" == prop_type:
                self.assertEqual(doc.cdb_object_id, prop_value["value"])
            elif "text" == prop_type:
                self.assertEqual(prop_code, prop_value["value"])

    def _set_property_values(self, doc, properties):
        for prop_code in list(properties.keys()):
            prop_value = properties[prop_code][0]
            prop_type = prop_value["property_type"]
            if "block" == prop_type:
                self._set_property_values(doc, prop_value["value"]["child_props"])
            elif "float" == prop_type:
                prop_value["value"]["float_value"] = 123.456
            elif "float_range" == prop_type:
                prop_value["value"]["min"]["float_value"] = 123.456
                prop_value["value"]["max"]["float_value"] = 456.789
            elif "boolean" == prop_type:
                prop_value["value"] = True
            elif "date" == prop_type:
                prop_value["value"] = datetime.date(2002, 3, 11)
            elif "integer" == prop_type:
                prop_value["value"] = 123
            elif "multilang" == prop_type:
                prop_value["value"]["de"]["text_value"] = prop_code + "_de"
                prop_value["value"]["en"]["text_value"] = prop_code + "_en"
            elif "objectref" == prop_type:
                prop_value["value"] = doc.cdb_object_id
            elif "text" == prop_type:
                prop_value["value"] = prop_code

    def test_create(self):
        doc = self._create_document()
        data = api.get_classification(doc)
        self.assertListEqual(["TEST_CLASS_ALL_PROPERTY_TYPES"], data["assigned_classes"])
        self.assertEqual(
            "testtext",
            data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"]
        )

    def test_copy(self):

        doc_without_classification = self._create_document(create_data=api.get_new_classification([]))
        # copy document without classification
        doc_copy = operation(
            constants.kOperationCopy,
            doc_without_classification
        )
        data = api.get_classification(doc_copy)
        self.assertListEqual([], data["assigned_classes"])
        self.assertDictEqual({}, data["properties"])

        doc = self._create_document()
        # copy without classification
        doc_copy = operation(
            constants.kOperationCopy,
            doc,
            system_args(**{"cs.classification.prevent_copy": "1"})
        )
        data = api.get_classification(doc_copy)
        self.assertListEqual([], data["assigned_classes"])
        self.assertDictEqual({}, data["properties"])

        # copy without reindexing
        doc_copy = operation(
            constants.kOperationCopy,
            doc,
            system_args(**{"cs.classification.prevent_index_update": "1"})
        )
        data = api.get_classification(doc_copy)
        self.assertListEqual(["TEST_CLASS_ALL_PROPERTY_TYPES"], data["assigned_classes"])
        self.assertEqual(
            "testtext",
            data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"]
        )
        self.assertNotIn(doc_copy.cdb_object_id, api.search(data))
        solr.index_object(doc_copy)
        self.assertIn(doc_copy.cdb_object_id, api.search(data))

        # copy without classification change
        doc_copy = operation(
            constants.kOperationCopy,
            doc
        )
        data = api.get_classification(doc_copy)
        self.assertListEqual(["TEST_CLASS_ALL_PROPERTY_TYPES"], data["assigned_classes"])
        self.assertEqual(
            "testtext",
            data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"]
        )

        data = api.get_classification(doc)
        data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"] = "updated testtext"
        data = api.rebuild_classification(data, ["TEST_CLASS_ARTICLE"])
        data["properties"]["TEST_CLASS_ARTICLE_TEST_PROP_ITEM_NUMBER"][0]["value"] = "123"

        # copy with classification change
        doc_copy = operation(
            constants.kOperationCopy,
            doc,
            system_args(
                classification_web_ctrl=tools.preset_mask_data(data)
            )
        )
        data = api.get_classification(doc_copy)
        self.assertSetEqual(
            set(["TEST_CLASS_ALL_PROPERTY_TYPES", "TEST_CLASS_ARTICLE"]),
            set(data["assigned_classes"])
        )
        self.assertEqual(
            "updated testtext",
            data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"]
        )
        self.assertEqual(
            "123",
            data["properties"]["TEST_CLASS_ARTICLE_TEST_PROP_ITEM_NUMBER"][0]["value"]
        )

    def test_copy_with_flag_and_rights_batch(self):
        doc_src = Document.KeywordQuery(z_nummer="CLASS000007")[0]
        doc_copy = operation(
            constants.kOperationCopy,
            doc_src,
            z_nummer=cdbuuid.create_uuid()[:19],
            z_index="",
            ursprungs_z=""
        )
        data = api.get_classification(doc_copy)
        self.assertSetEqual(
            set(['TEST_CLASS_COPY_YES', 'TEST_CLASS_RIGHTS_OLC', 'TEST_SUB_CLASS_RESTRICTED']),
            set(data["assigned_classes"])
        )
        self.assertSetEqual(
            set([
                'TEST_CLASS_RIGHTS_OLC_TEST_PROP_TEXT',
                'TEST_CLASS_RIGHTS_BASE_TEST_PROP_TEXT_MANDATORY',
                'TEST_CLASS_COPY_BASE_TEST_PROP_TEXT',
                'TEST_CLASS_COPY_YES_TEST_PROP_STORAGE_TYPE',
                'TEST_PROP_TEXT',
                'TEST_PROP_RESTRICTED_TEXT',
                'TEST_SUB_CLASS_RESTRICTED_TEXT_EDITABLE_ENUM',
                'TEST_BASE_CLASS_RESTRICTED_TEXT_EDITABLE',
                'TEST_BASE_CLASS_RESTRICTED_TEST_PROP_RESTRICTED_TEXT',
                'TEST_SUB_CLASS_RESTRICTED_TEST_PROP_RESTRICTED_INT',
            ]),
            set(data["properties"].keys())
        )
        self.assertEqual(
            'OLC Text',
            data["properties"]["TEST_CLASS_RIGHTS_OLC_TEST_PROP_TEXT"][0]["value"]
        )
        self.assertEqual(
            '4711',
            data["properties"]["TEST_CLASS_RIGHTS_BASE_TEST_PROP_TEXT_MANDATORY"][0]["value"]
        )
        self.assertEqual(
            'Testtext',
            data["properties"]["TEST_CLASS_COPY_BASE_TEST_PROP_TEXT"][0]["value"]
        )
        self.assertEqual(
            'Indoor',
            data["properties"]["TEST_CLASS_COPY_YES_TEST_PROP_STORAGE_TYPE"][0]["value"]
        )
        self.assertEqual(
            'Test Text',
            data["properties"]["TEST_PROP_TEXT"][0]["value"]
        )
        self.assertEqual(
            'Test Restricted Text',
            data["properties"]["TEST_PROP_RESTRICTED_TEXT"][0]["value"]
        )
        self.assertEqual(
            'text restricted',
            data["properties"]["TEST_SUB_CLASS_RESTRICTED_TEXT_EDITABLE_ENUM"][0]["value"]
        )
        self.assertEqual(
            'text restricted base',
            data["properties"]["TEST_BASE_CLASS_RESTRICTED_TEXT_EDITABLE"][0]["value"]
        )
        self.assertEqual(
            None,
            data["properties"]["TEST_BASE_CLASS_RESTRICTED_TEST_PROP_RESTRICTED_TEXT"][0]["value"]
        )
        self.assertEqual(
            456,
            data["properties"]["TEST_SUB_CLASS_RESTRICTED_TEST_PROP_RESTRICTED_INT"][0]["value"]
        )

    def test_copy_with_custom_object_classification_batch(self):
        # overwrite copy_for_ref_object method for test
        class MockObjectClassification(ObjectClassification): #pylint: disable=W0612
            def copy_for_ref_object(self, ref_object, ctx=None):
                copy_args = {
                    "ref_object_id": ref_object.cdb_object_id,
                    "not_deletable": 1
                }
                return self.Copy(**copy_args)

        doc_src = Document.KeywordQuery(z_nummer="CLASS000007")[0]
        doc_copy = operation(
            constants.kOperationCopy,
            doc_src,
            z_nummer=cdbuuid.create_uuid()[:19],
            z_index="",
            ursprungs_z=""
        )
        data = api.get_classification(doc_copy)
        self.assertSetEqual(
            set(["TEST_CLASS_COPY_YES", "TEST_CLASS_RIGHTS_OLC", "TEST_SUB_CLASS_RESTRICTED"]),
            set(data["assigned_classes"])
        )

        for object_classification in ObjectClassification.KeywordQuery(ref_object_id=doc_copy.cdb_object_id):
            self.assertEquals(1, object_classification.not_deletable)

    def test_copy_with_flag_and_rights_interactive(self):

        doc_src = Document.KeywordQuery(z_nummer="CLASS000007")[0]

        self.client = Client(Root())
        url = '/internal/classification/' + doc_src.cdb_object_id + '?for_create=true'
        result = self.client.get(url, status=200)
        classification_data = result.json['system:classification']
        classification_data["values"]["TEST_CLASS_COPY_BASE_TEST_PROP_TEXT"][0]["value"] = 'Testtext changed for copy'

        doc_copy = operation(
            constants.kOperationCopy,
            doc_src,
            system_args(
                classification_web_ctrl=tools.preset_mask_data({
                    "assigned_classes": tools.get_assigned_class_codes(classification_data),
                    "properties": classification_data["values"]
                })
            ),
            z_nummer=cdbuuid.create_uuid()[:19],
            z_index="",
            ursprungs_z=""
        )
        data_copy = api.get_classification(doc_copy)

        self.assertSetEqual(
            set(['TEST_CLASS_COPY_YES', 'TEST_CLASS_RIGHTS_OLC', 'TEST_SUB_CLASS_RESTRICTED']),
            set(data_copy["assigned_classes"])
        )
        self.assertSetEqual(
            set([
                'TEST_CLASS_RIGHTS_OLC_TEST_PROP_TEXT',
                'TEST_CLASS_RIGHTS_BASE_TEST_PROP_TEXT_MANDATORY',
                'TEST_CLASS_COPY_BASE_TEST_PROP_TEXT',
                'TEST_CLASS_COPY_YES_TEST_PROP_STORAGE_TYPE',
                'TEST_PROP_TEXT',
                'TEST_PROP_RESTRICTED_TEXT',
                'TEST_SUB_CLASS_RESTRICTED_TEXT_EDITABLE_ENUM',
                'TEST_BASE_CLASS_RESTRICTED_TEXT_EDITABLE',
                'TEST_BASE_CLASS_RESTRICTED_TEST_PROP_RESTRICTED_TEXT',
                'TEST_SUB_CLASS_RESTRICTED_TEST_PROP_RESTRICTED_INT',
            ]),
            set(data_copy["properties"].keys())
        )
        self.assertEqual(
            'OLC Text',
            data_copy["properties"]["TEST_CLASS_RIGHTS_OLC_TEST_PROP_TEXT"][0]["value"]
        )
        self.assertEqual(
            '4711',
            data_copy["properties"]["TEST_CLASS_RIGHTS_BASE_TEST_PROP_TEXT_MANDATORY"][0]["value"]
        )
        self.assertEqual(
            'Testtext changed for copy',
            data_copy["properties"]["TEST_CLASS_COPY_BASE_TEST_PROP_TEXT"][0]["value"]
        )
        self.assertEqual(
            'Indoor',
            data_copy["properties"]["TEST_CLASS_COPY_YES_TEST_PROP_STORAGE_TYPE"][0]["value"]
        )
        self.assertEqual(
            'Test Text',
            data_copy["properties"]["TEST_PROP_TEXT"][0]["value"]
        )
        self.assertEqual(
            'Test Restricted Text',
            data_copy["properties"]["TEST_PROP_RESTRICTED_TEXT"][0]["value"]
        )
        self.assertEqual(
            'text restricted',
            data_copy["properties"]["TEST_SUB_CLASS_RESTRICTED_TEXT_EDITABLE_ENUM"][0]["value"]
        )
        self.assertEqual(
            'text restricted base',
            data_copy["properties"]["TEST_BASE_CLASS_RESTRICTED_TEXT_EDITABLE"][0]["value"]
        )
        self.assertEqual(
            None,
            data_copy["properties"]["TEST_BASE_CLASS_RESTRICTED_TEST_PROP_RESTRICTED_TEXT"][0]["value"]
        )
        self.assertEqual(
            456,
            data_copy["properties"]["TEST_SUB_CLASS_RESTRICTED_TEST_PROP_RESTRICTED_INT"][0]["value"]
        )

    def test_copy_with_hidden_classification(self):
        class_codes = [
            "TEST_SUB_CLASS_HIDDEN",
            "TEST_SUB_CLASS_NOT_HIDDEN",
            "TEST_CLASS_ALL_PROPERTY_TYPES",
            "TEST_CLASS_COPY_NO",
            "TEST_CLASS_COPY_YES",
            "TEST_CLASS_RIGHTS_OLC",
            "TEST_SUB_CLASS_NOT_RESTRICTED",
            "TEST_SUB_CLASS_RESTRICTED",
        ]
        prop_codes = [
            "TEST_PROP_TEXT",
            "TEST_PROP_HIDDEN_TEXT",
            "TEST_PROP_RESTRICTED_TEXT"
        ]
        src_doc = self._create_classified_object(class_codes, prop_codes=prop_codes)

        doc_copy = operation(
            constants.kOperationCopy,
            src_doc,
            z_nummer=cdbuuid.create_uuid()[:19],
            z_index="",
            ursprungs_z=""
        )
        data_copy = api.get_classification(doc_copy, check_rights=False)
        self.assertSetEqual(
            set([
                "TEST_CLASS_ALL_PROPERTY_TYPES",
                "TEST_CLASS_COPY_YES",
                "TEST_CLASS_RIGHTS_OLC",
                "TEST_SUB_CLASS_NOT_RESTRICTED",
                "TEST_SUB_CLASS_RESTRICTED"
            ]),
            set(data_copy["assigned_classes"])
        )
        for prop_code in prop_codes:
            if "HIDDEN" in prop_code:
                self.assertNotIn(prop_code, data_copy["properties"])
            else:
                self.assertIn(prop_code, data_copy["properties"])
        self._check_property_values(src_doc, data_copy["properties"])

    def test_copy_with_hidden_valid_classification(self):
        doc_src = Document.KeywordQuery(z_nummer="CLASS000014")[0]
        doc_copy = operation(
            constants.kOperationCopy,
            doc_src,
            z_nummer=cdbuuid.create_uuid()[:19],
            z_index="",
            ursprungs_z=""
        )
        excpected_assigned_classes = ["TEST_CLASS_CONSTRAINTS_USING_PROPERTIES_FROM_HIDDEN_CLASSES"]
        data = api.get_new_classification(excpected_assigned_classes)
        data_copy = api.get_classification(doc_copy)
        self.assertListEqual(excpected_assigned_classes,data_copy["assigned_classes"])
        self.assertSetEqual(set(data["properties"].keys()), set(data_copy["properties"].keys()))


    def test_copy_with_hidden_invalid_classification(self):
        doc_src = Document.KeywordQuery(z_nummer="CLASS000013")[0]
        doc_copy = operation(
            constants.kOperationCopy,
            doc_src,
            z_nummer=cdbuuid.create_uuid()[:19],
            z_index="",
            ursprungs_z=""
        )
        excpected_assigned_classes = ["TEST_CLASS_CONSTRAINTS_USING_PROPERTIES_FROM_HIDDEN_CLASSES"]
        data = api.get_new_classification(excpected_assigned_classes)
        data_copy = api.get_classification(doc_copy)
        self.assertListEqual(excpected_assigned_classes, data_copy["assigned_classes"])
        self.assertSetEqual(set(data["properties"].keys()), set(data_copy["properties"].keys()))

    def test_delete(self):
        doc = self._create_document()
        ref_object_id = doc.cdb_object_id
        obj_classification = ObjectClassification.KeywordQuery(ref_object_id=ref_object_id)
        if not obj_classification:
            self.fail("ObjectClassification expected")
        eav = ObjectPropertyValue.KeywordQuery(ref_object_id=ref_object_id)
        if not eav:
            self.fail("ObjectPropertyValue expected")
        doc_copy = operation(
            constants.kOperationDelete,
            doc
        )
        obj_classification = ObjectClassification.KeywordQuery(ref_object_id=ref_object_id)
        if obj_classification:
            self.fail("No ObjectClassification expected")
        eav = ObjectPropertyValue.KeywordQuery(ref_object_id=ref_object_id)
        if eav:
            self.fail("No ObjectPropertyValue expected")

    def test_index(self):
        doc = self._create_document()
        doc_index = operation(
            constants.kOperationIndex,
            doc
        )
        data = api.get_classification(doc_index)
        self.assertListEqual(["TEST_CLASS_ALL_PROPERTY_TYPES"], data["assigned_classes"])
        self.assertEqual(
            "testtext",
            data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"]
        )

    def test_index_post(self):
        try:
            @sig.connect(Document, "index", "post")
            def index_post(obj, ctx):
                if obj.z_nummer == doc.z_nummer:
                    doc_2_index = operation(
                        constants.kOperationIndex,
                        doc_2
                    )
                    data = api.get_classification(doc_2_index)
                    self.assertListEqual(["TEST_CLASS_ALL_PROPERTY_TYPES"], data["assigned_classes"])
                    self.assertEqual(
                        "testtext",
                        data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"]
                    )

            doc = self._create_document()
            doc_2 = self._create_document()

            doc_index = operation(
                constants.kOperationIndex,
                doc
            )
            data = api.get_classification(doc_index)
            self.assertListEqual(["TEST_CLASS_ALL_PROPERTY_TYPES"], data["assigned_classes"])
            self.assertEqual(
                "testtext",
                data["properties"]["TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT"][0]["value"]
            )
        finally:
            sig.disconnect(index_post)

    def test_check_classification(self):
        def create(create_data, should_fail):
            try:
                self._create_document(create_data)
                if should_fail:
                    self.fail("Exception from check_classification expected.")
            except Exception as ex: # pylint: disable=W0703
                if not should_fail:
                    self.fail("No exception from check_classification expected.")

        class_codes = ["TEST_CLASS_FOR_CHECKS"]
        create_data = api.get_new_classification(class_codes)

        # no properties set
        create(create_data, True)

        # with mandatory properties
        create_data["properties"]["TEST_CLASS_FOR_CHECKS_TEST_PROP_TEXT_MANDATORY"][0]["value"] = "testtext"
        block_temperature = create_data["properties"]["TEST_CLASS_FOR_CHECKS_TEST_PROP_BLOCK_TEMPERATURE"][0]["value"]["child_props"]
        block_temperature["TEST_PROP_TEMPERATURE_TYPE"][0]["value"]["de"]["text_value"] = "Lagertemperatur"
        block_temperature["TEST_PROP_TEMPERATURE_TYPE"][0]["value"]["en"]["text_value"] = "Storage Temperature"
        create(create_data, False)

        # pattern violation
        create_data["properties"]["TEST_CLASS_FOR_CHECKS_TEST_PATTERN_PROP"][0]["value"] = "testtext"
        create(create_data, True)

        # without pattern violation
        create_data["properties"]["TEST_CLASS_FOR_CHECKS_TEST_PATTERN_PROP"][0]["value"] = "a11a&b22b_c33c"
        create(create_data, False)

        # with rule violation
        create_data["properties"]["TEST_CLASS_FOR_CHECKS_TEST_PROP_BREITE_1"][0]["value"]["float_value"] = 1.2
        create(create_data, True)

        # with constraint violation
        create_data["properties"]["TEST_CLASS_FOR_CHECKS_TEST_PROP_BREITE"][0]["value"]["float_value"] = 1.2
        create(create_data, True)

        # without constraint violation
        create_data["properties"]["TEST_CLASS_FOR_CHECKS_TEST_PROP_BREITE"][0]["value"]["float_value"] = 1.1
        create(create_data, True)

        # with identifying property violation
        create_data["properties"]["TEST_CLASS_FOR_CHECKS_TEST_PROP_BLOCK_TEMPERATURE"].append(
            copy.deepcopy(create_data["properties"]["TEST_CLASS_FOR_CHECKS_TEST_PROP_BLOCK_TEMPERATURE"][0])
        )
        create(create_data, True)

        block_temperature = create_data["properties"]["TEST_CLASS_FOR_CHECKS_TEST_PROP_BLOCK_TEMPERATURE"][0]["value"]["child_props"]
        block_temperature["TEST_PROP_TEMPERATURE_TYPE"][0]["value"]["de"]["text_value"] = "Betriebstemperatur"
        block_temperature["TEST_PROP_TEMPERATURE_TYPE"][0]["value"]["en"]["text_value"] = "Operating Temperature"
        create(create_data, False)

        # with identifying property violation in nested block
        block_temperature = create_data["properties"]["TEST_CLASS_FOR_CHECKS_TEST_PROP_BLOCK_TEMPERATURES"][0]["value"]["child_props"]["TEST_PROP_BLOCK_TEMPERATURE_WITHOUT_CREATE"][0]["value"]["child_props"]
        block_temperature["TEST_PROP_TEMPERATURE_TYPE"][0]["value"]["de"]["text_value"] = "Lagertemperatur"
        block_temperature["TEST_PROP_TEMPERATURE_TYPE"][0]["value"]["en"]["text_value"] = "Storage Temperature"

        create_data["properties"]["TEST_CLASS_FOR_CHECKS_TEST_PROP_BLOCK_TEMPERATURES"][0]["value"]["child_props"]["TEST_PROP_BLOCK_TEMPERATURE_WITHOUT_CREATE"].append(
            copy.deepcopy(create_data["properties"]["TEST_CLASS_FOR_CHECKS_TEST_PROP_BLOCK_TEMPERATURES"][0]["value"]["child_props"]["TEST_PROP_BLOCK_TEMPERATURE_WITHOUT_CREATE"][0])
        )
        create(create_data, True)

        block_temperature = block_temperature = create_data["properties"]["TEST_CLASS_FOR_CHECKS_TEST_PROP_BLOCK_TEMPERATURES"][0]["value"]["child_props"]["TEST_PROP_BLOCK_TEMPERATURE_WITHOUT_CREATE"][0]["value"]["child_props"]
        block_temperature["TEST_PROP_TEMPERATURE_TYPE"][0]["value"]["de"]["text_value"] = "Betriebstemperatur"
        block_temperature["TEST_PROP_TEMPERATURE_TYPE"][0]["value"]["en"]["text_value"] = "Operating Temperature"
        create(create_data, False)
