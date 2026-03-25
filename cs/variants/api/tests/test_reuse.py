# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

# pylint: disable=protected-access

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb.testcase import max_sql
from cs.variants.api import reuse
from cs.variants.api.tests import maxbom_deep_wide_constants
from cs.variants.api.tests.reinstantiate_test_case import ReinstantiateTestCase
from cs.variants.api.tests.reuse_test_case import ReuseTestCase
from cs.variants.api.variant_bom_node import StructureCompareData, VariantBomNode
from cs.vp.bom import AssemblyComponent
from cs.vp.items import Item


def test_get_first_level_no_bom_items():
    """part has no bom_items on level 1"""
    item = Item.ByKeys(**ReinstantiateTestCase.maxbom_subassembly2_part2_keys)
    attributes_to_load = ["teilenummer", "t_index"]

    with max_sql(1):
        first_level = reuse._get_first_level(item, attributes_to_load, [])

    assert not first_level


def test_get_first_level_with_structure():
    """part has bom_items"""
    item = Item.ByKeys(
        teilenummer=ReinstantiateTestCase.maxbom_subassembly1_teilenummer,
        t_index="",
    )
    attributes_to_load = ["teilenummer", "t_index"]
    occ_attributes_to_load = ["occurrence_id"]

    expected_structure = {
        ("9508582", ""): [("VAR_TEST_REINSTANTIATE_SUBASSEMBLY_1_P1_OC0",)],
        ("9508583", ""): [
            ("VAR_TEST_REINSTANTIATE_SUBASSEMBLY_1_P2_OC0",),
            ("VAR_TEST_REINSTANTIATE_SUBASSEMBLY_1_P2_OC1",),
        ],
    }

    with max_sql(2):
        first_level = reuse._get_first_level(
            item, attributes_to_load, occ_attributes_to_load
        )
    assert set(first_level.keys()) == set(expected_structure.keys())

    assert all(
        set(first_level[key]) == set(value) for key, value in expected_structure.items()
    )


def test_get_first_level_with_deep_structure():
    """make sure only the first level is loaded"""
    item = Item.ByKeys(teilenummer=ReinstantiateTestCase.maxbom_teilenummer, t_index="")
    attributes_to_load = ["teilenummer", "t_index"]
    occ_attributes_to_load = ["occurrence_id"]

    expected_structure = {
        ("9508576", ""): [("VAR_TEST_REINSTANTIATE_PART_1_OC0",)],
        ("9508580", ""): [
            ("VAR_TEST_REINSTANTIATE_PART_2_OC0",),
            ("VAR_TEST_REINSTANTIATE_PART_2_OC1",),
        ],
        ("9508579", ""): [("VAR_TEST_REINSTANTIATE_SUBASSEMBLY_1_OC0",)],
        ("9508581", ""): [
            ("VAR_TEST_REINSTANTIATE_SUBASSEMBLY_2_OC0",),
            ("VAR_TEST_REINSTANTIATE_SUBASSEMBLY_2_OC1",),
        ],
    }
    with max_sql(2):
        first_level = reuse._get_first_level(
            item, attributes_to_load, occ_attributes_to_load
        )
    assert set(first_level.keys()) == set(expected_structure.keys())
    assert all(
        set(first_level[key]) == set(value) for key, value in expected_structure.items()
    )


def test_get_first_level_not_existing_part():
    """empty list on non-existing part"""

    class MyItem:
        teilenummer = "XXX"
        t_index = ""

    attributes_to_load = ["teilenummer", "t_index"]
    first_level = reuse._get_first_level(MyItem(), attributes_to_load, [])
    assert not first_level


