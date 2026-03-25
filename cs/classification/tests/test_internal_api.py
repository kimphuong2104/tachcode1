# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
# Version:  $Id$

import copy
import datetime

from cdb import constants, testcase, ue
from cdb.objects.operations import operation

from cs.documents import Document

from cs.classification import api, ObjectClassification, tools
from cs.classification.classes import ClassificationClass
from cs.classification.classification_data import ClassificationData
from cs.classification.object_classification import ClassificationUpdater
from cs.classification.tests import utils


class TestInternalApi(utils.ClassificationTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestInternalApi, cls).setUpClass()
        testcase.require_service("cdb.uberserver.services.index.IndexService")

    def setUp(self):
        super(TestInternalApi, self).setUp()
        self.document_number = "CLASS000010"
        self.document = Document.ByKeys(z_nummer=self.document_number, z_index="")
        self.all_class_codes = [
            "TEST_SUB_CLASS_HIDDEN",
            "TEST_SUB_CLASS_NOT_HIDDEN",
            "TEST_CLASS_ALL_PROPERTY_TYPES",
            "TEST_CLASS_RIGHTS_OLC",
            "TEST_SUB_CLASS_NOT_RESTRICTED",
            "TEST_SUB_CLASS_RESTRICTED",
        ]

    def _create_mixed_classified_object(
        self, title, release_document=False, release_classification=False
    ):
        doc = operation(
            constants.kOperationNew,
            Document,
            titel=title,
            z_categ1="142",
            z_categ2="153"
        )
        self.assertIsNotNone(doc, 'document to classify could not be created!')
        classification_data = api.get_new_classification(self.all_class_codes)
        self.set_property_values(classification_data["properties"])
        api.update_classification(doc, classification_data)

        if release_document:
            doc.ChangeState(200)

        if release_classification:
            object_classification = ObjectClassification.ByKeys(
                ref_object_id=doc.cdb_object_id, class_code="TEST_CLASS_RIGHTS_OLC"
            )
            object_classification.ChangeState(200)

        return doc

    def _test_remove_classification_full_update_mode(self, class_code_to_delete):
        clazz = ClassificationClass.KeywordQuery(code=class_code_to_delete)[0]
        doc = self._create_mixed_classified_object(
            "Remove class full update mode: " + class_code_to_delete
        )
        all_classification_data = api.get_classification(doc, check_rights=False)
        self.check_property_values(all_classification_data["properties"])

        classification_data = api.get_classification(doc, check_rights=False)
        classification_data["assigned_classes"].remove(class_code_to_delete)

        expected_assigned_classes = set(self.all_class_codes) - set([class_code_to_delete])
        expected_classification_data_after_update = api.get_new_classification(expected_assigned_classes)
        property_codes_to_delete = set(classification_data["properties"].keys()) - \
                                   set(expected_classification_data_after_update["properties"].keys())
        for property_code in property_codes_to_delete:
            del classification_data["properties"][property_code]

        api.update_classification(doc, classification_data, full_update_mode=True)

        classification_data = api.get_classification(doc)
        self.assertNotIn(class_code_to_delete, classification_data["assigned_classes"])
        self.assertSetEqual(expected_assigned_classes, set(classification_data["assigned_classes"]))

        self.assertSetEqual(
            set(expected_classification_data_after_update["properties"].keys()),
            set(classification_data["properties"].keys())
        )


    def _test_remove_classification_partial_update_mode(self, class_code_to_delete):
        clazz = ClassificationClass.KeywordQuery(code=class_code_to_delete)[0]
        doc = self._create_mixed_classified_object(
            "Remove class partial update mode: " + class_code_to_delete
        )
        all_classification_data = api.get_classification(doc, check_rights=False)
        self.check_property_values(all_classification_data["properties"])

        classification_data = api.get_classification(doc, check_rights=True)
        classification_data["deleted_classes"] = [class_code_to_delete]
        api.update_classification(doc, classification_data, full_update_mode=False)

        classification_data = api.get_classification(doc)
        self.assertNotIn(class_code_to_delete, classification_data["assigned_classes"])
        expected_assigned_classes = set(self.all_class_codes) - set([class_code_to_delete])
        self.assertSetEqual(expected_assigned_classes, set(classification_data["assigned_classes"]))

        self.assertSetEqual(
            set(api.get_new_classification(
                classification_data["assigned_classes"]
            )["properties"].keys()),
            set(classification_data["properties"].keys())
        )


    def test_access_rights(self):
        doc = Document.ByKeys(z_nummer="CLASS000011", z_index="")
        self.assertIsNotNone(doc)

        class_codes = ["TEST_CLASS_RIGHTS_COMMENT", "TEST_CLASS_RIGHTS_OLC"]
        access_info = ClassificationData.get_access_info(class_codes, obj=doc, add_base_classes=True)

        expected_access_info = {
            'TEST_CLASS_RIGHTS_BASE': False,
            'TEST_CLASS_APPLICABLE': False,
            'TEST_CLASS_RIGHTS_OLC': False,
            'TEST_CLASS_RIGHTS_COMMENT': True,
            'TEST_BASE_CLASS': False
        }
        self.assertDictEqual(expected_access_info, access_info)

    def test_classification_data_with_right_filter(self):
        classification_data = ClassificationData(self.document, check_rights=True)
        properties, metadata, checksum = classification_data.get_classification()

        classification_data_complete = ClassificationData(self.document, check_rights=False)
        properties_complete, metadata_complete, checksum_complete = classification_data_complete.get_classification()

        self.assertEqual(checksum, checksum_complete)
        self.assertTrue(len(properties_complete) > len(properties))
        self.assertTrue(len(metadata_complete["classes"]) > len(metadata["classes"]))
        self.assertTrue(len(metadata_complete["addtl_properties"]) > len(metadata["addtl_properties"]))

    def test_remove_normal_classification_full_update_mode(self):
        self._test_remove_classification_full_update_mode("TEST_CLASS_ALL_PROPERTY_TYPES")

    def test_remove_normal_classification_partial_update_mode(self):
        self._test_remove_classification_partial_update_mode("TEST_CLASS_ALL_PROPERTY_TYPES")

    def test_remove_hidden_classification_full_update_mode(self):
        self._test_remove_classification_full_update_mode("TEST_SUB_CLASS_HIDDEN")

    def test_remove_hidden_classification_partial_update_mode(self):
        self._test_remove_classification_partial_update_mode("TEST_SUB_CLASS_HIDDEN")

    def test_remove_olc_classification_full_update_mode(self):
        self._test_remove_classification_full_update_mode("TEST_CLASS_RIGHTS_OLC")

    def test_remove_olc_classification_partial_update_mode(self):
        self._test_remove_classification_partial_update_mode("TEST_CLASS_RIGHTS_OLC")

    def test_remove_released_classification_full_update_mode(self):
        class_code_to_delete = "TEST_CLASS_RIGHTS_OLC"
        doc = self._create_mixed_classified_object(
            "Remove released class full update mode: " + class_code_to_delete, release_classification=True
        )
        all_classification_data = api.get_classification(doc, check_rights=False)

        classification_update_data = api.get_classification(doc, check_rights=False)
        classification_update_data["assigned_classes"].remove(class_code_to_delete)

        with self.assertRaisesRegex(
            ue.Exception,
            ".*Sie sind nicht berechtigt, die Klassifizierung mit folgenden Klassen zu ändern oder herzustellen:\.*"
        ):
            api.update_classification(doc, classification_update_data, full_update_mode=True)

        classification_data = api.get_classification(doc)
        expected_assigned_classes = set(self.all_class_codes)
        self.assertSetEqual(expected_assigned_classes, set(classification_data["assigned_classes"]))

        api.update_classification(doc, classification_update_data, full_update_mode=True, check_access=False)

        classification_data = api.get_classification(doc)
        self.assertNotIn(class_code_to_delete, classification_data["assigned_classes"])
        expected_assigned_classes = set(self.all_class_codes) - set([class_code_to_delete])
        self.assertSetEqual(expected_assigned_classes, set(classification_data["assigned_classes"]))

    def test_remove_released_classification_partial_update_mode(self):
        class_code_to_delete = "TEST_CLASS_RIGHTS_OLC"
        doc = self._create_mixed_classified_object(
            "Remove class released doc partial update mode: " + class_code_to_delete, release_document=True
        )
        all_classification_data = api.get_classification(doc)

        classification_update_data = api.get_classification(doc, check_rights=True)
        classification_update_data["deleted_classes"] = [class_code_to_delete]

        with self.assertRaisesRegex(
            ue.Exception,
            ".*Sie sind nicht berechtigt, die Klassifizierung mit folgenden Klassen zu ändern oder herzustellen:\.*"
        ):
            api.update_classification(doc, classification_update_data, full_update_mode=False)

        classification_data = api.get_classification(doc)
        expected_assigned_classes = set(self.all_class_codes)
        self.assertSetEqual(expected_assigned_classes, set(classification_data["assigned_classes"]))

        api.update_classification(doc, classification_update_data, full_update_mode=False, check_access=False)

        classification_data = api.get_classification(doc)
        self.assertNotIn(class_code_to_delete, classification_data["assigned_classes"])
        expected_assigned_classes = set(self.all_class_codes) - set([class_code_to_delete])
        self.assertSetEqual(expected_assigned_classes, set(classification_data["assigned_classes"]))

    def test_modify_multivalues_full_update_mode(self):
        doc = self._create_mixed_classified_object(
            "Modify multivalues full update mode", release_document=False
        )
        all_classification_data = api.get_classification(doc)

        multival_prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"
        api.add_multivalue(all_classification_data, multival_prop_code)
        api.add_multivalue(all_classification_data, multival_prop_code)
        all_classification_data["properties"][multival_prop_code][1]["value"] = "new value 1"
        all_classification_data["properties"][multival_prop_code][2]["value"] = "new value 2"
        api.update_classification(doc, all_classification_data, full_update_mode=True)

        classification_data = api.get_classification(doc)
        self.assertEqual(
            len(all_classification_data["properties"][multival_prop_code]),
            len(classification_data["properties"][multival_prop_code])
        )
        for pos, value in enumerate(all_classification_data["properties"][multival_prop_code]):
            self.assertEqual(
                value["value"],
                classification_data["properties"][multival_prop_code][pos]["value"]
            )

        classification_data["properties"][multival_prop_code][0]["value"] = "modify value"
        classification_data["properties"][multival_prop_code][1]["value"] = ""
        classification_data["properties"][multival_prop_code].pop()
        api.update_classification(doc, classification_data, full_update_mode=True)

        updated_classification_data = api.get_classification(doc)
        self.assertEqual(
            len(classification_data["properties"][multival_prop_code]),
            len(updated_classification_data["properties"][multival_prop_code])
        )
        for pos, value in enumerate(classification_data["properties"][multival_prop_code]):
            self.assertEqual(
                value["value"],
                updated_classification_data["properties"][multival_prop_code][pos]["value"]
            )

    def test_modify_multivalues_partial_update_mode(self):
        doc = self._create_mixed_classified_object(
            "Modify multivalues partial update mode", release_document=False
        )
        all_classification_data = api.get_classification(doc)

        multival_prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"
        api.add_multivalue(all_classification_data, multival_prop_code)
        api.add_multivalue(all_classification_data, multival_prop_code)
        all_classification_data["properties"][multival_prop_code][1]["value"] = "new value 1"
        all_classification_data["properties"][multival_prop_code][2]["value"] = "new value 2"
        api.update_classification(doc, all_classification_data, full_update_mode=False)

        classification_data = api.get_classification(doc)
        self.assertEqual(
            len(all_classification_data["properties"][multival_prop_code]),
            len(classification_data["properties"][multival_prop_code])
        )
        for pos, value in enumerate(all_classification_data["properties"][multival_prop_code]):
            self.assertEqual(
                value["value"],
                classification_data["properties"][multival_prop_code][pos]["value"]
            )

        classification_data["properties"][multival_prop_code][0]["value"] = "modify value"
        classification_data["properties"][multival_prop_code][1]["value"] = ""
        classification_data["properties"][multival_prop_code].pop()
        api.update_classification(doc, classification_data, full_update_mode=False)

        updated_classification_data = api.get_classification(doc)
        self.assertEqual(
            len(classification_data["properties"][multival_prop_code]),
            len(updated_classification_data["properties"][multival_prop_code])
        )
        for pos, value in enumerate(classification_data["properties"][multival_prop_code]):
            self.assertEqual(
                value["value"],
                updated_classification_data["properties"][multival_prop_code][pos]["value"]
            )

    def test_partial_update_mode_missing_properties(self):
        doc = self._create_mixed_classified_object(
            "Modify multivalues partial update mode", release_document=False
        )
        classification_data = api.get_classification(doc)

        prop_code = "TEST_CLASS_ALL_PROPERTY_TYPES_TEST_PROP_TEXT_MULTIVALUE"
        prop_value = classification_data["properties"][prop_code][0]["value"]
        del classification_data["properties"][prop_code]
        api.update_classification(doc, classification_data, full_update_mode=False)

        classification_data = api.get_classification(doc)
        self.assertEqual(
            prop_value,
            classification_data["properties"][prop_code][0]["value"]
        )

    def test_partial_update_mode_additional_properties(self):
        doc = self._create_mixed_classified_object(
            "Modify multivalues partial update mode", release_document=False
        )
        classification_data = api.get_classification(doc)
        prop_code_single = "TEST_PROP_TEXT"
        prop_code_multi = "TEST_PROP_TEXT_MULTIVALUE"
        addtl_props = api.create_additional_props([prop_code_single, prop_code_multi])
        api.add_multivalue(addtl_props, prop_code_multi)
        addtl_props["properties"][prop_code_single][0]["value"] = prop_code_single
        addtl_props["properties"][prop_code_multi][0]["value"] = prop_code_multi + "_0"
        addtl_props["properties"][prop_code_multi][1]["value"] = prop_code_multi + "_1"

        classification_data["properties"].update(addtl_props["properties"])
        api.update_classification(doc, classification_data, full_update_mode=False)
        classification_data_updated = api.get_classification(doc)
        self.assertEqual(
            addtl_props["properties"][prop_code_single][0]["value"],
            classification_data_updated["properties"][prop_code_single][0]["value"]
        )
        self.assertEqual(
            len(addtl_props["properties"][prop_code_multi]),
            len(classification_data_updated["properties"][prop_code_multi])
        )
        self.assertEqual(
            addtl_props["properties"][prop_code_multi][0]["value"],
            classification_data_updated["properties"][prop_code_multi][0]["value"]
        )
        self.assertEqual(
            addtl_props["properties"][prop_code_multi][1]["value"],
            classification_data_updated["properties"][prop_code_multi][1]["value"]
        )

        # test deleted addtl multivalue
        classification_data_updated["properties"][prop_code_multi].pop()
        api.update_classification(doc, classification_data_updated, full_update_mode=False)
        classification_data_updated = api.get_classification(doc)
        self.assertEqual(
            addtl_props["properties"][prop_code_single][0]["value"],
            classification_data_updated["properties"][prop_code_single][0]["value"]
        )
        self.assertEqual(
            len(addtl_props["properties"][prop_code_multi]) - 1,
            len(classification_data_updated["properties"][prop_code_multi])
        )
        self.assertEqual(
            addtl_props["properties"][prop_code_multi][0]["value"],
            classification_data_updated["properties"][prop_code_multi][0]["value"]
        )

        classification_data_updated = api.get_classification(doc)
        del classification_data_updated["properties"][prop_code_single]
        del classification_data_updated["properties"][prop_code_multi]
        api.update_classification(doc, classification_data_updated, full_update_mode=False)
        classification_data_updated = api.get_classification(doc)
        self.assertEqual(
            addtl_props["properties"][prop_code_single][0]["value"],
            classification_data_updated["properties"][prop_code_single][0]["value"]
        )
        self.assertEqual(
            len(addtl_props["properties"][prop_code_multi]) - 1,
            len(classification_data_updated["properties"][prop_code_multi])
        )
        self.assertEqual(
            addtl_props["properties"][prop_code_multi][0]["value"],
            classification_data_updated["properties"][prop_code_multi][0]["value"]
        )

        classification_data_updated = api.get_classification(doc)
        classification_data_updated["deleted_properties"] = [prop_code_single, prop_code_multi]
        api.update_classification(doc, classification_data_updated, full_update_mode=False)
        classification_data_updated = api.get_classification(doc)
        self.assertNotIn(
            prop_code_single, classification_data_updated["properties"]
        )
        self.assertNotIn(
            prop_code_multi, classification_data_updated["properties"]
        )

    def _create_classified_object_mixed_subclasses(
        self, title, class_codes, release_document=False, release_classification=False
    ):

        def set_property_values(properties):
            for prop_code in list(properties.keys()):
                prop_value_1 = properties[prop_code][0]
                prop_value_2 = copy.deepcopy(prop_value_1)
                properties[prop_code].append(prop_value_2)

                prop_type = prop_value_1["property_type"]
                if "block" == prop_type:
                    set_property_values(prop_value_1["value"]["child_props"])
                    set_property_values(prop_value_2["value"]["child_props"])
                elif "multilang" == prop_type:
                    prop_value_1["value"]["de"]["text_value"] = prop_code + "_1_de"
                    prop_value_1["value"]["en"]["text_value"] = prop_code + "_1_en"
                    prop_value_2["value"]["de"]["text_value"] = prop_code + "_2_de"
                    prop_value_2["value"]["en"]["text_value"] = prop_code + "_2_en"
                elif "text" == prop_type:
                    prop_value_1["value"] = prop_code + "_1"
                    prop_value_2["value"] = prop_code + "_2"

        doc = operation(
            constants.kOperationNew,
            Document,
            titel=title,
            z_categ1="142",
            z_categ2="153"
        )
        self.assertIsNotNone(doc, 'document to classify could not be created!')

        classification_data = api.get_new_classification(class_codes)
        set_property_values(classification_data["properties"])
        api.update_classification(doc, classification_data)

        if release_document:
           doc.ChangeState(200)

        if release_classification:
            object_classification = ObjectClassification.ByKeys(
               ref_object_id=doc.cdb_object_id, class_code="TEST_CLASS_SUB_OLC"
            )
            object_classification.ChangeState(200)
            object_classification = ObjectClassification.ByKeys(
                ref_object_id=doc.cdb_object_id, class_code="TEST_CLASS_SUB_OLC_HIDDEN"
            )
            object_classification.ChangeState(200)

        return doc

    def test_mixed_subclasses_full_data(self):

        def check_deletable_properties(data):
            class_codes_to_delete = []
            for class_code in class_codes:
                class_codes_to_delete.append(class_code)
                data["deleted_classes"] = class_codes_to_delete
                updater = ClassificationUpdater(doc, full_update_mode=False)
                updater._prepare_update(data)

                props_codes_from_deleted_classes = set()
                for class_code in data["deleted_classes"]:
                    clazz = ClassificationClass.KeywordQuery(code=class_code)[0]
                    if set(class_codes) - set(class_codes_to_delete):
                        # classes will remain. only own properties are deletable
                        for prop in clazz.OwnProperties:
                            props_codes_from_deleted_classes.add(prop.code)
                    else:
                        # no classes will remain. also inherited properties are deletable
                        for prop in clazz.Properties:
                            props_codes_from_deleted_classes.add(prop.code)

                deletable_prop_codes = updater._property_codes_of_deleted_classes()
                self.assertSetEqual(props_codes_from_deleted_classes, deletable_prop_codes)

        class_codes = [
            "TEST_CLASS_SUB_HIDDEN",
            "TEST_CLASS_SUB_NORMAL",
            "TEST_CLASS_SUB_OLC",
            "TEST_CLASS_SUB_OLC_HIDDEN",
            "TEST_CLASS_SUB_RESTRICTED"
        ]

        doc = self._create_classified_object_mixed_subclasses("test doc", class_codes)
        check_deletable_properties(api.get_classification(doc))
        check_deletable_properties(api.get_classification(doc, check_rights=True))

    def test_delete_hidden_class(self):
        doc = self._create_mixed_classified_object(
            "Modify multivalues partial update mode", release_document=False
        )
        hidden_prop_code = "TEST_PROP_HIDDEN_TEXT"
        addtl_props = api.create_additional_props([hidden_prop_code])
        addtl_props["properties"][hidden_prop_code][0]["value"] = hidden_prop_code
        api.update_additional_props(doc, addtl_props)

        hidden_class_code = "TEST_SUB_CLASS_HIDDEN"
        classification_data = api.get_classification(doc, check_rights=True)
        classification_data["deleted_classes"] = [hidden_class_code]
        classification_data["deleted_properties"] = [hidden_prop_code]
        api.update_classification(doc, classification_data, full_update_mode=False)

        classification_data = api.get_classification(doc, check_rights=False)
        self.assertNotIn(hidden_class_code, tools.get_assigned_class_codes(classification_data))
        self.assertNotIn(hidden_prop_code, classification_data["properties"])
