# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
# pylint: disable=too-many-lines
import random

# pylint: disable=deprecated-module
import string
from math import ceil

import webtest

from cdb import ElementsError, constants, ddl, sqlapi, testcase
from cdb.cdbuuid import create_uuid
from cdb.objects import operations
from cdb.platform.mom import getObjectHandle
from cdb.sqlapi import SQLselect
from cdb.testcase import RollbackTestCase, max_sql, skip_dbms
from cdb.validationkit import run_with_roles
from cdbwrapc import CDBClassDef, CDBMsg, SQLrows
from cs.platform.web.root import root as RootApp
from cs.variants.selection_condition import (
    SelectionCondition,
    get_expression_dd_field_length,
    is_expression_long,
    map_expression_to_correct_attribute,
)
from cs.variants.tests import common


class TestSelectionConditionWithVariantsTestCase(common.VariantsTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSelectionConditionWithVariantsTestCase, cls).setUpClass()
        testcase.require_service("cdb.uberserver.services.index.IndexService")

    @staticmethod
    def generate_expression(number_of_chars):
        return '"""{0}"""'.format(
            "".join(
                random.choice(string.ascii_lowercase + string.digits)
                for _ in range(max(number_of_chars - 6, 0))
            )
        )

    def approve_whole_maxbom(self):
        self.comp.Item.ChangeState(200)
        self.subassembly.ChangeState(200)
        self.maxbom.ChangeState(200)

    def assert_permission_exception(self, e):
        e_str = str(e)
        self.assertIn("(Relation: 'teile_stamm', Recht:'save_bom')", e_str)
        self.assertIn("(Beziehung:Stückliste)", e_str)
        self.assertIn("(Beziehung:Auswahlbedingungen)", e_str)
        self.assertIn("Rechteüberprüfung wurde auf dem referenzierenden Objekt", e_str)

    def test_copy_copies_selection_condition(self):
        self.assertEquals(len(self.comp.SelectionConditions), 1)

        new_comp = operations.operation(
            constants.kOperationCopy, self.comp, position=11
        )
        new_comp.Reload()
        self.assertEquals(len(new_comp.SelectionConditions), 1)

    def test_access_rights_item_not_released(self):
        self.assertTrue(self.selection_condition.CheckAccess("delete", "engineer"))
        self.assertTrue(self.selection_condition.CheckAccess("save", "engineer"))
        self.assertTrue(self.selection_condition.CheckAccess("create", "engineer"))

    def test_access_rights_item_review(self):
        self.subassembly.ChangeState(100)
        self.assertFalse(self.selection_condition.CheckAccess("delete", "engineer"))
        self.assertFalse(self.selection_condition.CheckAccess("save", "engineer"))
        self.assertFalse(self.selection_condition.CheckAccess("create", "engineer"))

    def test_access_rights_item_obsolete(self):
        self.subassembly.ChangeState(180)
        self.assertFalse(self.selection_condition.CheckAccess("delete", "engineer"))
        self.assertFalse(self.selection_condition.CheckAccess("save", "engineer"))
        self.assertFalse(self.selection_condition.CheckAccess("create", "engineer"))

    def test_access_rights_item_revision(self):
        self.comp.Item.ChangeState(200)
        self.subassembly.ChangeState(200)
        self.subassembly.ChangeState(190)
        self.assertFalse(self.selection_condition.CheckAccess("delete", "engineer"))
        self.assertFalse(self.selection_condition.CheckAccess("save", "engineer"))
        self.assertFalse(self.selection_condition.CheckAccess("create", "engineer"))

    def test_access_rights_item_released(self):
        self.comp.Item.ChangeState(200)
        self.subassembly.ChangeState(200)
        self.assertFalse(self.selection_condition.CheckAccess("delete", "engineer"))
        self.assertFalse(self.selection_condition.CheckAccess("save", "engineer"))
        self.assertFalse(self.selection_condition.CheckAccess("create", "engineer"))

    @run_with_roles(["public", "Engineering"])
    def test_delete_operation(self):
        self.approve_whole_maxbom()

        with self.assertRaises(ElementsError):
            try:
                operations.operation(
                    constants.kOperationDelete, self.selection_condition
                )
            except ElementsError as e:
                self.assert_permission_exception(e)
                raise

    @run_with_roles(["public", "Engineering"])
    def test_create_operation(self):
        self.approve_whole_maxbom()

        with self.assertRaises(ElementsError):
            try:
                operations.operation(
                    constants.kOperationNew,
                    SelectionCondition,
                    variability_model_id=self.variability_model.cdb_object_id,
                    ref_object_id=self.subassembly_comp.cdb_object_id,
                    expression="42 == 42",
                )
            except ElementsError as e:
                self.assert_permission_exception(e)
                raise

    @run_with_roles(["public", "Engineering"])
    def test_modify_operation(self):
        self.approve_whole_maxbom()

        with self.assertRaises(ElementsError):
            try:
                operations.operation(
                    constants.kOperationModify,
                    self.selection_condition,
                    expression="1 == 1",
                )
            except ElementsError as e:
                self.assert_permission_exception(e)
                raise

    def create_long_expression(self):
        expression_long = '"""{0}"""'.format(
            "".join(
                random.choice(string.ascii_lowercase + string.digits)
                for _ in range(10000)
            )
        )

        keys = {
            "variability_model_id": self.variability_model.cdb_object_id,
            "ref_object_id": create_uuid(),
        }

        with self.assertRaises(ValueError):
            operations.operation(
                constants.kOperationNew,
                SelectionCondition,
                **dict(keys, expression=expression_long)
            )

        result = operations.operation(
            constants.kOperationNew,
            SelectionCondition,
            **dict(keys, cs_sc_expression_long=expression_long)
        )

        return keys, expression_long, result

    def test_expression_object_framework(self):
        keys, _, _ = self.create_long_expression()

        with max_sql(1):
            selection_condition = SelectionCondition.ByKeys(**keys)

        with max_sql(0):
            self.assertEqual(None, selection_condition.expression)

    def test_expression_long_object_framework(self):
        keys, expression_long, _ = self.create_long_expression()

        with max_sql(1):
            selection_condition = SelectionCondition.ByKeys(**keys)

        with max_sql(1):
            self.assertEqual(
                expression_long, selection_condition.GetText("cs_sc_expression_long")
            )

    def test_expression_object_framework_collection(self):
        SelectionCondition.Query().Delete()

        self.create_long_expression()
        self.create_long_expression()
        self.create_long_expression()

        with max_sql(1):
            selection_conditions = SelectionCondition.Query().Execute()

        with max_sql(0):
            self.assertEqual([None, None, None], selection_conditions.expression)

    def test_expression_long_object_framework_collection(self):
        SelectionCondition.Query().Delete()

        _, expression_long1, _ = self.create_long_expression()
        _, expression_long2, _ = self.create_long_expression()
        _, expression_long3, _ = self.create_long_expression()

        with max_sql(1):
            selection_conditions = SelectionCondition.Query().Execute()

        with max_sql(3):
            self.assertEqual(
                [expression_long1, expression_long2, expression_long3],
                [
                    each.GetText("cs_sc_expression_long")
                    for each in selection_conditions
                ],
            )

    def test_expression_object_handle(self):
        keys, _, _ = self.create_long_expression()
        cdef = CDBClassDef(SelectionCondition.__maps_to__)

        with max_sql(0):
            selection_condition = getObjectHandle(cdef, **keys)

        with max_sql(1):
            self.assertEqual("", selection_condition["expression"])

    def test_expression_object_handle2(self):
        keys, _, _ = self.create_long_expression()
        cdef = CDBClassDef(SelectionCondition.__maps_to__)

        with max_sql(0):
            selection_condition = getObjectHandle(cdef, **keys)

        with max_sql(1):
            self.assertEqual("", selection_condition.getValue("expression", False))

    def test_expression_object_handle3(self):
        keys, _, _ = self.create_long_expression()
        cdef = CDBClassDef(SelectionCondition.__maps_to__)

        with max_sql(0):
            selection_condition = getObjectHandle(cdef, **keys)

        with max_sql(1):
            self.assertEqual("", selection_condition.getValue("expression", True))

    def test_expression_object_handle4(self):
        keys, expression_long, _ = self.create_long_expression()
        cdef = CDBClassDef(SelectionCondition.__maps_to__)

        with max_sql(0):
            selection_condition = getObjectHandle(cdef, **keys)

        with max_sql(2):
            self.assertEqual(
                expression_long,
                selection_condition.getValue("cs_sc_expression_long", False),
            )

    def test_expression_object_handle5(self):
        keys, expression_long, _ = self.create_long_expression()
        cdef = CDBClassDef(SelectionCondition.__maps_to__)

        with max_sql(0):
            selection_condition = getObjectHandle(cdef, **keys)

        with max_sql(2):
            self.assertEqual(
                expression_long,
                selection_condition.getValue("cs_sc_expression_long", True),
            )

    def test_expression_creation_with_modify_reset_different_expression_fields(self):
        _, expression_long, selection_condition = self.create_long_expression()

        expression_long_after_creation_count = SQLrows(
            SQLselect(
                "* FROM cs_sc_expression_long WHERE cdb_object_id='{0}'".format(
                    selection_condition.cdb_object_id
                )
            )
        )

        number_of_lines = int(
            ceil(len(expression_long) / float(get_expression_dd_field_length()))
        )
        self.assertEqual(
            number_of_lines,
            expression_long_after_creation_count,
        )
        self.assertEqual(None, selection_condition.expression)

        expression_short = "True"
        operations.operation(
            constants.kOperationModify,
            selection_condition,
            **map_expression_to_correct_attribute(expression_short)
        )
        expression_long_after_short_modify_count = SQLrows(
            SQLselect(
                "* FROM cs_sc_expression_long WHERE cdb_object_id='{0}'".format(
                    selection_condition.cdb_object_id
                )
            )
        )
        self.assertEqual(0, expression_long_after_short_modify_count)
        self.assertEqual(expression_short, selection_condition.expression)

        operations.operation(
            constants.kOperationModify,
            selection_condition,
            **map_expression_to_correct_attribute(expression_long)
        )
        expression_long_after_long_modify_count = SQLrows(
            SQLselect(
                "* FROM cs_sc_expression_long WHERE cdb_object_id='{0}'".format(
                    selection_condition.cdb_object_id
                )
            )
        )

        self.assertEqual(
            number_of_lines,
            expression_long_after_long_modify_count,
        )
        self.assertEqual("", selection_condition.expression)

    def test_expression_creation_with_modify_reset_different_expression_fields_rest_api(
        self,
    ):
        client = webtest.TestApp(RootApp)

        expression_long = '"""{0}"""'.format(
            "".join(
                random.choice(string.ascii_lowercase + string.digits)
                for _ in range(10000)
            )
        )
        keys = {
            "variability_model_id": self.variability_model.cdb_object_id,
            "ref_object_id": self.subassembly_comp.cdb_object_id,
        }

        client.post_json(
            "/api/v1/collection/cs_selection_condition",
            params=dict(keys, **map_expression_to_correct_attribute(expression_long)),
        )
        selection_condition = SelectionCondition.ByKeys(**keys)

        expression_long_after_creation_count = SQLrows(
            SQLselect(
                "* FROM cs_sc_expression_long WHERE cdb_object_id='{0}'".format(
                    selection_condition.cdb_object_id
                )
            )
        )

        number_of_lines = int(
            ceil(len(expression_long) / float(get_expression_dd_field_length()))
        )
        self.assertEqual(
            number_of_lines,
            expression_long_after_creation_count,
        )
        self.assertEqual("", selection_condition.expression)

        expression_short = "True"
        client.put_json(
            "/api/v1/collection/cs_selection_condition/{0}".format(
                selection_condition.cdb_object_id
            ),
            params=map_expression_to_correct_attribute(expression_short),
        )
        selection_condition.Reload()

        expression_long_after_short_modify_count = SQLrows(
            SQLselect(
                "* FROM cs_sc_expression_long WHERE cdb_object_id='{0}'".format(
                    selection_condition.cdb_object_id
                )
            )
        )
        self.assertEqual(0, expression_long_after_short_modify_count)
        self.assertEqual(expression_short, selection_condition.expression)

        client.put_json(
            "/api/v1/collection/cs_selection_condition/{0}".format(
                selection_condition.cdb_object_id
            ),
            params=map_expression_to_correct_attribute(expression_long),
        )
        selection_condition.Reload()

        expression_long_after_long_modify_count = SQLrows(
            SQLselect(
                "* FROM cs_sc_expression_long WHERE cdb_object_id='{0}'".format(
                    selection_condition.cdb_object_id
                )
            )
        )

        self.assertEqual(
            number_of_lines,
            expression_long_after_long_modify_count,
        )
        self.assertEqual("", selection_condition.expression)

    def assert_non_variant_driving_properties_exception(self, exception_context):
        error_message = CDBMsg.getMessage(
            "cs_variants_sc_expression_non_variant_driving_properties"
        )
        error_message = error_message.replace("\\n", "") % ""
        self.assertIn(error_message, str(exception_context.exception))

    def test_expression_create_wrong_prop(self):
        with self.assertRaises(ElementsError) as asserted_exception_context:
            operations.operation(
                constants.kOperationNew,
                SelectionCondition,
                **{
                    "variability_model_id": self.variability_model.cdb_object_id,
                    **map_expression_to_correct_attribute("abc"),
                }
            )
        self.assert_non_variant_driving_properties_exception(asserted_exception_context)

    def test_expression_long_create_wrong_prop(self):
        with self.assertRaises(ElementsError) as asserted_exception_context:
            operations.operation(
                constants.kOperationNew,
                SelectionCondition,
                **{
                    "variability_model_id": self.variability_model.cdb_object_id,
                    **map_expression_to_correct_attribute(
                        "abc == {0}".format(
                            self.generate_expression(get_expression_dd_field_length())
                        )
                    ),
                }
            )

        self.assert_non_variant_driving_properties_exception(asserted_exception_context)

    def test_expression_create_correct(self):
        expected_expression = "{0} == {1}".format(
            self.get_prop_with_class_prefix(self.prop1), self.generate_expression(10)
        )
        selection_condition = operations.operation(
            constants.kOperationNew,
            SelectionCondition,
            **{
                "variability_model_id": self.variability_model.cdb_object_id,
                **map_expression_to_correct_attribute(expected_expression),
            }
        )
        self.assertEqual(expected_expression, selection_condition.get_expression())

    def test_expression_long_create_correct(self):
        expected_expression = "{0} == {1}".format(
            self.get_prop_with_class_prefix(self.prop1),
            self.generate_expression(get_expression_dd_field_length()),
        )
        selection_condition = operations.operation(
            constants.kOperationNew,
            self.selection_condition,
            **{
                "variability_model_id": self.variability_model.cdb_object_id,
                **map_expression_to_correct_attribute(expected_expression),
            }
        )

        self.assertEqual(expected_expression, selection_condition.get_expression())

    def test_expression_modify_wrong_prop(self):
        with self.assertRaises(ElementsError) as asserted_exception_context:
            operations.operation(
                constants.kOperationModify,
                self.selection_condition,
                **{
                    "variability_model_id": self.variability_model.cdb_object_id,
                    **map_expression_to_correct_attribute("abc"),
                }
            )
        self.assert_non_variant_driving_properties_exception(asserted_exception_context)

    def test_expression_long_modify_wrong_prop(self):
        with self.assertRaises(ElementsError) as asserted_exception_context:
            operations.operation(
                constants.kOperationModify,
                self.selection_condition,
                **{
                    "variability_model_id": self.variability_model.cdb_object_id,
                    **map_expression_to_correct_attribute(
                        "abc == {0}".format(
                            self.generate_expression(get_expression_dd_field_length())
                        )
                    ),
                }
            )
        self.assert_non_variant_driving_properties_exception(asserted_exception_context)

    def test_expression_modify_correct(self):
        expected_expression = "{0} == {1}".format(
            self.get_prop_with_class_prefix(self.prop1), self.generate_expression(10)
        )
        selection_condition = operations.operation(
            constants.kOperationModify,
            self.selection_condition,
            **{
                "variability_model_id": self.variability_model.cdb_object_id,
                **map_expression_to_correct_attribute(expected_expression),
            }
        )
        self.assertEqual(expected_expression, selection_condition.get_expression())

    def test_expression_long_modify_correct(self):
        expected_expression = "{0} == {1}".format(
            self.get_prop_with_class_prefix(self.prop1),
            self.generate_expression(get_expression_dd_field_length()),
        )
        selection_condition = operations.operation(
            constants.kOperationModify,
            self.selection_condition,
            **{
                "variability_model_id": self.variability_model.cdb_object_id,
                **map_expression_to_correct_attribute(expected_expression),
            }
        )

        self.assertEqual(expected_expression, selection_condition.get_expression())

    def test_expression_copy_wrong_prop(self):
        with self.assertRaises(ElementsError) as asserted_exception_context:
            operations.operation(
                constants.kOperationCopy,
                self.selection_condition,
                **{
                    "variability_model_id": self.variability_model.cdb_object_id,
                    "ref_object_id": self.subassembly_comp.cdb_object_id,
                    **map_expression_to_correct_attribute("abc"),
                }
            )

        self.assert_non_variant_driving_properties_exception(asserted_exception_context)

    def test_expression_copy_modify_wrong_prop(self):
        with self.assertRaises(ElementsError) as asserted_exception_context:
            operations.operation(
                constants.kOperationCopy,
                self.selection_condition,
                **{
                    "variability_model_id": self.variability_model.cdb_object_id,
                    "ref_object_id": self.subassembly_comp.cdb_object_id,
                    **map_expression_to_correct_attribute(
                        "abc == {0}".format(
                            self.generate_expression(get_expression_dd_field_length())
                        )
                    ),
                }
            )
        self.assert_non_variant_driving_properties_exception(asserted_exception_context)

    def test_expression_copy_correct(self):
        expected_expression = "{0} == {1}".format(
            self.get_prop_with_class_prefix(self.prop1), self.generate_expression(10)
        )
        selection_condition = operations.operation(
            constants.kOperationCopy,
            self.selection_condition,
            **{
                "variability_model_id": self.variability_model.cdb_object_id,
                "ref_object_id": self.subassembly_comp.cdb_object_id,
                **map_expression_to_correct_attribute(expected_expression),
            }
        )
        self.assertEqual(expected_expression, selection_condition.get_expression())

    def test_expression_long_copy_correct(self):
        expected_expression = "{0} == {1}".format(
            self.get_prop_with_class_prefix(self.prop1),
            self.generate_expression(get_expression_dd_field_length()),
        )
        selection_condition = operations.operation(
            constants.kOperationCopy,
            self.selection_condition,
            **{
                "variability_model_id": self.variability_model.cdb_object_id,
                "ref_object_id": self.subassembly_comp.cdb_object_id,
                **map_expression_to_correct_attribute(expected_expression),
            }
        )

        self.assertEqual(expected_expression, selection_condition.get_expression())


