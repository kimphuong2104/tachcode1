# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from copy import deepcopy

from cdb import validationkit
from cs.variants.api import reinstantiate_parts
from cs.variants.api.instantiate_options import InstantiateOptions
from cs.variants.api.tests.reinstantiate_test_case import ReinstantiateTestCase
from cs.variants.api.tests.subassembly_structure import SubassemblyStructure
from cs.variants.exceptions import (
    NotAllowedToReinstantiateError,
    SelectionConditionEvaluationError,
)
from cs.variants.selection_condition import SelectionCondition
from cs.vp.bom.tests import generateAssemblyComponent


class TestReinstantiate(ReinstantiateTestCase):
    def setUp(self):
        super().setUp()
        self.options = InstantiateOptions.ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM
        InstantiateOptions.ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM = [
            "netto_laenge",
        ]

    def tearDown(self):
        super().tearDown()
        InstantiateOptions.ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM = self.options

    def test_reinstantiate_changed_maxbom_structure_filtered(self):
        """
        reinstantiate_parts method will recompute the 100% product structure
        of a changed maxbom structure filtered
        """
        self.assert_subassembly_structure(
            self.expected_var1_part1_smaller_maxbom_structure,
            self.var1_part1_smaller_maxbom,
        )

        expected_structure = SubassemblyStructure(
            self.var1_part1_smaller_maxbom_keys,
            children=[
                self.expected_maxbom_part2,
                SubassemblyStructure(
                    self.copy_of_maxbom_subassembly1_keys,
                    children=[self.expected_maxbom_subassembly1_part2],
                ),
            ],
        )

        reinstantiate_parts([self.var1_part1_smaller_maxbom])

        self.assert_subassembly_structure(
            expected_structure,
            self.var1_part1_smaller_maxbom,
        )
        self.assertRelationshipToMaxBOM(
            self.var1_part1_smaller_maxbom, self.maxbom, self.var1
        )

    def test_reinstantiate_changed_maxbom_structure(self):
        """
        reinstantiate_parts method will recompute the 100% product structure
        of a changed maxbom structure NOT filtered
        """
        self.assert_subassembly_structure(
            self.expected_var2_part1_smaller_maxbom_structure,
            self.var2_part1_smaller_maxbom,
        )

        expected_structure = SubassemblyStructure(
            self.var2_part1_smaller_maxbom_keys,
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
                    occurrence_keys=[self.maxbom_subassembly1_occurrence1_keys],
                ),
                SubassemblyStructure(
                    {
                        "teilenummer": self.check_teilenummer_not_exists,
                        "t_index": "",
                        "cdb_object_id": self.check_object_id_not_exists,
                    },
                    children=[
                        self.expected_maxbom_subassembly2_part1,
                        self.expected_maxbom_subassembly2_part2,
                    ],
                    occurrence_keys=[
                        self.maxbom_subassembly2_occurrence1_keys,
                        self.maxbom_subassembly2_occurrence2_keys,
                    ],
                ),
            ],
        )

        reinstantiate_parts([self.var2_part1_smaller_maxbom])
        self.assert_subassembly_structure(
            expected_structure,
            self.var2_part1_smaller_maxbom,
        )
        self.assertRelationshipToMaxBOM(
            self.var2_part1_smaller_maxbom, self.maxbom, self.var2
        )

    def test_reinstantiate_simple_NOT_filtered(self):
        """reinstantiate_parts method will recompute the 100% product structure NOT filtered"""
        self.assert_subassembly_structure(
            self.expected_var2_part2_no_selection_condition_structure,
            self.var2_part2_no_selection_condition,
        )

        expected_structure = SubassemblyStructure(
            self.var2_part2_no_selection_condition_keys,
            children=[
                self.expected_maxbom_part1,
                self.expected_maxbom_part2,
                SubassemblyStructure(
                    self.copy_of_maxbom_subassembly1_keys,
                    children=[
                        self.expected_maxbom_subassembly1_part1,
                        self.expected_maxbom_subassembly1_part2,
                    ],
                ),
                SubassemblyStructure(
                    {
                        "teilenummer": self.check_teilenummer_not_exists,
                        "t_index": "",
                        "cdb_object_id": self.check_object_id_not_exists,
                    },
                    children=[
                        self.expected_maxbom_subassembly2_part1,
                        self.expected_maxbom_subassembly2_part2,
                    ],
                ),
            ],
        )

        reinstantiate_parts([self.var2_part2_no_selection_condition])

        self.assert_subassembly_structure(
            expected_structure,
            self.var2_part2_no_selection_condition,
        )
        self.assertRelationshipToMaxBOM(
            self.var2_part2_no_selection_condition, self.maxbom, self.var2
        )

    def test_reinstantiate_simple_after_adding_new_selection_condition(self):
        """reinstantiate_parts method will recompute the 100% product structure filtered"""
        self.assert_subassembly_structure(
            self.expected_var1_part2_no_selection_condition_structure,
            self.var1_part2_no_selection_condition,
        )

        expected_structure = SubassemblyStructure(
            self.var1_part2_no_selection_condition_keys,
            children=[
                self.expected_maxbom_part2,
                SubassemblyStructure(
                    self.copy_of_maxbom_subassembly1_keys,
                    children=[self.expected_maxbom_subassembly1_part2],
                ),
            ],
        )

        reinstantiate_parts([self.var1_part2_no_selection_condition])

        self.assert_subassembly_structure(
            expected_structure,
            self.var1_part2_no_selection_condition,
        )
        self.assertRelationshipToMaxBOM(
            self.var1_part2_no_selection_condition, self.maxbom, self.var1
        )

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

        reinstantiate_parts([self.var1_part3])

        expected_structure = deepcopy(self.expected_var1_part3_structure)
        expected_structure.update_keys(
            bom_item_keys={"menge": 42, "netto_laenge": 42}, recursive=True
        )

        self.assert_subassembly_structure(
            expected_structure,
            self.var1_part3,
        )
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
        self.assertRelationshipToMaxBOM(self.var1_part3, self.maxbom, self.var1)

    def test_reinstantiate_multiple(self):
        """reinstantiate_parts method will recompute the 100% product structure for multiple parts"""
        self.assert_subassembly_structure(
            self.expected_var1_part1_smaller_maxbom_structure,
            self.var1_part1_smaller_maxbom,
        )
        self.assert_subassembly_structure(
            self.expected_var1_part2_no_selection_condition_structure,
            self.var1_part2_no_selection_condition,
        )
        self.assert_subassembly_structure(
            self.expected_var1_part3_structure, self.var1_part3
        )

        expected_var1_part1_smaller_maxbom_structure = SubassemblyStructure(
            self.var1_part1_smaller_maxbom_keys,
            children=[
                self.expected_maxbom_part2,
                SubassemblyStructure(
                    self.copy_of_maxbom_subassembly1_keys,
                    children=[self.expected_maxbom_subassembly1_part2],
                ),
            ],
        )

        expected_var1_part2_no_selection_condition_structure = SubassemblyStructure(
            self.var1_part2_no_selection_condition_keys,
            children=[
                self.expected_maxbom_part2,
                SubassemblyStructure(
                    self.copy_of_maxbom_subassembly1_keys,
                    children=[self.expected_maxbom_subassembly1_part2],
                ),
            ],
        )

        reinstantiate_parts(
            [
                self.var1_part1_smaller_maxbom,
                self.var1_part2_no_selection_condition,
                self.var1_part3,
            ]
        )

        self.assert_subassembly_structure(
            expected_var1_part1_smaller_maxbom_structure, self.var1_part1_smaller_maxbom
        )
        self.assertRelationshipToMaxBOM(
            self.var1_part1_smaller_maxbom, self.maxbom, self.var1
        )

        self.assert_subassembly_structure(
            expected_var1_part2_no_selection_condition_structure,
            self.var1_part2_no_selection_condition,
        )
        self.assertRelationshipToMaxBOM(
            self.var1_part2_no_selection_condition, self.maxbom, self.var1
        )

        self.assert_subassembly_structure(
            self.expected_var1_part3_structure, self.var1_part3
        )
        self.assertRelationshipToMaxBOM(self.var1_part3, self.maxbom, self.var1)

    def test_reinstantiate_multiple_sequentially(self):
        """
        reinstantiate_parts method will recompute the 100% product structure for multiple parts sequentially
        """

        self.assert_subassembly_structure(
            self.expected_var1_part1_smaller_maxbom_structure,
            self.var1_part1_smaller_maxbom,
        )
        self.assert_subassembly_structure(
            self.expected_var1_part2_no_selection_condition_structure,
            self.var1_part2_no_selection_condition,
        )
        self.assert_subassembly_structure(
            self.expected_var1_part3_structure, self.var1_part3
        )

        expected_var1_part1_smaller_maxbom_structure = SubassemblyStructure(
            self.var1_part1_smaller_maxbom_keys,
            children=[
                self.expected_maxbom_part2,
                SubassemblyStructure(
                    self.copy_of_maxbom_subassembly1_keys,
                    children=[self.expected_maxbom_subassembly1_part2],
                ),
            ],
        )

        expected_var1_part2_no_selection_condition_structure = SubassemblyStructure(
            self.var1_part2_no_selection_condition_keys,
            children=[
                self.expected_maxbom_part2,
                SubassemblyStructure(
                    self.copy_of_maxbom_subassembly1_keys,
                    children=[self.expected_maxbom_subassembly1_part2],
                ),
            ],
        )

        reinstantiate_parts(
            [
                self.var1_part1_smaller_maxbom,
            ]
        )

        self.assert_subassembly_structure(
            expected_var1_part1_smaller_maxbom_structure, self.var1_part1_smaller_maxbom
        )
        self.assertRelationshipToMaxBOM(
            self.var1_part1_smaller_maxbom, self.maxbom, self.var1
        )
        self.assert_subassembly_structure(
            self.expected_var1_part2_no_selection_condition_structure,
            self.var1_part2_no_selection_condition,
        )
        self.assert_subassembly_structure(
            self.expected_var1_part3_structure, self.var1_part3
        )

        reinstantiate_parts(
            [
                self.var1_part2_no_selection_condition,
            ]
        )

        self.assert_subassembly_structure(
            expected_var1_part1_smaller_maxbom_structure, self.var1_part1_smaller_maxbom
        )
        self.assert_subassembly_structure(
            expected_var1_part2_no_selection_condition_structure,
            self.var1_part2_no_selection_condition,
        )
        self.assertRelationshipToMaxBOM(
            self.var1_part2_no_selection_condition, self.maxbom, self.var1
        )
        self.assert_subassembly_structure(
            self.expected_var1_part3_structure, self.var1_part3
        )

        reinstantiate_parts(
            [
                self.var1_part3,
            ]
        )

        self.assert_subassembly_structure(
            expected_var1_part1_smaller_maxbom_structure, self.var1_part1_smaller_maxbom
        )
        self.assert_subassembly_structure(
            expected_var1_part2_no_selection_condition_structure,
            self.var1_part2_no_selection_condition,
        )
        self.assert_subassembly_structure(
            self.expected_var1_part3_structure, self.var1_part3
        )
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
                    self.copy_of_maxbom_indexed_subassembly1_keys,
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

    def test_reinstantiate_without_access_rights(self):
        """the reinstantiate_part method will raise NotAllowedToReinstantiateError if the part is released"""

        @validationkit.run_with_roles(["public"])
        def perform():
            reinstantiate_parts([self.var2_part4_approved])

        with self.assertRaises(NotAllowedToReinstantiateError):
            perform()

    def test_reinstantiate_with_syntax_error(self):
        ref_object_ids = [each.cdb_object_id for each in self.maxbom.Components]
        selection_condition = SelectionCondition.KeywordQuery(
            ref_object_id=ref_object_ids
        )
        selection_condition.Update(expression="abc == 'Syntax Error")

        with self.assertRaises(SelectionConditionEvaluationError) as assert_raises:
            reinstantiate_parts([self.var1_part3])

        self.assertIn(assert_raises.exception.ref_object_id, ref_object_ids)

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
