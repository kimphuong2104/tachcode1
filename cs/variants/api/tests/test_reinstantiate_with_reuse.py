# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

# pylint: disable=protected-access

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from copy import deepcopy

from cs.variants import VariantSubPart
from cs.variants.api import helpers, reinstantiate_parts
from cs.variants.api.instantiate_options import InstantiateOptions
from cs.variants.api.tests.reinstantiate_test_case import ReinstantiateTestCase
from cs.variants.api.tests.subassembly_structure import SubassemblyStructure
from cs.variants.selection_condition import SelectionCondition
from cs.vp.bom.tests import generateAssemblyComponent


class TestReinstantiateWithReuse(ReinstantiateTestCase):
    def tearDown(self):
        super().tearDown()
        helpers.REUSE_ENABLED = False
        InstantiateOptions.ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM = self.options

    def setUp(self):
        super().setUp()
        helpers.REUSE_ENABLED = True
        self.options = InstantiateOptions.ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM
        InstantiateOptions.ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM = [
            "netto_laenge",
        ]

    def test_reinstantiate_simple_after_removing_selection_conditions(self):
        self.assert_subassembly_structure(
            self.expected_var1_part3_structure,
            self.var1_part3,
        )

        expected_structure = SubassemblyStructure(
            self.var1_part3_keys, children=self.maxbom_children
        )

        SelectionCondition.Query().Delete()
        reinstantiate_parts([self.var1_part3])

        self.assert_subassembly_structure(
            expected_structure,
            self.var1_part3,
        )
        self.assertRelationshipToMaxBOM(self.var1_part3, self.maxbom, self.var1)

    def test_reinstantiate_simple_no_change(self):
        self.assert_subassembly_structure(
            self.expected_var1_part3_structure,
            self.var1_part3,
        )

        reinstantiate_parts([self.var1_part3])

        self.assert_subassembly_structure(
            self.expected_var1_part3_structure,
            self.var1_part3,
        )
        self.assertRelationshipToMaxBOM(self.var1_part3, self.maxbom, self.var1)

    def test_reinstantiate_adapt_to_maxbom_attribute_changes_recursive(self):
        self.assert_subassembly_structure(
            self.expected_var1_part3_structure, self.var1_part3, assert_occurrences=True
        )

        self.update_bom_item_attributes(
            self.maxbom, {"menge": 42, "netto_laenge": 42}, recursive=True
        )

        reinstantiate_parts([self.var1_part3])

        expected_structure = deepcopy(self.expected_var1_part3_structure)
        # Because occurrences exists menge will be modified by them
        expected_structure.update_keys(
            bom_item_keys={"!menge": 42, "netto_laenge": 42}, recursive=True
        )

        self.assert_subassembly_structure(
            expected_structure, self.var1_part3, assert_occurrences=True
        )
        self.assertRelationshipToMaxBOM(self.var1_part3, self.maxbom, self.var1)

    def test_reinstantiate_adapt_to_maxbom_attribute_changes_recursive_without_occurrence(
        self,
    ):
        self.remove_all_occurrences()

        self.assert_subassembly_structure(
            self.expected_var1_part3_structure,
            self.var1_part3,
        )

        self.update_bom_item_attributes(
            self.maxbom, {"menge": 42, "netto_laenge": 42}, recursive=True
        )

        sub_part = VariantSubPart.ByKeys(
            instantiated_of_part_object_id=self.maxbom_subassembly1_id,
            part_object_id=self.var1_part3_subassembly1_id,
        )
        self.assertIsNotNone(sub_part)
        old_checksum = sub_part.structure_checksum

        reinstantiate_parts([self.var1_part3])

        expected_structure = deepcopy(self.expected_var1_part3_structure)
        expected_structure.update_keys(
            bom_item_keys={"menge": 42, "netto_laenge": 42}, recursive=True
        )

        self.assert_subassembly_structure(
            expected_structure,
            self.var1_part3,
        )

        sub_part.Reload()
        self.assertNotEqual(old_checksum, sub_part.structure_checksum)
        self.assertRelationshipToMaxBOM(self.var1_part3, self.maxbom, self.var1)

    def test_reinstantiate_adapt_to_maxbom_attribute_changes(self):
        self.assert_subassembly_structure(
            self.expected_var1_part3_structure,
            self.var1_part3,
        )

        self.update_bom_item_attributes(
            self.maxbom, {"menge": 42, "netto_laenge": 42}, recursive=False
        )

        reinstantiate_parts([self.var1_part3])

        expected_structure = deepcopy(self.expected_var1_part3_structure)
        expected_structure.update_keys(
            bom_item_keys={"menge": 42, "netto_laenge": 42}, recursive=False
        )

        self.assert_subassembly_structure(
            expected_structure,
            self.var1_part3,
        )
        self.assertRelationshipToMaxBOM(self.var1_part3, self.maxbom, self.var1)

    def test_reinstantiate_adapt_to_maxbom_attribute_changes_only_deep(self):
        self.assert_subassembly_structure(
            self.expected_var1_part3_structure, self.var1_part3, assert_occurrences=True
        )

        self.update_bom_item_attributes(
            self.subassembly1, {"menge": 42, "netto_laenge": 42}, recursive=False
        )

        reinstantiate_parts([self.var1_part3])

        expected_structure = deepcopy(self.expected_var1_part3_structure)
        for each in expected_structure.children[1].children:
            # Because occurrences exists menge will be modified by them
            each.update_keys(
                bom_item_keys={"!menge": 42, "netto_laenge": 42}, recursive=False
            )

        self.assert_subassembly_structure(
            expected_structure, self.var1_part3, assert_occurrences=True
        )
        self.assertRelationshipToMaxBOM(self.var1_part3, self.maxbom, self.var1)

    def test_reinstantiate_adapt_to_maxbom_attribute_changes_only_deep_without_occurrences(
        self,
    ):
        self.remove_all_occurrences()

        self.assert_subassembly_structure(
            self.expected_var1_part3_structure,
            self.var1_part3,
        )

        self.update_bom_item_attributes(
            self.subassembly1, {"menge": 42, "netto_laenge": 42}, recursive=False
        )

        sub_part = VariantSubPart.ByKeys(
            instantiated_of_part_object_id=self.maxbom_subassembly1_id,
            part_object_id=self.var1_part3_subassembly1_id,
        )
        self.assertIsNotNone(sub_part)
        old_checksum = sub_part.structure_checksum

        reinstantiate_parts([self.var1_part3])

        expected_structure = deepcopy(self.expected_var1_part3_structure)
        for each in expected_structure.children[1].children:
            each.update_keys(
                bom_item_keys={"menge": 42, "netto_laenge": 42}, recursive=False
            )

        self.assert_subassembly_structure(
            expected_structure,
            self.var1_part3,
        )
        sub_part.Reload()
        self.assertNotEqual(old_checksum, sub_part.structure_checksum)
        self.assertRelationshipToMaxBOM(self.var1_part3, self.maxbom, self.var1)

    def test_reinstantiate_switch_to_new_index_bom_var1(self):
        """
        reinstantiate_parts method will recompute the 100% product structure for a new indexed bom variant 1
        """

        # New index MaxBOM should show change
        expected_structure = SubassemblyStructure(
            self.var1_part3_keys,
            children=[
                self.expected_maxbom_part1,
                self.expected_maxbom_part2,
                SubassemblyStructure(
                    {
                        "teilenummer": self.check_teilenummer_not_exists,
                        "t_index": "",
                        "cdb_object_id": self.check_object_id_not_exists,
                    },
                    children=[
                        self.expected_maxbom_subassembly1_part1,
                        self.expected_maxbom_subassembly1_part2,
                    ],
                ),
                self.expected_indexed_subassembly2_structure,
            ],
        )

        reinstantiate_parts([self.var1_part3], maxbom=self.maxbom_indexed)
        self.assert_subassembly_structure(expected_structure, self.var1_part3)
        self.assertRelationshipToMaxBOM(
            self.var1_part3,
            self.maxbom_indexed,
            self.var1,
            original_max_bom=self.maxbom,
        )

    def test_reinstantiate_switch_to_new_index_bom_var2self(self):
        """
        reinstantiate_parts method will recompute the 100% product structure for a new indexed bom variant 2
        """

        # New index MaxBOM should show change
        expected_structure = SubassemblyStructure(
            self.var2_part3_keys,
            children=[
                self.expected_maxbom_part2,
                SubassemblyStructure(
                    {
                        "teilenummer": self.check_teilenummer_not_exists,
                        "t_index": "",
                        "cdb_object_id": self.check_object_id_not_exists,
                    },
                    children=[
                        self.expected_maxbom_subassembly1_part2,
                    ],
                ),
            ],
        )

        reinstantiate_parts([self.var2_part3], maxbom=self.maxbom_indexed)
        self.assert_subassembly_structure(expected_structure, self.var2_part3)
        self.assertRelationshipToMaxBOM(
            self.var2_part3,
            self.maxbom_indexed,
            self.var2,
            original_max_bom=self.maxbom,
        )

    def test_reinstantiate_multiple_to_new_index_bom(self):
        """
        reinstantiate_parts method will recompute the 100% product structure
        for multiple parts with new indexed bom
        """
        expected_structure_var1_part3 = SubassemblyStructure(
            self.var1_part3_keys,
            children=[
                self.expected_maxbom_part1,
                self.expected_maxbom_part2,
                SubassemblyStructure(
                    {
                        "teilenummer": self.check_teilenummer_not_exists,
                        "t_index": "",
                        "cdb_object_id": self.check_object_id_not_exists,
                    },
                    children=[
                        self.expected_maxbom_subassembly1_part1,
                        self.expected_maxbom_subassembly1_part2,
                    ],
                ),
                self.expected_indexed_subassembly2_structure,
            ],
        )

        expected_structure_var2_part3 = SubassemblyStructure(
            self.var2_part3_keys,
            children=[
                self.expected_maxbom_part2,
                SubassemblyStructure(
                    {
                        "teilenummer": self.check_teilenummer_not_exists,
                        "t_index": "",
                        "cdb_object_id": self.check_object_id_not_exists,
                    },
                    children=[self.expected_maxbom_subassembly1_part2],
                ),
            ],
        )

        reinstantiate_parts(
            [self.var1_part3, self.var2_part3], maxbom=self.maxbom_indexed
        )

        self.assert_subassembly_structure(
            expected_structure_var1_part3, self.var1_part3
        )
        self.assertRelationshipToMaxBOM(
            self.var1_part3,
            self.maxbom_indexed,
            self.var1,
            original_max_bom=self.maxbom,
        )

        self.assert_subassembly_structure(
            expected_structure_var2_part3, self.var2_part3
        )
        self.assertRelationshipToMaxBOM(
            self.var2_part3,
            self.maxbom_indexed,
            self.var2,
            original_max_bom=self.maxbom,
        )

    def test_reinstantiate_simple_bom_item_added_in_instantiated_part(self):
        """
        An manual added bom_item in an instanced part will get removed if reinstantiate is done
        """
        new_bom_item = generateAssemblyComponent(self.var1_part3, position=999)
        self.var1_part3.Reload()

        expected_after_added_bom_item = SubassemblyStructure(
            self.var1_part3_keys,
            children=[
                self.expected_maxbom_part2,
                self.expected_var1_part3_subassembly1_structure,
                SubassemblyStructure(
                    {
                        "teilenummer": new_bom_item.teilenummer,
                        "t_index": new_bom_item.t_index,
                    },
                    bom_item_keys={
                        "baugruppe": self.var1_part3.teilenummer,
                        "b_index": self.var1_part3.t_index,
                    },
                ),
            ],
        )

        self.assert_subassembly_structure(
            expected_after_added_bom_item,
            self.var1_part3,
        )

        reinstantiate_parts([self.var1_part3])

        self.assert_subassembly_structure(
            self.expected_var1_part3_structure,
            self.var1_part3,
        )
        self.assertRelationshipToMaxBOM(self.var1_part3, self.maxbom, self.var1)

    def test_reinstantiate_simple_bom_item_removed_in_instantiated_part(self):
        """
        An manual removed bom_item in an instanced part will get readded if reinstantiate is done
        """
        self.var1_part3.Components.KeywordQuery(position=20).Delete()

        expected_after_removed_bom_item = SubassemblyStructure(
            self.var1_part3_keys,
            children=[self.expected_var1_part3_subassembly1_structure],
        )

        self.assert_subassembly_structure(
            expected_after_removed_bom_item,
            self.var1_part3,
        )

        reinstantiate_parts([self.var1_part3])

        # Because we deleted the bom_item we need to get a new id
        expected_structure = deepcopy(self.expected_var1_part3_structure)
        expected_subassembly_structure_bom_item_keys = expected_structure.children[
            0
        ].bom_item_keys
        expected_subassembly_structure_bom_item_keys[
            "!cdb_object_id"
        ] = expected_subassembly_structure_bom_item_keys.pop("cdb_object_id")

        self.assert_subassembly_structure(
            expected_structure,
            self.var1_part3,
        )
        self.assertRelationshipToMaxBOM(self.var1_part3, self.maxbom, self.var1)