class TestReuseCompareStructure(ReuseTestCase):
    @staticmethod
    def create_structure_compare_data():
        dummy_node = VariantBomNode(None)
        structure_to_match = StructureCompareData()
        structure_to_match.bom_item_attributes = list(
            dummy_node.remove_assembly_keys(dummy_node.bom_item_keys)
        )
        structure_to_match.occurrence_only_attributes = dummy_node.occurrence_keys[:]
        structure_to_match.occurrence_attributes = (
            structure_to_match.bom_item_attributes
        )

        return structure_to_match

    def test_match_without_occurrence(self):
        self.remove_all_occurrences()
        keys_to_check = ("9508609", "")
        structure_to_match = self.create_structure_compare_data()
        structure_to_match.item_structure = [keys_to_check]
        list_of_items = [self.t9508608_id, self.t9508614_id]

        result = reuse.compare_structure(structure_to_match, list_of_items)
        self.assertIsNotNone(result)
        self.assertEqual(result.teilenummer, "9508608")

    def test_no_match_without_occurrence(self):
        self.remove_all_occurrences()
        keys_to_check = ("x", "")
        structure_to_match = self.create_structure_compare_data()
        structure_to_match.item_structure = keys_to_check
        list_of_items = [self.t9508608_id, self.t9508614_id]

        result = reuse.compare_structure(structure_to_match, list_of_items)
        self.assertIsNone(result)

    def test_match_with_occurrence(self):
        keys_to_check = ("9508609", "")
        structure_to_match = self.create_structure_compare_data()
        structure_to_match.item_structure = [keys_to_check]
        list_of_items = [self.t9508608_id, self.t9508614_id]

        bom_item = AssemblyComponent.ByKeys(cdb_object_id=self.b_t9508608_9508607)
        self.assertIsNotNone(bom_item)
        self.assertEqual(len(bom_item.Occurrences), 1)
        structure_to_match.occ_structure[keys_to_check] = [
            (
                "VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL2_OC1",
                "VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL2_OC1.asm",
            ),
            (
                "VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL2_OC2",
                "VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL2_OC2.asm",
            ),
        ]
        result = reuse.compare_structure(structure_to_match, list_of_items)
        self.assertIsNotNone(result)
        self.assertEqual(result.teilenummer, "9508608")

    def test_no_match_with_occurrence(self):
        keys_to_check = ("9508609", "")
        structure_to_match = self.create_structure_compare_data()
        structure_to_match.item_structure = [keys_to_check]
        list_of_items = [self.t9508608_id, self.t9508614_id]

        bom_item = AssemblyComponent.ByKeys(cdb_object_id=self.b_t9508609_9508608)
        self.assertIsNotNone(bom_item)
        self.assertEqual(len(bom_item.Occurrences), 2)
        bom_item.Occurrences.Delete()
        self.assertEqual(len(bom_item.Occurrences), 0)

        structure_to_match.occ_structure[keys_to_check] = [
            (
                "VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL2_OC1",
                "VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL2_OC1.asm",
            ),
            (
                "VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL2_OC2",
                "VAR_TEST_MAXBOM_DEEP_SUBASSEMBLY_LEVEL2_OC2.asm",
            ),
        ]

        result = reuse.compare_structure(structure_to_match, list_of_items)
        self.assertIsNone(result)

    def test_all_occ_must_match(self):
        """make sure we check all occ from all bom_items"""
        keys_to_check1 = ("9508627", "")
        keys_to_check2 = ("9508628", "")
        structure_to_match = self.create_structure_compare_data()
        structure_to_match.item_structure = [keys_to_check1, keys_to_check2]
        list_of_items = [maxbom_deep_wide_constants.t9508635_id]

        # prechecks (make sure we have a match on the first occurrence)
        item = Item.ByKeys(cdb_object_id=maxbom_deep_wide_constants.t9508635_id)
        self.assertIsNotNone(item)
        bom_item_27 = item.Components.KeywordQuery(teilenummer="9508627")[0]
        self.assertEqual(len(bom_item_27.Occurrences), 1)
        occ = bom_item_27.Occurrences[0]
        self.assertEqual(occ.occurrence_id, "VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I1_OC0")

        structure_to_match.occ_structure[keys_to_check1] = [
            (
                "VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I1_OC0",
                "VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I1_OC0.asm",
            )
        ]
        structure_to_match.occ_structure[keys_to_check2] = [
            (
                "xxx",
                "xxx.asm",
            )
        ]
        result = reuse.compare_structure(structure_to_match, list_of_items)
        self.assertIsNone(result)
