# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import unittest
import cdb

from cdb import constants
from cdb.objects import operations
from cdb.testcase import require_service

from cs import documents  # @UnresolvedImport
from cs.classification import api, catalog, classes
from cs.classification.applicability import ClassificationApplicability
from cs.classification.constraints import Constraint
from cs.classification.tests import utils


class test_classification_classes(utils.ClassificationTestCase):

    def setUp(self):
        super(test_classification_classes, self).setUp()
        require_service("cdb.uberserver.services.index.IndexService")

        self.classes = {
            "TEST_BASE_CLASS": classes.ClassificationClass.ByKeys(code="TEST_BASE_CLASS"),
            "TEST_CLASS_RESISTOR": classes.ClassificationClass.ByKeys(code="TEST_CLASS_RESISTOR"),
            "TEST_CLASS_TOP_LEVEL": classes.ClassificationClass.ByKeys(code="TEST_CLASS_TOP_LEVEL")
        }
        self.document = documents.Document.ByKeys(z_nummer="CLASS000003", z_index="")
        self.assertTrue(self.document is not None)

    def _create_test_class(self, code, parent_class_id=None):
        class_args = {
            "cdb_status_txt": "Released",
            "cdb_objektart": "cs_classification_class",
            "code": code,
            "name_de": code,
            "parent_class_id": parent_class_id,
            "status": 200
        }
        test_class = classes.ClassificationClass.Create(**class_args)
        self.classes[code] = test_class
        return test_class

    def _create_test_class_hierarchie(self, prefix):
        base_class = self._create_test_class(prefix + '_BASE_CLASS')
        applicability_args = {
            "classification_class_id": base_class.cdb_object_id,
            "dd_classname": "document",
            "is_active": 1,
            "write_access_obj": "save"
        }
        ClassificationApplicability.Create(**applicability_args)

        sub_class_1 = self._create_test_class(
            prefix + '_SUB_CLASS_1', base_class.cdb_object_id
        )
        sub_class_1_sub_class_1 = self._create_test_class(
            prefix + '_SUB_CLASS_1_SUB_CLASS_1', sub_class_1.cdb_object_id
        )
        sub_class_1_sub_class_2 = self._create_test_class(
            prefix + '_SUB_CLASS_1_SUB_CLASS_2', sub_class_1.cdb_object_id
        )
        sub_class_2 = self._create_test_class(
            prefix + '_SUB_CLASS_2', base_class.cdb_object_id
        )
        sub_class_2_sub_class_1 = self._create_test_class(
            prefix + '_SUB_CLASS_2_SUB_CLASS_1', sub_class_2.cdb_object_id
        )
        sub_class_2_sub_class_2 = self._create_test_class(
            prefix + '_SUB_CLASS_2_SUB_CLASS_2', sub_class_2.cdb_object_id
        )


    def test_code_invalid(self):
        """The class  code cannot start with a number and cannot contain any spaces"""
        invalid_codes = [
            "123",
            "123Stella",
            "Once upon a time"
        ]
        for code in invalid_codes:
            with self.assertRaisesRegex(cdb.ElementsError, "Ungültiger Wert für das Attribut 'Kennung'. Die Kennung darf nicht mit einer Zahl beginnen und darf keine Leer- und Sonderzeichen enthalten."):
                operations.operation(
                    constants.kOperationNew,  # @UndefinedVariable
                    classes.ClassificationClass,
                    code=code,
                )

    def test_code_unique(self):
        """The class code should be globally unique"""
        with self.assertRaisesRegex(cdb.ElementsError, "Der Wert von 'Kennung' existiert bereits"):
            operations.operation(
                constants.kOperationNew,  # @UndefinedVariable
                classes.ClassificationClass,
                code="TEST_BASE_CLASS"
            )

    def test_changing_base_class_hierarchie(self):
        class_to_modify = self.classes["TEST_BASE_CLASS"]
        base_class = self.classes["TEST_CLASS_TOP_LEVEL"]

        with self.assertRaisesRegex(cdb.ElementsError, "Diese übergeordnete Klasse kann nicht geändert werden, da diese Klasse bereits in einer Objektbewertung verwendet wird."):
            operations.operation(
                constants.kOperationModify,  # @UndefinedVariable
                class_to_modify, parent_class_id=base_class.cdb_object_id
            )

    def test_recursive_class_hierarchie(self):
        class_to_modify = self.classes["TEST_BASE_CLASS"]
        base_class = class_to_modify

        # test assigning class as baseclass for itsself
        with self.assertRaisesRegex(cdb.ElementsError, "Rekursive Klassenhierarchien werden nicht unterstützt."):
            operations.operation(
                constants.kOperationModify,  # @UndefinedVariable
                class_to_modify, parent_class_id=base_class.cdb_object_id
            )

        # test assigning subclass as baseclass
        base_class = self.classes["TEST_CLASS_RESISTOR"]
        with self.assertRaisesRegex(cdb.ElementsError, "Rekursive Klassenhierarchien werden nicht unterstützt."):
            operations.operation(
                constants.kOperationModify,  # @UndefinedVariable
                class_to_modify, parent_class_id=base_class.cdb_object_id
            )

    def _test_class_copy(self, class_code):

        source_clazz = classes.ClassificationClass.ByKeys(code=class_code)
        self.assertIsNotNone(source_clazz, "Source class {} could not be found".format(class_code))
        clazz_args = {
            'code': classes.ClassificationClass.get_valid_code(source_clazz.code)
        }
        prop_code_mapping = {}
        copied_clazz = source_clazz.copy(clazz_args, prop_code_mapping)
        self.assertIsNotNone(copied_clazz, "Class {} is not copied".format(class_code))

        self.assertEqual(
            len(source_clazz.Children), len(copied_clazz.Children), "Subclasses do not match"
        )

        constraints = Constraint.KeywordQuery(classification_class_id=copied_clazz.cdb_object_id)
        for constraint in constraints:
            if any(prop_code in constraint.when_condition for prop_code in prop_code_mapping.keys()):
                self.fail("Not all property codes are replaced in constraint when conditions.")
            if any(prop_code in constraint.expression for prop_code in prop_code_mapping.keys()):
                self.fail("Not all property codes are replaced in constraint expressions.")

        copied_props = {}
        for prop in copied_clazz.OwnProperties:
            copied_props[prop.code] = prop
            for formula in prop.Formulas:
                if any(prop_code in formula.when_condition for prop_code in prop_code_mapping.keys()):
                    self.fail("Not all property codes are replaced in formula when conditions.")
                if any(prop_code in formula.value_formula for prop_code in prop_code_mapping.keys()):
                    self.fail("Not all property codes are replaced in formula expressions.")
            for rule in prop.Rules:
                if any(prop_code in rule.expression for prop_code in prop_code_mapping.keys()):
                    self.fail("Not all property codes are replaced in rule expressions.")

        for source_prop in source_clazz.OwnProperties:
            self.assertTrue(prop_code_mapping[source_prop.code] in copied_props)

    def test_class_copy(self):
        self._test_class_copy("COMPUTER")

    def test_class_copy_with_many_props(self):
        self._test_class_copy("TEST_CLASS_WITH_MANY_PROPERTIES")

    def test_get_all_properties(self):
        self._create_test_class_hierarchie('test_get_all_properties')
        class_codes = [
            'test_get_all_properties_BASE_CLASS',
            'test_get_all_properties_SUB_CLASS_2',
            'test_get_all_properties_SUB_CLASS_2_SUB_CLASS_2'
        ]
        clazz = self.classes['test_get_all_properties_SUB_CLASS_2_SUB_CLASS_2']

        expected_property_codes = set()
        catalog_property = catalog.Property.KeywordQuery(code='TEST_PROP_TEXT')[0]
        for class_code in class_codes:
            classes.ClassProperty.NewPropertyFromCatalog(
                catalog_property, self.classes[class_code].cdb_object_id, skip_solr=True
            )
            expected_property_codes.add(class_code + '_TEST_PROP_TEXT')

        all_properties = clazz.Properties
        self.assertSetEqual(
            expected_property_codes,
            set([property.code for property in all_properties])
        )

    def test_get_base_classes(self):

        self._create_test_class_hierarchie('test_get_base_class_codes')

        expected_base_class_codes = set([
            'test_get_base_class_codes_BASE_CLASS',
            'test_get_base_class_codes_SUB_CLASS_2'
        ])
        expected_base_class_codes_with_given = set([
            'test_get_base_class_codes_BASE_CLASS',
            'test_get_base_class_codes_SUB_CLASS_2',
            'test_get_base_class_codes_SUB_CLASS_2_SUB_CLASS_2'
        ])

        base_class_codes = classes.ClassificationClass.get_base_class_codes(
            class_codes=['test_get_base_class_codes_SUB_CLASS_2_SUB_CLASS_2']
        )
        self.assertSetEqual(expected_base_class_codes, set(base_class_codes))
        base_class_codes = classes.ClassificationClass.get_base_class_codes(
            class_codes=['test_get_base_class_codes_SUB_CLASS_2_SUB_CLASS_2'], include_given=True
        )
        self.assertSetEqual(expected_base_class_codes_with_given, set(base_class_codes))

        base_class_ids = classes.ClassificationClass.get_base_class_ids(
            class_codes=['test_get_base_class_codes_SUB_CLASS_2_SUB_CLASS_2']
        )
        self.assertSetEqual(set([
                self.classes[class_code].cdb_object_id for class_code in expected_base_class_codes
            ]),
            set(base_class_ids)
        )
        base_class_ids = classes.ClassificationClass.get_base_class_ids(
            class_codes=['test_get_base_class_codes_SUB_CLASS_2_SUB_CLASS_2'], include_given=True
        )
        self.assertSetEqual(set([
            self.classes[class_code].cdb_object_id for class_code in expected_base_class_codes_with_given
        ]),
            set(base_class_ids)
        )

        base_classes = classes.ClassificationClass.get_base_classes(
            class_codes=['test_get_base_class_codes_SUB_CLASS_2_SUB_CLASS_2']
        )
        self.assertSetEqual(
            expected_base_class_codes,
            set([clazz.code for clazz in base_classes])
        )
        base_classes = classes.ClassificationClass.get_base_classes(
            class_codes=['test_get_base_class_codes_SUB_CLASS_2_SUB_CLASS_2'], include_given=True
        )
        self.assertSetEqual(
            expected_base_class_codes_with_given,
            set([clazz.code for clazz in base_classes])
        )
        base_classes = self.classes['test_get_base_class_codes_SUB_CLASS_2_SUB_CLASS_2'].AllParents
        self.assertSetEqual(
            expected_base_class_codes,
            set([clazz.code for clazz in base_classes])
        )

    def test_get_sub_classes(self):
        self._create_test_class_hierarchie('test_get_sub_class_codes')
        expected_sub_class_codes = set([
            'test_get_sub_class_codes_SUB_CLASS_1',
            'test_get_sub_class_codes_SUB_CLASS_1_SUB_CLASS_1',
            'test_get_sub_class_codes_SUB_CLASS_1_SUB_CLASS_2',
            'test_get_sub_class_codes_SUB_CLASS_2',
            'test_get_sub_class_codes_SUB_CLASS_2_SUB_CLASS_1',
            'test_get_sub_class_codes_SUB_CLASS_2_SUB_CLASS_2'
        ])

        sub_class_codes = classes.ClassificationClass.get_sub_class_codes(
            class_codes=['test_get_sub_class_codes_BASE_CLASS']
        )
        self.assertSetEqual(expected_sub_class_codes, set(sub_class_codes))

        sub_class_ids = classes.ClassificationClass.get_sub_class_ids(
            class_codes=['test_get_sub_class_codes_BASE_CLASS']
        )
        self.assertSetEqual(set([
            self.classes[class_code].cdb_object_id for class_code in expected_sub_class_codes
        ]),
            set(sub_class_ids)
        )

    def test_has_object_classifications(self):
        self._create_test_class_hierarchie('test_has_object_classifications')
        api.update_classification(
            self.create_document("test_has_object_classifications"),
            api.get_new_classification(["test_has_object_classifications_SUB_CLASS_2_SUB_CLASS_2"])
        )
        for class_code in [
            'test_has_object_classifications_SUB_CLASS_2_SUB_CLASS_2',
            'test_has_object_classifications_SUB_CLASS_2',
            'test_has_object_classifications_BASE_CLASS',
        ]:
            self.assertTrue(
                classes.ClassificationClass.has_class_object_classifications(
                    class_codes=[class_code]
                )
            )

    def test_get_applicable_classes(self):
        applicable_classes = classes.ClassificationClass.get_applicable_classes(
            'document',
            class_codes = [
                'TEST_CLASS_ALL_PROPERTY_TYPES',
                'TEST_CLASS_APPLICABLE_DOCUMENT_SUB',
                'TEST_CLASS_NOT_APPLICABLE',
                'TEST_CLASS_ROOT_NOT_RELEASED_NOT_APPLICABLE_WITH_SUBCLASS_APPLICABLE_RELEASED'
            ]
        )
        self.assertSetEqual(
            set(['TEST_CLASS_ALL_PROPERTY_TYPES', 'TEST_CLASS_APPLICABLE_DOCUMENT_SUB']),
            set(class_info['code'] for class_info in applicable_classes)
        )

    def test_get_applicable_root_classes(self):
        applicable_classes = {}
        for class_info in classes.ClassificationClass.get_applicable_root_classes('document'):
            applicable_classes[class_info['code']] = class_info

        expected_class_codes = [
            'TEST_CLASS_ROOT_RELEASED_APPLICABLE',
            'TEST_CLASS_ROOT_RELEASED_NOT_APPLICABLE_WITH_INTERMEDIATE_CLASS_RELEASED',
            'TEST_CLASS_ROOT_RELEASED_NOT_APPLICABLE_WITH_INTERMEDIATE_CLASS_NOT_RELEASED',
            'TEST_CLASS_ROOT_RELEASED_NOT_APPLICABLE_WITH_ONE_PATH_APPLICABLE_RELEASED',
            'TEST_CLASS_ROOT_RELEASED_NOT_APPLICABLE_WITH_SUBCLASS_APPLICABLE_RELEASED'
        ]

        for class_code in expected_class_codes:
            self.assertTrue(class_code in applicable_classes)
            class_info = applicable_classes[class_code]
            if 'TEST_CLASS_ROOT_RELEASED_APPLICABLE' == class_code:
                self.assertTrue(class_info['is_applicable'])
                self.assertEqual(1, class_info['flags'][0])
            else:
                self.assertFalse(class_info['is_applicable'])
                self.assertEqual(0, class_info['flags'][0])

        not_expected_class_codes = [
            'TEST_CLASS_ROOT_RELEASED_NOT_APPLICABLE',
            'TEST_CLASS_ROOT_RELEASED_NOT_APPLICABLE_WITH_SUBCLASS_APPLICABLE_NOT_RELEASED',
            'TEST_CLASS_ROOT_NOT_RELEASED_APPLICABLE',
            'TEST_CLASS_ROOT_NOT_RELEASED_NOT_APPLICABLE',
            'TEST_CLASS_ROOT_NOT_RELEASED_NOT_APPLICABLE_WITH_SUBCLASS_APPLICABLE_RELEASED',
            'TEST_CLASS_ROOT_NOT_RELEASED_NOT_APPLICABLE_WITH_SUBCLASS_APPLICABLE_NOT_RELEASED'
        ]

        for class_code in not_expected_class_codes:
            self.assertTrue(class_code not in applicable_classes)

    def test_get_applicable_sub_classes(self):
        applicable_classes = {}
        for class_info in classes.ClassificationClass.get_applicable_sub_classes(
            'document', 'TEST_CLASS_ROOT_RELEASED_NOT_APPLICABLE_WITH_ONE_PATH_APPLICABLE_RELEASED'
        ):
            applicable_classes[class_info['code']] = class_info

        expected_sub_classes = [
            'TEST_CLASS_ROOT_RELEASED_NOT_APPLICABLE_WITH_ONE_PATH_APPLICABLE_RELEASED_INTERMEDIATE_APPLICABLE',
            'TEST_CLASS_ROOT_RELEASED_NOT_APPLICABLE_WITH_ONE_PATH_APPLICABLE_RELEASED_INTERMEDIATE_NOT_APPLICABLE'
        ]
        for class_code in expected_sub_classes:
            self.assertTrue(class_code in applicable_classes)

        self.assertEqual(0, len(classes.ClassificationClass.get_applicable_sub_classes(
            'document', 'TEST_CLASS_ROOT_RELEASED_NOT_APPLICABLE_WITH_ONE_PATH_APPLICABLE_RELEASED_SUB_NOT_APPLICABLE'
        )))

    def test_search_applicable_classes(self):
        applicable_classes = {}
        for class_info in classes.ClassificationClass.search_applicable_classes(
                'document', 'TEST_CLASS_ALL'
        ):
            applicable_classes[class_info['code']] = class_info
        expected_classes = [
            'TEST_CLASS_ALL_PROPERTY_TYPES'
        ]
        for class_code in expected_classes:
            self.assertTrue(class_code in applicable_classes)

        applicable_classes = {}
        for class_info in classes.ClassificationClass.search_applicable_classes(
                'document', 'Test_Class_Root'
        ):
            applicable_classes[class_info['code']] = class_info
        expected_classes = [
            'TEST_CLASS_ROOT_RELEASED_NOT_APPLICABLE_WITH_SUBCLASS_APPLICABLE_RELEASED',
            'TEST_CLASS_ROOT_RELEASED_NOT_APPLICABLE_INTERMEDIATE_CLASS_RELEASED',
            'TEST_CLASS_ROOT_RELEASED_NOT_APPLICABLE_WITH_ONE_PATH_APPLICABLE_RELEASED_INTERMEDIATE_APPLICABLE',
            'TEST_CLASS_ROOT_RELEASED_NOT_APPLICABLE_WITH_ONE_PATH_APPLICABLE_RELEASED_SUB_APPLICABLE',
            'TEST_CLASS_ROOT_RELEASED_NOT_APPLICABLE_INTERMEDIATE_SUB_CLASS__RELEASED',
            'TEST_CLASS_ROOT_RELEASED_NOT_APPLICABLE_SUBCLASS_APPLICABLE_RELEASED',
            'TEST_CLASS_ROOT_RELEASED_NOT_APPLICABLE_WITH_INTERMEDIATE_CLASS_RELEASED',
            'TEST_CLASS_ROOT_RELEASED_NOT_APPLICABLE_WITH_ONE_PATH_APPLICABLE_RELEASED',
            'TEST_CLASS_ROOT_RELEASED_APPLICABLE'
        ]
        for class_code in expected_classes:
            self.assertTrue(class_code in applicable_classes)

    def test_access_rights(self):

        class_codes = [
            'TEST_CLASS_APPLICABILITIES_DOCUMENT_OLC',
            'TEST_CLASS_APPLICABILITIES_DOCUMENT_OLC_SUB',
            'TEST_CLASS_APPLICABILITIES_DOCUMENT_PUBLIC',
            'TEST_CLASS_APPLICABILITIES_DOCUMENT_PUBLIC_SUB',
            'TEST_CLASS_APPLICABILITIES_DOCUMENT_SUB',
            'TEST_CLASS_APPLICABILITIES_DOCUMENT_SUBCLASS',
            'TEST_CLASS_APPLICABILITIES_ORGA',
        ]

        expected_access_rights = {
            'document' : {
                'TEST_CLASS_APPLICABILITIES_DOCUMENT_SUBCLASS': ('save', '', ''),
                'TEST_CLASS_APPLICABILITIES_DOCUMENT_SUB': ('save', '', ''),
                'TEST_CLASS_APPLICABILITIES_ORGA': None,
                'TEST_CLASS_APPLICABILITIES_DOCUMENT_PUBLIC_SUB': ('', '', ''),
                'TEST_CLASS_APPLICABILITIES_DOCUMENT_OLC': ('save', 'save', 'cs_property'),
                'TEST_CLASS_APPLICABILITIES_BASE': None,
                'TEST_CLASS_APPLICABILITIES_DOCUMENT': ('save', '', ''),
                'TEST_CLASS_APPLICABILITIES_DOCUMENT_PUBLIC': ('', '', ''),
                'TEST_CLASS_APPLICABILITIES_DOCUMENT_OLC_SUB': ('save', 'save', 'cs_property')
            },
            'dummy_document_subclass': {
                'TEST_CLASS_APPLICABILITIES_DOCUMENT_SUBCLASS': ('', '', ''),
                'TEST_CLASS_APPLICABILITIES_DOCUMENT_SUB': ('save', '', ''),
                'TEST_CLASS_APPLICABILITIES_ORGA': None,
                'TEST_CLASS_APPLICABILITIES_DOCUMENT_PUBLIC_SUB': ('', '', ''),
                'TEST_CLASS_APPLICABILITIES_DOCUMENT_OLC': ('save', 'save', 'cs_property'),
                'TEST_CLASS_APPLICABILITIES_BASE': None,
                'TEST_CLASS_APPLICABILITIES_DOCUMENT': ('save', '', ''),
                'TEST_CLASS_APPLICABILITIES_DOCUMENT_PUBLIC': ('', '', ''),
                'TEST_CLASS_APPLICABILITIES_DOCUMENT_OLC_SUB': ('save', 'save', 'cs_property')
            },
        }

        for dd_class in ['document', 'dummy_document_subclass']:
            access_rights = classes.ClassificationClass.get_access_rights(
                dd_class, class_codes=class_codes
            )
            for class_code in class_codes:
                new_accss_right = access_rights[class_code]["access_rights"]
                expected_access_right = expected_access_rights[dd_class][class_code]
                self.assertEqual(expected_access_right, new_accss_right)

    def test_oid_code_mapping(self):

        expected_base_class_codes_with_given = set([
            'test_get_base_class_codes_BASE_CLASS',
            'test_get_base_class_codes_SUB_CLASS_2',
            'test_get_base_class_codes_SUB_CLASS_2_SUB_CLASS_2'
        ])

        class_infos = classes.ClassificationClass.get_base_class_infos(
            class_codes=['TEST_CLASS_ALL_PROPERTY_TYPES'], include_given=True
        )
        class_ids = [class_info["cdb_object_id"] for class_info in class_infos]
        oids_to_code = classes.ClassificationClass.oids_to_code(class_ids)
        for class_info in class_infos:
            self.assertEqual(class_info["code"], oids_to_code[class_info["cdb_object_id"]])

        class_codes = [class_info["code"] for class_info in class_infos]
        oids_to_code = classes.ClassificationClass.codes_to_oid(class_codes)
        for class_info in class_infos:
            self.assertEqual(class_info["cdb_object_id"], oids_to_code[class_info["code"]])


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
