#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
import hashlib

from cdb import testcase
from cdb.testcase import max_sql
from cs.variants import Variant
from cs.variants.api.instantiate import _update_old_bom_item_attributes
from cs.variants.api.instantiate_lookup import InstantiateLookup
from cs.variants.api.instantiate_options import InstantiateOptions
from cs.variants.api.tests import maxbom_deep_wide_constants
from cs.variants.api.tests.reuse_test_case import ReuseTestCase
from cs.variants.api.variant_bom_node import VariantBomNode, get_key_dict
from cs.variants.items import AssemblyComponent
from cs.vp import items


class TestVariantBomNode(testcase.RollbackTestCase):
    def setUp(self):
        super().setUp()
        self.node = VariantBomNode(None)
        self.node.children = [
            VariantBomNode(x)
            for x in AssemblyComponent.KeywordQuery(
                baugruppe="9508391", b_index=""
            ).Execute()
        ]
        self.assertEqual(len(self.node.children), 13)

        self.comp_to_find = AssemblyComponent.ByKeys(
            baugruppe="9508391", b_index="", position=20
        )
        self.assertIsNotNone(self.comp_to_find)
        self.keys = get_key_dict(self.comp_to_find)

        self.options = InstantiateOptions.ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM
        InstantiateOptions.ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM = [
            "netto_laenge",
        ]

    def tearDown(self):
        super().tearDown()
        InstantiateOptions.ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM = self.options

    def test_find_children_by_keys(self):
        with max_sql(0):
            result = self.node.find_children_by_keys(self.keys)

        self.assertEqual(len(result), 1)
        self.assertDictEqual(result[0].value.__dict__, self.comp_to_find.__dict__)

    def test_find_non_existing_pos(self):
        self.keys["teilenummer"] = 999
        with max_sql(0):
            result = self.node.find_children_by_keys(self.keys)
        self.assertEqual(len(result), 0)

    def test_find_missing_key(self):
        del self.keys["teilenummer"]
        with self.assertRaises(KeyError):
            self.node.find_children_by_keys(self.keys)

    def test_identification_key_values_as_tuple_empty_blacklist(self):
        bom_item = AssemblyComponent.ByKeys(
            baugruppe="9508619", b_index="", teilenummer="9508620", t_index=""
        )
        node = VariantBomNode(bom_item)
        expected_result = ("9508619", "", "9508620", "", 1.0)
        result = node.get_identification_key_values()

        self.assertTupleEqual(result, expected_result)

    def test_identification_key_values_as_tuple_with_occurrences(self):
        bom_item = AssemblyComponent.ByKeys(
            baugruppe="9508619", b_index="", teilenummer="9508620", t_index=""
        )
        node = VariantBomNode(bom_item)
        node.has_occurrences = True
        expected_result = ("9508619", "", "9508620", "")
        result = node.get_identification_key_values()

        self.assertTupleEqual(result, expected_result)

    def test_update_old_bom_item_attributes_no_changes(self):
        t9508620 = AssemblyComponent.ByKeys(
            cdb_object_id=maxbom_deep_wide_constants.t9508620_bom_item_object_id
        )
        t9508630 = AssemblyComponent.ByKeys(
            cdb_object_id=maxbom_deep_wide_constants.t9508630_bom_item_object_id
        )
        bom_node = VariantBomNode(t9508620)
        bom_node.ref_to_bom_item = t9508630

        with max_sql(0):
            _update_old_bom_item_attributes(bom_node)

    def test_occ_only_keys(self):
        """return only occurrence specific keys (without bom_node keys)

        This test exist to bring in mind:
            do not change the keys without knowing what are you doing!
        """
        expected_result = ["occurrence_id", "assembly_path"]

        result = VariantBomNode.occurrence_keys

        self.assertListEqual(result, expected_result)

    def test_update_old_bom_item_attributes_changes(self):
        t9508620 = AssemblyComponent.ByKeys(
            cdb_object_id=maxbom_deep_wide_constants.t9508620_bom_item_object_id
        )
        t9508620.netto_laenge = 10
        t9508620.Reload()
        t9508630 = AssemblyComponent.ByKeys(
            cdb_object_id=maxbom_deep_wide_constants.t9508630_bom_item_object_id
        )
        t9508630.Reload()
        self.assertNotEqual(t9508630.netto_laenge, 10)

        bom_node = VariantBomNode(t9508620)
        bom_node.ref_to_bom_item = t9508630

        with max_sql(1):
            _update_old_bom_item_attributes(bom_node)

        t9508630.Reload()
        self.assertEqual(t9508630.netto_laenge, 10)


