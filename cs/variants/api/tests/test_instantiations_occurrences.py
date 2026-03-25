#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from copy import deepcopy

from cs.variants.api import helpers, instantiate_part, reinstantiate_parts
from cs.variants.api.tests.reinstantiate_test_case import ReinstantiateTestCase
from cs.variants.api.tests.subassembly_structure import SubassemblyStructure
from cs.variants.tests.common import generate_selection_condition


class TestInstantiationsOccurrences(ReinstantiateTestCase):
    def tearDown(self):
        super().tearDown()
        helpers.REUSE_ENABLED = self.reuse_enabled

    def setUp(self):
        super().setUp()
        self.reuse_enabled = helpers.REUSE_ENABLED
        helpers.REUSE_ENABLED = False

    def assert_maxbom_deep_level5(self, instance, expected_level5):
        self.assert_subassembly_structure(
            SubassemblyStructure(
                self.copy_of_maxbom_deep_keys,
                children=[
                    SubassemblyStructure(
                        self.copy_of_maxbom_deep_subassembly_level1_keys,
                        children=[
                            SubassemblyStructure(
                                self.copy_of_maxbom_deep_subassembly_level2_keys,
                                children=[
                                    SubassemblyStructure(
                                        self.copy_of_maxbom_deep_subassembly_level3_keys,
                                        children=[
                                            SubassemblyStructure(
                                                self.copy_of_maxbom_deep_subassembly_level4_keys,
                                                children=[expected_level5],
                                                occurrence_keys=[
                                                    self.maxbom_deep_subassembly_level4_occurrence1_keys,
                                                    self.maxbom_deep_subassembly_level4_occurrence2_keys,
                                                ],
                                            )
                                        ],
                                        occurrence_keys=[
                                            self.maxbom_deep_subassembly_level3_occurrence1_keys
                                        ],
                                    )
                                ],
                                occurrence_keys=[
                                    self.maxbom_deep_subassembly_level2_occurrence1_keys,
                                    self.maxbom_deep_subassembly_level2_occurrence2_keys,
                                ],
                            )
                        ],
                        occurrence_keys=[
                            self.maxbom_deep_subassembly_level1_occurrence1_keys
                        ],
                    )
                ],
            ),
            instance,
            assert_occurrences=True,
        )

    @classmethod
    def setUpClass(cls):
        super(TestInstantiationsOccurrences, cls).setUpClass()

        cls.expected_structure_maxbom_with_variant1 = SubassemblyStructure(
            cls.copy_of_maxbom_keys,
            children=[
                SubassemblyStructure(
                    cls.maxbom_part2_keys,
                    occurrence_keys=[cls.maxbom_part2_occurrence1_keys],
                ),
                SubassemblyStructure(
                    cls.copy_of_maxbom_subassembly1_keys,
                    children=[
                        SubassemblyStructure(
                            cls.maxbom_subassembly1_part2_keys,
                            occurrence_keys=[
                                cls.maxbom_subassembly1_part2_occurrence1_keys,
                            ],
                        )
                    ],
                    occurrence_keys=[cls.maxbom_subassembly1_occurrence1_keys],
                ),
            ],
        )

        cls.expected_structure_maxbom_with_variant1_with_no_bom_item_scs = (
            SubassemblyStructure(
                cls.copy_of_maxbom_keys,
                children=[
                    cls.expected_maxbom_part1,
                    SubassemblyStructure(
                        cls.maxbom_part2_keys,
                        occurrence_keys=[cls.maxbom_part2_occurrence1_keys],
                    ),
                    SubassemblyStructure(
                        cls.copy_of_maxbom_subassembly1_keys,
                        children=[
                            cls.expected_maxbom_subassembly1_part1,
                            SubassemblyStructure(
                                cls.maxbom_subassembly1_part2_keys,
                                occurrence_keys=[
                                    cls.maxbom_subassembly1_part2_occurrence1_keys
                                ],
                            ),
                        ],
                        occurrence_keys=[cls.maxbom_subassembly1_occurrence1_keys],
                    ),
                    SubassemblyStructure(
                        cls.copy_of_maxbom_subassembly2_keys,
                        children=[
                            cls.expected_maxbom_subassembly2_part1,
                            SubassemblyStructure(
                                cls.maxbom_subassembly2_part2_keys,
                                occurrence_keys=[
                                    cls.maxbom_subassembly2_part2_occurrence1_keys
                                ],
                            ),
                        ],
                        occurrence_keys=[
                            cls.maxbom_subassembly2_occurrence1_keys,
                            cls.maxbom_subassembly2_occurrence2_keys,
                        ],
                    ),
                ],
            )
        )

        cls.expected_structure_maxbom_with_variant2 = SubassemblyStructure(
            cls.copy_of_maxbom_keys,
            children=[
                cls.expected_maxbom_part1,
                cls.expected_maxbom_part2,
                SubassemblyStructure(
                    cls.copy_of_maxbom_subassembly1_keys,
                    children=[
                        cls.expected_maxbom_subassembly1_part1,
                        cls.expected_maxbom_subassembly1_part2,
                    ],
                    occurrence_keys=[cls.maxbom_subassembly1_occurrence1_keys],
                ),
                SubassemblyStructure(
                    cls.copy_of_maxbom_subassembly2_keys,
                    children=[
                        cls.expected_maxbom_subassembly2_part1,
                        cls.expected_maxbom_subassembly2_part2,
                    ],
                    occurrence_keys=[cls.maxbom_subassembly2_occurrence1_keys],
                ),
            ],
        )

        cls.expected_structure_maxbom_with_variant2_with_no_bom_item_scs = (
            SubassemblyStructure(
                cls.copy_of_maxbom_keys,
                children=[
                    cls.expected_maxbom_part1,
                    cls.expected_maxbom_part2,
                    SubassemblyStructure(
                        cls.copy_of_maxbom_subassembly1_keys,
                        children=[
                            cls.expected_maxbom_subassembly1_part1,
                            cls.expected_maxbom_subassembly1_part2,
                        ],
                        occurrence_keys=[cls.maxbom_subassembly1_occurrence1_keys],
                    ),
                    SubassemblyStructure(
                        cls.copy_of_maxbom_subassembly2_keys,
                        children=[
                            cls.expected_maxbom_subassembly2_part1,
                            cls.expected_maxbom_subassembly2_part2,
                        ],
                        occurrence_keys=[cls.maxbom_subassembly2_occurrence1_keys],
                    ),
                ],
            )
        )

    def test_instantiation_persistent_variant_1_with_occurrences_without_rules_on_occurrences(
        self,
    ):
        self.remove_occurrences_selection_conditions()

        expected_structure = SubassemblyStructure(
            self.copy_of_maxbom_keys,
            children=[
                self.expected_maxbom_part2,
                SubassemblyStructure(
                    self.copy_of_maxbom_subassembly1_keys,
                    children=[self.expected_maxbom_subassembly1_part2],
                    occurrence_keys=[self.maxbom_subassembly1_occurrence1_keys],
                ),
            ],
        )

        instance = instantiate_part(self.var1, self.maxbom)

        self.assert_subassembly_structure(
            expected_structure, instance, assert_occurrences=True
        )
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.var1)

    def test_instantiation_persistent_variant_1_with_occurrences_without_rules_on_occurrences_adapted_menge(
        self,
    ):
        self.remove_occurrences_selection_conditions()

        # This is expected to not have no effect because menge is calculated if occurrences exist
        self.bom_item_part2.menge = 10
        self.bom_item_subassembly1.menge = 10

        expected_structure = SubassemblyStructure(
            self.copy_of_maxbom_keys,
            children=[
                self.expected_maxbom_part2,
                SubassemblyStructure(
                    self.copy_of_maxbom_subassembly1_keys,
                    children=[self.expected_maxbom_subassembly1_part2],
                    occurrence_keys=[self.maxbom_subassembly1_occurrence1_keys],
                ),
            ],
        )

        instance = instantiate_part(self.var1, self.maxbom)

        self.assert_subassembly_structure(
            expected_structure, instance, assert_occurrences=True
        )
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.var1)

    def test_instantiation_persistent_variant_1_with_occurrences_without_rules_on_occurrences_adapted_menge2(
        self,
    ):
        self.remove_occurrences_selection_conditions()

        # This should have an effect because we remove occurrences
        self.bom_item_part2.Occurrences.Delete()
        self.bom_item_part2.menge = 10

        # This is expected to not have no effect because menge is calculated if occurrences exist
        self.bom_item_subassembly1.menge = 10

        expected_structure = SubassemblyStructure(
            self.copy_of_maxbom_keys,
            children=[
                SubassemblyStructure(
                    self.maxbom_part2_keys, bom_item_keys={"menge": 10}
                ),
                SubassemblyStructure(
                    self.copy_of_maxbom_subassembly1_keys,
                    children=[self.expected_maxbom_subassembly1_part2],
                    bom_item_keys={"menge": 1},
                ),
            ],
        )

        instance = instantiate_part(self.var1, self.maxbom)

        self.assert_subassembly_structure(
            expected_structure, instance, assert_occurrences=False
        )
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.var1)

    def test_instantiation_persistent_variant_1_with_occurrences_without_rules_on_occurrences_adapted_menge3(
        self,
    ):
        self.remove_occurrences_selection_conditions()

        # This should have an effect because we remove occurrences
        self.bom_item_subassembly1.Occurrences.Delete()
        self.bom_item_subassembly1.menge = 10

        # This is expected to not have no effect because menge is calculated if occurrences exist
        self.bom_item_part2.menge = 10

        expected_structure = SubassemblyStructure(
            self.copy_of_maxbom_keys,
            children=[
                SubassemblyStructure(
                    self.maxbom_part2_keys, bom_item_keys={"menge": 2}
                ),
                SubassemblyStructure(
                    self.copy_of_maxbom_subassembly1_keys,
                    children=[self.expected_maxbom_subassembly1_part2],
                    bom_item_keys={"menge": 10},
                ),
            ],
        )

        instance = instantiate_part(self.var1, self.maxbom)

        self.assert_subassembly_structure(
            expected_structure, instance, assert_occurrences=False
        )
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.var1)

    def test_instantiation_persistent_variant_2_with_occurrences_without_rules_on_occurrences(
        self,
    ):
        self.remove_occurrences_selection_conditions()

        expected_structure = SubassemblyStructure(
            self.copy_of_maxbom_keys,
            children=[
                self.expected_maxbom_part1,
                self.expected_maxbom_part2,
                SubassemblyStructure(
                    self.copy_of_maxbom_subassembly1_keys,
                    children=[
                        self.expected_maxbom_subassembly1_part1,
                        self.expected_maxbom_subassembly1_part2,
                    ],
                    occurrence_keys=[self.maxbom_subassembly1_occurrence1_keys],
                ),
                self.expected_subassembly2_structure,
            ],
        )

        instance = instantiate_part(self.var2, self.maxbom)

        self.assert_subassembly_structure(
            expected_structure, instance, assert_occurrences=True
        )
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.var2)

    def test_instantiation_persistent_variant_1_with_occurrences_with_rules_on_occurrences(
        self,
    ):
        instance = instantiate_part(self.var1, self.maxbom)

        self.assert_subassembly_structure(
            self.expected_structure_maxbom_with_variant1,
            instance,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.var1)

    def test_instantiation_persistent_variant_2_with_occurrences_with_rules_on_occurrences(
        self,
    ):
        instance = instantiate_part(self.var2, self.maxbom)

        self.assert_subassembly_structure(
            self.expected_structure_maxbom_with_variant2,
            instance,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(instance, self.maxbom, self.var2)

    def test_reinstantiation_var1_part1(self):
        reinstantiate_parts([self.var1_part1_smaller_maxbom])

        self.assert_subassembly_structure(
            self.expected_structure_maxbom_with_variant1,
            self.var1_part1_smaller_maxbom,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            self.var1_part1_smaller_maxbom, self.maxbom, self.var1
        )

    def test_reinstantiation_var1_part1_with_no_selection_condition(self):
        self.remove_all_selection_conditions()

        expected_structure = SubassemblyStructure(
            self.var1_part1_smaller_maxbom_keys, children=deepcopy(self.maxbom_children)
        )
        expected_structure.children[0].update_keys(
            bom_item_keys={"cdb_object_id": self.var1_part1_child_part1_bom_item_id}
        )

        reinstantiate_parts([self.var1_part1_smaller_maxbom])

        self.assert_subassembly_structure(
            expected_structure,
            self.var1_part1_smaller_maxbom,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            self.var1_part1_smaller_maxbom, self.maxbom, self.var1
        )

    def test_reinstantiation_var1_part2(self):
        reinstantiate_parts([self.var1_part2_no_selection_condition])

        self.assert_subassembly_structure(
            self.expected_structure_maxbom_with_variant1,
            self.var1_part2_no_selection_condition,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            self.var1_part2_no_selection_condition, self.maxbom, self.var1
        )

    def test_reinstantiation_var1_part3(self):
        reinstantiate_parts([self.var1_part3])

        self.assert_subassembly_structure(
            self.expected_structure_maxbom_with_variant1,
            self.var1_part3,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(self.var1_part3, self.maxbom, self.var1)

    def test_reinstantiation_var1_part1_to_3(self):
        reinstantiate_parts(
            [
                self.var1_part1_smaller_maxbom,
                self.var1_part2_no_selection_condition,
                self.var1_part3,
            ]
        )

        self.assert_subassembly_structure(
            self.expected_structure_maxbom_with_variant1,
            self.var1_part1_smaller_maxbom,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            self.var1_part1_smaller_maxbom, self.maxbom, self.var1
        )

        self.assert_subassembly_structure(
            self.expected_structure_maxbom_with_variant1,
            self.var1_part2_no_selection_condition,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            self.var1_part2_no_selection_condition, self.maxbom, self.var1
        )

        self.assert_subassembly_structure(
            self.expected_structure_maxbom_with_variant1,
            self.var1_part3,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(self.var1_part3, self.maxbom, self.var1)

    def test_reinstantiation_var2_part1(self):
        reinstantiate_parts([self.var2_part1_smaller_maxbom])

        self.assert_subassembly_structure(
            self.expected_structure_maxbom_with_variant2,
            self.var2_part1_smaller_maxbom,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            self.var1_part1_smaller_maxbom, self.maxbom, self.var1
        )

    def test_reinstantiation_var2_part2(self):
        reinstantiate_parts([self.var2_part2_no_selection_condition])

        self.assert_subassembly_structure(
            self.expected_structure_maxbom_with_variant2,
            self.var2_part2_no_selection_condition,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            self.var2_part2_no_selection_condition, self.maxbom, self.var2
        )

    def test_reinstantiation_var2_part3(self):
        reinstantiate_parts([self.var2_part3])

        self.assert_subassembly_structure(
            self.expected_structure_maxbom_with_variant2,
            self.var2_part3,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(self.var2_part3, self.maxbom, self.var2)

    def test_reinstantiation_var2_part1_to_3(self):
        reinstantiate_parts(
            [
                self.var2_part1_smaller_maxbom,
                self.var2_part2_no_selection_condition,
                self.var2_part3,
            ]
        )

        self.assert_subassembly_structure(
            self.expected_structure_maxbom_with_variant2,
            self.var2_part1_smaller_maxbom,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            self.var2_part1_smaller_maxbom, self.maxbom, self.var2
        )

        self.assert_subassembly_structure(
            self.expected_structure_maxbom_with_variant2,
            self.var2_part2_no_selection_condition,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            self.var2_part2_no_selection_condition, self.maxbom, self.var2
        )

        self.assert_subassembly_structure(
            self.expected_structure_maxbom_with_variant2,
            self.var2_part3,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(self.var2_part3, self.maxbom, self.var2)

    def test_reinstantiation_var1_part1_to_maxbom_without_selection_condition(self):
        self.remove_all_selection_conditions()

        reinstantiate_parts([self.var1_part1_smaller_maxbom])

        self.assert_subassembly_structure(
            SubassemblyStructure(
                self.var1_part1_smaller_maxbom_keys, children=self.maxbom_children
            ),
            self.var1_part1_smaller_maxbom,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            self.var1_part1_smaller_maxbom, self.maxbom, self.var1
        )

    def test_reinstantiation_var1_part2_to_maxbom_without_selection_condition(self):
        self.remove_all_selection_conditions()

        reinstantiate_parts([self.var1_part2_no_selection_condition])

        self.assert_subassembly_structure(
            SubassemblyStructure(
                self.var1_part2_no_selection_condition_keys,
                children=self.maxbom_children,
            ),
            self.var1_part2_no_selection_condition,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            self.var1_part2_no_selection_condition, self.maxbom, self.var1
        )

    def test_reinstantiation_var1_part3_to_maxbom_without_selection_condition(self):
        self.remove_all_selection_conditions()

        reinstantiate_parts([self.var1_part3])

        self.assert_subassembly_structure(
            SubassemblyStructure(self.var1_part3_keys, children=self.maxbom_children),
            self.var1_part3,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(self.var1_part3, self.maxbom, self.var1)

    def test_reinstantiation_var1_part3_to_maxbom_without_selection_condition_adapted_menge_maxbom(
        self,
    ):
        self.remove_all_selection_conditions()

        # This is expected to not have no effect because menge is calculated if occurrences exist
        self.bom_item_part2.menge = 10
        self.bom_item_subassembly1.menge = 10

        reinstantiate_parts([self.var1_part3])

        self.assert_subassembly_structure(
            SubassemblyStructure(self.var1_part3_keys, children=self.maxbom_children),
            self.var1_part3,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(self.var1_part3, self.maxbom, self.var1)

    def test_reinstantiation_var1_part3_to_maxbom_without_selection_condition_adapted_menge_maxbom2(
        self,
    ):
        self.remove_all_selection_conditions()

        # This should have an effect because we remove occurrences
        self.bom_item_part2.Occurrences.Delete()
        self.bom_item_part2.menge = 10

        # This is expected to not have no effect because menge is calculated if occurrences exist
        self.bom_item_subassembly1.menge = 10

        reinstantiate_parts([self.var1_part3])

        self.assert_subassembly_structure(
            SubassemblyStructure(
                self.var1_part3_keys,
                children=[
                    self.expected_maxbom_part1,
                    SubassemblyStructure(
                        self.maxbom_part2_keys, bom_item_keys={"menge": 10}
                    ),
                    SubassemblyStructure(
                        self.maxbom_subassembly1_keys,
                        children=[
                            self.expected_maxbom_subassembly1_part1,
                            self.expected_maxbom_subassembly1_part2,
                        ],
                        bom_item_keys={"menge": 1},
                    ),
                    self.expected_subassembly2_structure,
                ],
            ),
            self.var1_part3,
            assert_occurrences=False,
        )
        self.assertRelationshipToMaxBOM(self.var1_part3, self.maxbom, self.var1)

    def test_reinstantiation_var1_part3_to_maxbom_without_selection_condition_adapted_menge_maxbom3(
        self,
    ):
        self.remove_all_selection_conditions()

        # This should have an effect because we remove occurrences
        self.bom_item_subassembly1.Occurrences.Delete()
        self.bom_item_subassembly1.menge = 10

        # This is expected to not have no effect because menge is calculated if occurrences exist
        self.bom_item_part2.menge = 10

        reinstantiate_parts([self.var1_part3])

        self.assert_subassembly_structure(
            SubassemblyStructure(
                self.var1_part3_keys,
                children=[
                    self.expected_maxbom_part1,
                    SubassemblyStructure(
                        self.maxbom_part2_keys, bom_item_keys={"menge": 2}
                    ),
                    SubassemblyStructure(
                        self.maxbom_subassembly1_keys,
                        children=[
                            self.expected_maxbom_subassembly1_part1,
                            self.expected_maxbom_subassembly1_part2,
                        ],
                        bom_item_keys={"menge": 10},
                    ),
                    self.expected_subassembly2_structure,
                ],
            ),
            self.var1_part3,
            assert_occurrences=False,
        )
        self.assertRelationshipToMaxBOM(self.var1_part3, self.maxbom, self.var1)

    def test_reinstantiation_var1_part3_to_maxbom_without_selection_condition_adapted_menge(
        self,
    ):
        self.remove_all_selection_conditions()

        # This is expected to not have no effect because menge is calculated if occurrences exist
        for each in self.var1_part3.Components:
            each.menge = 10

        reinstantiate_parts([self.var1_part3])

        self.assert_subassembly_structure(
            SubassemblyStructure(self.var1_part3_keys, children=self.maxbom_children),
            self.var1_part3,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(self.var1_part3, self.maxbom, self.var1)

    def test_reinstantiation_var1_part3_to_maxbom_without_selection_condition_adapted_menge2(
        self,
    ):
        self.remove_all_selection_conditions()

        # This should have an effect because we remove occurrences
        for each in self.maxbom.Components:
            each.Occurrences.Delete()
        for each in self.var1_part3.Components:
            each.menge = 10

        reinstantiate_parts([self.var1_part3])

        self.assert_subassembly_structure(
            SubassemblyStructure(self.var1_part3_keys, children=self.maxbom_children),
            self.var1_part3,
            assert_occurrences=False,
        )
        self.assertRelationshipToMaxBOM(self.var1_part3, self.maxbom, self.var1)
        # Should maxbom or old instanced item changes win?
        # self.var1_part3.Reload()
        # for each in self.var1_part3.Components:
        #     each.Reload()
        #     self.assertEqual(10, each.menge)

    def test_reinstantiation_var2_part2_to_maxbom_without_selection_condition(self):
        self.remove_all_selection_conditions()

        reinstantiate_parts([self.var2_part2_no_selection_condition])

        self.assert_subassembly_structure(
            SubassemblyStructure(
                self.var2_part2_no_selection_condition_keys,
                children=self.maxbom_children,
            ),
            self.var2_part2_no_selection_condition,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            self.var2_part2_no_selection_condition, self.maxbom, self.var2
        )

    def test_reinstantiation_var2_part3_to_maxbom_without_selection_condition(self):
        self.remove_all_selection_conditions()

        reinstantiate_parts([self.var2_part3])

        self.assert_subassembly_structure(
            SubassemblyStructure(self.var2_part3_keys, children=self.maxbom_children),
            self.var2_part3,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(self.var2_part3, self.maxbom, self.var2)

    def test_reinstantiation_var1_part1_to_maxbom_without_selection_condition_on_bom_item(
        self,
    ):
        self.remove_bom_item_selection_conditions()

        reinstantiate_parts([self.var1_part1_smaller_maxbom])

        self.assert_subassembly_structure(
            self.expected_structure_maxbom_with_variant1_with_no_bom_item_scs,
            self.var1_part1_smaller_maxbom,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            self.var1_part1_smaller_maxbom, self.maxbom, self.var1
        )

    def test_reinstantiation_var1_part2_to_maxbom_without_selection_condition_on_bom_item(
        self,
    ):
        self.remove_bom_item_selection_conditions()

        reinstantiate_parts([self.var1_part2_no_selection_condition])

        self.assert_subassembly_structure(
            self.expected_structure_maxbom_with_variant1_with_no_bom_item_scs,
            self.var1_part2_no_selection_condition,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            self.var1_part2_no_selection_condition, self.maxbom, self.var1
        )

    def test_reinstantiation_var1_part3_to_maxbom_without_selection_condition_on_bom_item(
        self,
    ):
        self.remove_bom_item_selection_conditions()

        reinstantiate_parts([self.var1_part3])

        self.assert_subassembly_structure(
            self.expected_structure_maxbom_with_variant1_with_no_bom_item_scs,
            self.var1_part3,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(self.var1_part3, self.maxbom, self.var1)

    def test_reinstantiation_var2_part1_to_maxbom_without_selection_condition_on_bom_item(
        self,
    ):
        self.remove_bom_item_selection_conditions()

        reinstantiate_parts([self.var2_part1_smaller_maxbom])

        self.assert_subassembly_structure(
            self.expected_structure_maxbom_with_variant2_with_no_bom_item_scs,
            self.var2_part1_smaller_maxbom,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            self.var2_part1_smaller_maxbom, self.maxbom, self.var2
        )

    def test_reinstantiation_var2_part2_to_maxbom_without_selection_condition_on_bom_item(
        self,
    ):
        self.remove_bom_item_selection_conditions()

        reinstantiate_parts([self.var2_part2_no_selection_condition])

        self.assert_subassembly_structure(
            self.expected_structure_maxbom_with_variant2_with_no_bom_item_scs,
            self.var2_part2_no_selection_condition,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            self.var2_part2_no_selection_condition, self.maxbom, self.var2
        )

    def test_reinstantiation_var2_part3_to_maxbom_without_selection_condition_on_bom_item(
        self,
    ):
        self.remove_bom_item_selection_conditions()

        reinstantiate_parts([self.var2_part3])

        self.assert_subassembly_structure(
            self.expected_structure_maxbom_with_variant2_with_no_bom_item_scs,
            self.var2_part3,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(self.var2_part3, self.maxbom, self.var2)

    def test_instantiation_maxbom_deep_with_no_selection_condition(self):
        instance = instantiate_part(self.var1, self.maxbom_deep)

        self.assert_subassembly_structure(
            SubassemblyStructure(
                self.copy_of_maxbom_deep_keys,
                children=[self.maxbom_deep_subassembly_level1],
            ),
            instance,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(instance, self.maxbom_deep, self.var1)

    def test_reinstantiation_maxbom_deep_with_no_selection_condition_var1(self):
        reinstantiate_parts([self.var1_part_maxbom_deep])

        self.assert_subassembly_structure(
            SubassemblyStructure(
                self.var1_part_maxbom_deep_keys,
                children=[self.maxbom_deep_subassembly_level1],
            ),
            self.var1_part_maxbom_deep,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            self.var1_part_maxbom_deep, self.maxbom_deep, self.var1
        )

    def test_reinstantiation_maxbom_deep_with_no_selection_condition_var2(self):
        reinstantiate_parts([self.var2_part_maxbom_deep])

        self.assert_subassembly_structure(
            SubassemblyStructure(
                self.var2_part_maxbom_deep_keys,
                children=[self.maxbom_deep_subassembly_level1],
            ),
            self.var2_part_maxbom_deep,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            self.var2_part_maxbom_deep, self.maxbom_deep, self.var2
        )

    def test_instantiation_maxbom_var1_deep_with_selection_condition_on_deepest_part_only_occurrence(
        self,
    ):
        generate_selection_condition(
            self.variability_model,
            self.maxbom_deep_bom_item_occurrence2_level5,
            self.expression_valid_for_variant2,
        )

        instance = instantiate_part(self.var1, self.maxbom_deep)

        expected_level5 = SubassemblyStructure(
            self.copy_of_maxbom_deep_subassembly_level5_keys,
            children=[
                SubassemblyStructure(
                    self.maxbom_deep_part_level5_keys,
                    occurrence_keys=[self.maxbom_deep_part_level5_occurrence1_keys],
                )
            ],
            occurrence_keys=[self.maxbom_deep_subassembly_level5_occurrence1_keys],
        )

        self.assert_maxbom_deep_level5(instance, expected_level5)
        self.assertRelationshipToMaxBOM(instance, self.maxbom_deep, self.var1)

    def test_instantiation_maxbom_var2_deep_with_selection_condition_on_deepest_part_only_occurrence(
        self,
    ):
        generate_selection_condition(
            self.variability_model,
            self.maxbom_deep_bom_item_occurrence2_level5,
            self.expression_valid_for_variant2,
        )

        instance = instantiate_part(self.var2, self.maxbom_deep)

        expected_level5 = SubassemblyStructure(
            self.copy_of_maxbom_deep_subassembly_level5_keys,
            children=[self.maxbom_deep_part_level5],
            occurrence_keys=[self.maxbom_deep_subassembly_level5_occurrence1_keys],
        )

        self.assert_maxbom_deep_level5(instance, expected_level5)
        self.assertRelationshipToMaxBOM(instance, self.maxbom_deep, self.var2)

    def test_reinstantiation_maxbom_var1_deep_with_selection_condition_on_deepest_part_only_oc_removed(
        self,
    ):
        selection_condition = generate_selection_condition(
            self.variability_model,
            self.maxbom_deep_bom_item_occurrence2_level5,
            self.expression_valid_for_variant2,
        )

        instance = instantiate_part(self.var1, self.maxbom_deep)
        self.assertRelationshipToMaxBOM(instance, self.maxbom_deep, self.var1)

        selection_condition.Delete()

        reinstantiate_parts([instance])

        self.assert_subassembly_structure(
            SubassemblyStructure(
                self.var1_part_maxbom_deep_keys,
                children=[self.maxbom_deep_subassembly_level1],
            ),
            self.var1_part_maxbom_deep,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(instance, self.maxbom_deep, self.var1)

    def test_reinstantiation_maxbom_var1_deep_with_sc_on_deepest_part_oc__removed_but_bom_added(
        self,
    ):
        selection_condition_for_oc = generate_selection_condition(
            self.variability_model,
            self.maxbom_deep_bom_item_occurrence2_level5,
            self.expression_valid_for_variant2,
        )

        instance = instantiate_part(self.var1, self.maxbom_deep)
        self.assertRelationshipToMaxBOM(instance, self.maxbom_deep, self.var1)

        generate_selection_condition(
            self.variability_model,
            self.maxbom_deep_bom_item_level5,
            self.expression_valid_for_variant1,
        )
        selection_condition_for_oc.Delete()

        reinstantiate_parts([instance])

        expected_level5 = SubassemblyStructure(
            self.copy_of_maxbom_deep_subassembly_level5_keys,
            children=[self.maxbom_deep_part_level5],
            occurrence_keys=[self.maxbom_deep_subassembly_level5_occurrence1_keys],
        )

        self.assert_maxbom_deep_level5(instance, expected_level5)
        self.assertRelationshipToMaxBOM(instance, self.maxbom_deep, self.var1)
