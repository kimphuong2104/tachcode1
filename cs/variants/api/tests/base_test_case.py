#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from operator import attrgetter
from typing import Any

from cdb import testcase
from cdb.sqlapi import SQLdelete
from cs.variants import VariantPart
from cs.variants.api.tests import subassembly_structure
from cs.variants.tests.common import ensure_running_classification_core
from cs.vp import items
from cs.vp.bom import AssemblyComponent


class BaseTestCase(testcase.RollbackTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        ensure_running_classification_core()

    def setUp(self):
        super().setUp()
        self.all_items = items.Item.Query()
        self.teilenummer_lookup = self.all_items.teilenummer
        self.cdb_object_id_lookup = self.all_items.cdb_object_id

    def check_teilenummer_not_exists(self, value):
        return value not in self.teilenummer_lookup

    def check_object_id_not_exists(self, value):
        return value not in self.cdb_object_id_lookup

    def assert_keys(
        self, expected_keys: subassembly_structure.KeysType, object_to_check: Any
    ) -> None:
        for each_key, each_value in expected_keys.items():
            if each_key.startswith("!"):
                object_to_check_key_value = object_to_check[each_key[1:]]

                if callable(each_value):
                    self.assertTrue(
                        each_value(object_to_check_key_value),
                        msg=f"Callable returned False for key '{each_key}' "
                        f"and value: '{object_to_check_key_value}'",
                    )
                else:
                    self.assertNotEqual(
                        object_to_check_key_value,
                        each_value,
                        msg=f"Key should not be equal '{each_key}' "
                        f"has value: {object_to_check_key_value} not Expected: {each_value} "
                        f"for object: '{object_to_check}'",
                    )
            else:
                object_to_check_key_value = object_to_check[each_key]

                if callable(each_value):
                    self.assertTrue(
                        each_value(object_to_check_key_value),
                        msg=f"Callable returned False for key '{each_key}' "
                        f"and value: '{object_to_check_key_value}'",
                    )
                else:
                    self.assertEqual(
                        object_to_check_key_value,
                        each_value,
                        msg=f"Key should be equal '{each_key}' has value: {object_to_check_key_value} "
                        f"Expected: {each_value} for object: '{object_to_check}'",
                    )

    def assert_subassembly_structure(
        self,
        expected_subassembly_structure: subassembly_structure.SubassemblyStructure,
        item_or_bom_item_to_check: items.Item | AssemblyComponent,
        assert_occurrences: bool = False,
    ) -> None:
        if isinstance(item_or_bom_item_to_check, items.Item):
            item_to_check = item_or_bom_item_to_check
        elif isinstance(item_or_bom_item_to_check, AssemblyComponent):
            item_to_check = item_or_bom_item_to_check.Item
            if expected_subassembly_structure.bom_item_keys is not None:
                self.assert_keys(
                    expected_subassembly_structure.bom_item_keys,
                    item_or_bom_item_to_check,
                )
        else:
            raise TypeError(
                "Not supported type: {0}".format(type(item_or_bom_item_to_check))
            )

        self.assert_keys(expected_subassembly_structure.item_keys, item_to_check)
        item_to_check_components = item_to_check.Components.Execute()

        expected_children_length = len(expected_subassembly_structure.children)
        children_length = len(item_to_check_components)

        self.assertEqual(
            expected_children_length,
            children_length,
            msg="Found # of subassembly ({2}) children: {0} Expected: {1}".format(
                children_length,
                expected_children_length,
                expected_subassembly_structure.item_keys,
            ),
        )

        for index, each in enumerate(expected_subassembly_structure.children):
            bom_item = item_to_check_components[index]
            bom_item.Reload()
            bom_item.Item.Reload()

            if each.children:
                self.assert_subassembly_structure(
                    each, bom_item, assert_occurrences=assert_occurrences
                )
            else:
                if each.bom_item_keys is not None:
                    self.assert_keys(
                        each.bom_item_keys,
                        bom_item,
                    )
                self.assert_keys(each.item_keys, bom_item.Item)

            if assert_occurrences:
                self.assertEqual(
                    len(each.occurrence_keys),
                    bom_item.menge,
                    msg="Menge is {0} but is expecting {1} occurrences for bom item {2}".format(
                        bom_item.menge, len(each.occurrence_keys), each
                    ),
                )

                bom_item_occurrences = sorted(
                    bom_item.Occurrences, key=attrgetter("occurrence_id")
                )
                self.assertEqual(
                    len(each.occurrence_keys),
                    len(bom_item_occurrences),
                    msg="Found # of bom_item_occurrences: {0} Expected: {1} for (bom)item {2}".format(
                        len(bom_item_occurrences),
                        len(each.occurrence_keys),
                        bom_item.teilenummer,
                    ),
                )

                for occurrence_index, occurrence in enumerate(bom_item_occurrences):
                    self.assert_keys(each.occurrence_keys[occurrence_index], occurrence)

    def assertRelationshipToMaxBOM(
        self, instance, max_bom, variant, original_max_bom=None
    ):
        instance.Reload()
        expected_cdb_copy_of_item_id = (
            max_bom.cdb_object_id
            if original_max_bom is None
            else original_max_bom.cdb_object_id
        )
        self.assertEqual(expected_cdb_copy_of_item_id, instance.cdb_copy_of_item_id)
        variant_parts = VariantPart.KeywordQuery(
            variability_model_id=variant.variability_model_id,
            variant_id=variant.id,
            maxbom_teilenummer=max_bom.teilenummer,
            maxbom_t_index=max_bom.t_index,
            teilenummer=instance.teilenummer,
            t_index=instance.t_index,
        )
        self.assertEqual(1, len(variant_parts), "No variant part found")

    def assertNotExistingVariantPart(self, instance, max_bom, variant):
        variant_parts = VariantPart.KeywordQuery(
            variability_model_id=variant.variability_model_id,
            variant_id=variant.id,
            maxbom_teilenummer=max_bom.teilenummer,
            maxbom_t_index=max_bom.t_index,
            teilenummer=instance.teilenummer,
            t_index=instance.t_index,
        )
        self.assertEqual(
            0, len(variant_parts), "No variant part expected but was found"
        )

    @staticmethod
    def remove_occurrences_selection_conditions():
        SQLdelete(
            """
        FROM cs_selection_condition
        WHERE cs_selection_condition.ref_object_id IN (SELECT cdb_object_id FROM bom_item_occurrence)
        """
        )

    @staticmethod
    def remove_all_selection_conditions():
        SQLdelete(
            """
        FROM cs_selection_condition
        """
        )

    @staticmethod
    def remove_bom_item_selection_conditions():
        SQLdelete(
            """
        FROM cs_selection_condition
        WHERE cs_selection_condition.ref_object_id IN (SELECT cdb_object_id FROM einzelteile)
        """
        )

    @staticmethod
    def remove_all_occurrences():
        SQLdelete(
            """
        FROM bom_item_occurrence
        """
        )

    def assert_bom_items_count(self, item_to_check, expected_count):
        self.assertEqual(expected_count, len(item_to_check.Components))

    def update_bom_item_attributes(self, item, attributes, recursive=False):
        item.Components.Update(**attributes)
        if recursive:
            for each in item.Components:
                self.update_bom_item_attributes(
                    each.Item, attributes, recursive=recursive
                )