class TestSelectionCondition(RollbackTestCase):
    @staticmethod
    def generate_expression(number_of_chars):
        return '"""{0}"""'.format(
            "".join(
                random.choice(string.ascii_lowercase + string.digits)
                for _ in range(max(number_of_chars - 6, 0))
            )
        )

    def generate_selection_condition(self, number_of_chars):
        expression = self.generate_expression(number_of_chars)

        is_expression_long_result = is_expression_long(expression)

        if is_expression_long_result:
            create_args = {"expression": None}
        else:
            create_args = {"expression": expression}

        create_args.update(SelectionCondition.MakeChangeControlAttributes())
        selection_condition = SelectionCondition.Create(**create_args)
        if is_expression_long_result:
            selection_condition.SetText("cs_sc_expression_long", expression)

        return expression, selection_condition

    def test_map_expression_to_correct_attribute_short(self):
        expression_to_test = self.generate_expression(get_expression_dd_field_length())

        result = map_expression_to_correct_attribute(expression_to_test)
        expected = {"expression": expression_to_test, "cs_sc_expression_long": None}

        self.assertDictEqual(expected, result)

    def test_map_expression_to_correct_attribute_long(self):
        expression_to_test = self.generate_expression(
            get_expression_dd_field_length() + 1
        )

        result = map_expression_to_correct_attribute(expression_to_test)
        expected = {"expression": None, "cs_sc_expression_long": expression_to_test}

        self.assertDictEqual(expected, result)

    def test_get_expression_short(self):
        expression_to_test, selection_condition = self.generate_selection_condition(
            get_expression_dd_field_length()
        )
        result = selection_condition.get_expression()

        self.assertEqual(expression_to_test, result)
        self.assertEqual(expression_to_test, selection_condition.expression)
        self.assertEqual("", selection_condition.GetText("cs_sc_expression_long"))

    def test_get_expression_long(self):
        expression_to_test, selection_condition = self.generate_selection_condition(
            get_expression_dd_field_length() + 1
        )
        result = selection_condition.get_expression()

        self.assertEqual(expression_to_test, result)
        self.assertEqual(None, selection_condition.expression)
        self.assertEqual(
            expression_to_test, selection_condition.GetText("cs_sc_expression_long")
        )

    def assert_syntax_error_exception(self, exception_context):
        error_message = CDBMsg.getMessage("cs_variants_sc_expression_syntax_error")
        error_message = error_message.replace("\\n", "") % ""
        self.assertIn(error_message, str(exception_context.exception))

    def test_expression_create_wrong_syntax(self):
        with self.assertRaises(ElementsError) as asserted_exception_context:
            operations.operation(
                constants.kOperationNew,
                SelectionCondition,
                **map_expression_to_correct_attribute("1abc")
            )
        self.assert_syntax_error_exception(asserted_exception_context)

    def test_expression_long_create_wrong_syntax(self):
        with self.assertRaises(ElementsError) as asserted_exception_context:
            operations.operation(
                constants.kOperationNew,
                SelectionCondition,
                **map_expression_to_correct_attribute(
                    "1abc == {0}".format(
                        self.generate_expression(get_expression_dd_field_length())
                    )
                )
            )
        self.assert_syntax_error_exception(asserted_exception_context)

    def test_expression_modify_wrong_syntax(self):
        _, selection_condition = self.generate_selection_condition(10)

        with self.assertRaises(ElementsError) as asserted_exception_context:
            operations.operation(
                constants.kOperationModify,
                selection_condition,
                **map_expression_to_correct_attribute("1abc")
            )
        self.assert_syntax_error_exception(asserted_exception_context)

    def test_expression_long_modify_wrong_syntax(self):
        _, selection_condition = self.generate_selection_condition(10)

        with self.assertRaises(ElementsError) as asserted_exception_context:
            operations.operation(
                constants.kOperationModify,
                selection_condition,
                **map_expression_to_correct_attribute(
                    "1abc == {0}".format(
                        self.generate_expression(get_expression_dd_field_length())
                    )
                )
            )
        self.assert_syntax_error_exception(asserted_exception_context)

    def test_expression_copy_wrong_syntax(self):
        _, selection_condition = self.generate_selection_condition(10)

        with self.assertRaises(ElementsError) as asserted_exception_context:
            operations.operation(
                constants.kOperationCopy,
                selection_condition,
                **map_expression_to_correct_attribute("1abc")
            )
        self.assert_syntax_error_exception(asserted_exception_context)

    def test_expression_long_copy_wrong_syntax(self):
        _, selection_condition = self.generate_selection_condition(10)

        with self.assertRaises(ElementsError) as asserted_exception_context:
            operations.operation(
                constants.kOperationCopy,
                selection_condition,
                **map_expression_to_correct_attribute(
                    "1abc == {0}".format(
                        self.generate_expression(get_expression_dd_field_length())
                    )
                )
            )
        self.assert_syntax_error_exception(asserted_exception_context)

    @skip_dbms(sqlapi.DBMS_SQLITE)
    def test_indexes_on_table(self):
        table = ddl.Table(SelectionCondition.__maps_to__)
        indices = ddl.Index.find_all_indices(table)

        expected_indices = ["ref_object_id", "variability_model_id"]

        while expected_indices:
            current_expected_index = expected_indices.pop()

            found = False
            for each in indices:
                if each.unique:
                    continue

                if len(each.columns) == 1 and each.columns[0] == current_expected_index:
                    found = True
                    break

            if not found:
                raise Exception(  # pylint: disable=broad-exception-raised
                    "Expected index not found: {0}".format(current_expected_index)
                )