class VariantBomNodeMock(VariantBomNode):
    def __init__(self, value):
        super().__init__(value)
        self.bom_item_keys = ["teilenummer"]


class TestVariantBomNodeChecksum(testcase.RollbackTestCase):
    EMPTY_LIST_CHECKSUM = "d41d8cd98f00b204e9800998ecf8427e"

    def create_checksum(self, list_of_strings):
        """
        Used to calculate the expected checksum

        This is a copy of the implementation of 'checksum' from the VariantBomNode class
        We dont want to override the original method.

        :param list_of_strings:
        :return:
        """
        return hashlib.md5(  # nosec
            "".join(list_of_strings).encode("utf-8")
        ).hexdigest()

    def test_checksum_with_menge(self):
        root_node = VariantBomNodeMock({"teilenummer": "root"})
        child1_node = VariantBomNodeMock({"teilenummer": "child1", "menge": 10})
        child1_node.has_occurrences = False
        root_node.children.append(child1_node)

        expected_checksum = self.create_checksum(["child110", self.create_checksum([])])
        self.assertEqual(root_node.checksum, expected_checksum)

    def test_checksum_without_menge(self):
        root_node = VariantBomNodeMock({"teilenummer": "root"})
        child1_node = VariantBomNodeMock({"teilenummer": "child1"})
        child1_node.has_occurrences = True
        root_node.children.append(child1_node)

        expected_checksum = self.create_checksum(["child1", self.create_checksum([])])
        self.assertEqual(root_node.checksum, expected_checksum)

    def test_checksum_deep(self):
        """
        root_node
            |-  child1
                |-  child2
                    |-  child3

        checksum of child1 is attributes from child2 and the checksum of child2

        :return:
        """
        root_node = VariantBomNodeMock({"teilenummer": "root"})
        child1_node = VariantBomNodeMock({"teilenummer": "child1", "menge": 10})
        child2_node = VariantBomNodeMock({"teilenummer": "child2", "menge": 10})
        child3_node = VariantBomNodeMock({"teilenummer": "child3", "menge": 10})

        child2_node.children.append(child3_node)
        child1_node.children.append(child2_node)
        root_node.children.append(child1_node)

        child3_node_exp_checksum = self.create_checksum([])
        self.assertEqual(child3_node.checksum, child3_node_exp_checksum)

        child2_node_exp_checksum = self.create_checksum(
            ["child310", self.create_checksum([])]
        )
        self.assertEqual(child2_node.checksum, child2_node_exp_checksum)

        child1_node_exp_checksum = self.create_checksum(
            ["child210", child2_node_exp_checksum]
        )
        self.assertEqual(child1_node.checksum, child1_node_exp_checksum)

    def test_no_checksum_for_empty_list(self):
        """no children return the checklist for an empty list"""
        bom_node = VariantBomNode(None)
        assert bom_node.checksum == self.EMPTY_LIST_CHECKSUM

    def test_raw_checksum(self):
        """
        Checking the checksum functionality with human-readable strings

        9508625@ - VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2 Variant(2@1771fe02-f5e3-11eb-923d-f875a45b4131)
         +- 9508627@ - VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I1
         |  +- > VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I1_OC0
         +- 9508628@ - VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2
            +- > VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC1


        """
        maxbom_deep_wide = items.Item.ByKeys(**maxbom_deep_wide_constants.t9508625_keys)
        var2 = Variant.ByKeys(
            variability_model_id=ReuseTestCase.variability_model_id_multi, id=2
        )

        expected_result = [
            "95086259508627",  # first bom item
            "VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I1_OC0VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I1_OC0.asm",
            self.EMPTY_LIST_CHECKSUM,
            "95086259508628",  # second bom item
            "VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC1VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC1.asm",
            self.EMPTY_LIST_CHECKSUM,
        ]

        lookup = InstantiateLookup(maxbom_deep_wide, var2)
        lookup.build_variant_bom()

        result = lookup.variant_bom.calculate_checksum()
        assert result == expected_result
