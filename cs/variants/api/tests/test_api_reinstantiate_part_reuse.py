#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/

from cdb.objects.operations import operation
from cdb.validationkit import SwitchRoles
from cs.variants.api import helpers, instantiate_part, reinstantiate_parts
from cs.variants.api.tests import maxbom_deep_wide_constants
from cs.variants.api.tests.reinstantiate_test_case import ReinstantiateTestCase
from cs.variants.api.tests.reuse_test_case import ReuseTestCase
from cs.variants.api.tests.subassembly_structure import SubassemblyStructure as Subst
from cs.variants.selection_condition import SelectionCondition
from cs.vp.bom import AssemblyComponent
from cs.vp.items import Item


class TestApiReInstantiatePartReuse(ReuseTestCase):
    def tearDown(self):
        super().tearDown()
        helpers.REUSE_ENABLED = False

    def setUp(self):
        super().setUp()
        helpers.REUSE_ENABLED = True

    def test_reinstantiate_var1_with_no_changes(self):
        part_to_reinstantiate = Item.ByKeys(**maxbom_deep_wide_constants.t9508629_keys)
        self.assertIsNotNone(part_to_reinstantiate)

        reinstantiate_parts([part_to_reinstantiate], self.maxbom_deep_wide)
        expected_result = Subst(
            {
                "teilenummer": part_to_reinstantiate.teilenummer,
                "t_index": part_to_reinstantiate.t_index,
            },
            children=[maxbom_deep_wide_constants.t9508630],
        )

        self.assert_subassembly_structure(
            expected_result, part_to_reinstantiate, assert_occurrences=True
        )
        self.assertRelationshipToMaxBOM(
            part_to_reinstantiate, self.maxbom_deep_wide, self.var1
        )

    def test_reinstantiate_var1_with_second_instance_and_no_changes(self):
        # second instance of v1 with reuse of assembly from first instance
        result = instantiate_part(self.var1, self.maxbom_deep_wide)
        expected_result = Subst(
            {"teilenummer": result.teilenummer, "t_index": result.t_index},
            children=[maxbom_deep_wide_constants.t9508630],
        )

        self.assert_subassembly_structure(
            expected_result, result, assert_occurrences=True
        )
        self.assertRelationshipToMaxBOM(result, self.maxbom_deep_wide, self.var1)

        part_to_reinstantiate = Item.ByKeys(**maxbom_deep_wide_constants.t9508629_keys)
        self.assertIsNotNone(part_to_reinstantiate)

        reinstantiate_parts([part_to_reinstantiate], self.maxbom_deep_wide)
        expected_result = maxbom_deep_wide_constants.t9508629

        self.assert_subassembly_structure(
            expected_result, part_to_reinstantiate, assert_occurrences=True
        )
        self.assertRelationshipToMaxBOM(
            part_to_reinstantiate, self.maxbom_deep_wide, self.var1
        )

    def test_reinstantiate_var1_with_second_instance_and_removed_sc(self):
        """
        do not update inplace if assembly has more then one usage

        must be create a new instance if the existing one is uses in other instances
        only the sc from bom_item with teilenummer "9508626" is removed
        """
        # second instance of v1 with reuse of assembly from first instance
        second_instance = instantiate_part(self.var1, self.maxbom_deep_wide)
        second_instance_expected_result = Subst(
            {
                "teilenummer": second_instance.teilenummer,
                "t_index": second_instance.t_index,
            },
            children=[maxbom_deep_wide_constants.t9508630],
        )

        self.assert_subassembly_structure(
            second_instance_expected_result, second_instance, assert_occurrences=True
        )
        self.assertRelationshipToMaxBOM(
            second_instance, self.maxbom_deep_wide, self.var1
        )

        bom_item_with_sc = AssemblyComponent.ByKeys(
            teilenummer=maxbom_deep_wide_constants.t9508626_teilenummer,
            t_index="",
            baugruppe=maxbom_deep_wide_constants.t9508624_teilenummer,
            b_index="",
        )
        sc = SelectionCondition.ByKeys(ref_object_id=bom_item_with_sc.cdb_object_id)
        sc.Delete()

        part_to_reinstantiate = Item.ByKeys(**maxbom_deep_wide_constants.t9508629_keys)
        self.assertIsNotNone(part_to_reinstantiate)
        teilenummer_lookup = Item.Query().teilenummer

        reinstantiate_parts([part_to_reinstantiate], self.maxbom_deep_wide)

        def check_teilenummer(value):
            return value not in teilenummer_lookup

        expected_result = Subst(
            {
                "teilenummer": part_to_reinstantiate.teilenummer,
                "t_index": part_to_reinstantiate.t_index,
            },
            children=[Subst({"teilenummer": check_teilenummer, "t_index": ""})],
        )

        self.assert_subassembly_structure(
            expected_result, part_to_reinstantiate, assert_occurrences=False
        )
        self.assertRelationshipToMaxBOM(
            part_to_reinstantiate, self.maxbom_deep_wide, self.var1
        )

        # check if second instance has not changed
        self.assert_subassembly_structure(
            second_instance_expected_result, second_instance, assert_occurrences=True
        )

    def test_reinstantiate_var1_with_no_second_instance_and_removed_sc(self):
        """
        Update existing instance inplace if assembly has only one usage

        Only the sc from bom_item with teilenummer "9508626" is removed
        """

        bom_item_with_sc = AssemblyComponent.ByKeys(
            teilenummer=maxbom_deep_wide_constants.t9508626_teilenummer,
            t_index="",
            baugruppe=maxbom_deep_wide_constants.t9508624_teilenummer,
            b_index="",
        )
        sc = SelectionCondition.ByKeys(ref_object_id=bom_item_with_sc.cdb_object_id)
        sc.Delete()

        part_to_reinstantiate = Item.ByKeys(**maxbom_deep_wide_constants.t9508629_keys)
        self.assertIsNotNone(part_to_reinstantiate)

        reinstantiate_parts([part_to_reinstantiate], self.maxbom_deep_wide)

        t9508633 = Subst(
            maxbom_deep_wide_constants.t9508633_keys,
            children=[
                maxbom_deep_wide_constants.t9508624,
                maxbom_deep_wide_constants.t9508635,
            ],
            # occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L4_P1_OC0_keys],
        )

        t9508632 = Subst(
            maxbom_deep_wide_constants.t9508632_keys,
            children=[t9508633],
            # occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L3_P1_OC0_keys],
        )
        t9508631 = Subst(
            maxbom_deep_wide_constants.t9508631_keys,
            children=[t9508632],
            # occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L2_P1_OC0_keys],
        )
        t9508630 = Subst(
            maxbom_deep_wide_constants.t9508630_keys,
            children=[t9508631],
            # occurrence_keys=[VAR_TEST_MAXBOM_DEEP_WIDE_L1_P1_OC0_keys],
        )

        expected_result = Subst(
            maxbom_deep_wide_constants.t9508629_keys,
            children=[t9508630],
        )

        self.assert_subassembly_structure(
            expected_result, part_to_reinstantiate, assert_occurrences=False
        )
        self.assertRelationshipToMaxBOM(
            part_to_reinstantiate, self.maxbom_deep_wide, self.var1
        )

    def test_reinstantiate_var1_with_second_instance_and_removed_sc_on_occ_no_change(
        self,
    ):
        """
        Removed sc on occ with no changes should not update

        We remove a sc on occ but this changes does not effect the result.
        The removed sc evaluates to True.
        Only the sc from occ "VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC0" is removed
        """
        # second instance of v1 with reuse of assembly from first instance
        second_instance = instantiate_part(self.var1, self.maxbom_deep_wide)
        second_instance_expected_result = Subst(
            {
                "teilenummer": second_instance.teilenummer,
                "t_index": second_instance.t_index,
            },
            children=[maxbom_deep_wide_constants.t9508630],
        )

        self.assert_subassembly_structure(
            second_instance_expected_result, second_instance, assert_occurrences=True
        )
        self.assertRelationshipToMaxBOM(
            second_instance, self.maxbom_deep_wide, self.var1
        )

        sc = SelectionCondition.ByKeys(
            ref_object_id=maxbom_deep_wide_constants.VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC0_object_id
        )
        self.assertIsNotNone(sc)
        sc.Delete()

        part_to_reinstantiate = Item.ByKeys(**maxbom_deep_wide_constants.t9508629_keys)
        self.assertIsNotNone(part_to_reinstantiate)

        reinstantiate_parts([part_to_reinstantiate], self.maxbom_deep_wide)

        self.assert_subassembly_structure(
            maxbom_deep_wide_constants.t9508629, part_to_reinstantiate
        )
        self.assertRelationshipToMaxBOM(
            part_to_reinstantiate, self.maxbom_deep_wide, self.var1
        )

    def test_reinstantiate_var1_with_second_instance_and_removed_sc_on_occ(self):
        """
        Do not update inplace if assembly has more then one usage

        Must be create a new instance if the existing one is uses in other instances
        Only the sc from occ "VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC0" is removed
        The removed sc evaluates to False
        """
        # second instance of v1 with reuse of assembly from first instance
        second_instance = instantiate_part(self.var1, self.maxbom_deep_wide)
        second_instance_expected_result = Subst(
            {
                "teilenummer": second_instance.teilenummer,
                "t_index": second_instance.t_index,
            },
            children=[maxbom_deep_wide_constants.t9508630],
        )

        self.assert_subassembly_structure(
            second_instance_expected_result, second_instance, assert_occurrences=True
        )
        self.assertRelationshipToMaxBOM(
            second_instance, self.maxbom_deep_wide, self.var1
        )

        sc = SelectionCondition.ByKeys(
            ref_object_id=maxbom_deep_wide_constants.VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC1_object_id
        )
        sc.Delete()

        part_to_reinstantiate = Item.ByKeys(**maxbom_deep_wide_constants.t9508629_keys)
        self.assertIsNotNone(part_to_reinstantiate)
        teilenummer_lookup = Item.Query().teilenummer

        reinstantiate_parts([part_to_reinstantiate], self.maxbom_deep_wide)

        def check_teilenummer(value):
            return value not in teilenummer_lookup

        expected_result = Subst(
            {
                "teilenummer": part_to_reinstantiate.teilenummer,
                "t_index": part_to_reinstantiate.t_index,
            },
            children=[Subst({"teilenummer": check_teilenummer, "t_index": ""})],
        )
        self.assert_subassembly_structure(expected_result, part_to_reinstantiate)
        self.assertRelationshipToMaxBOM(
            part_to_reinstantiate, self.maxbom_deep_wide, self.var1
        )

    def test_reinstantiate_var1_with_no_second_instance_and_removed_sc_on_occ(self):
        """
        Update existing instance inplace if assembly has only one usage

        Only the sc from occ "VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC0" is removed
        """
        sc = SelectionCondition.ByKeys(
            ref_object_id=maxbom_deep_wide_constants.VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_I2_OC0_object_id
        )
        self.assertIsNotNone(sc)
        sc.Delete()
        part_to_reinstantiate = Item.ByKeys(**maxbom_deep_wide_constants.t9508629_keys)
        self.assertIsNotNone(part_to_reinstantiate)

        reinstantiate_parts([part_to_reinstantiate], self.maxbom_deep_wide)

        self.assert_subassembly_structure(
            maxbom_deep_wide_constants.t9508629,
            part_to_reinstantiate,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            part_to_reinstantiate, self.maxbom_deep_wide, self.var1
        )

    def test_reinstantiate_var1_with_second_instance_and_removed_bom_item(self):
        """
        Do not update inplace if assembly has more then one usage

        Must be create a new instance if the existing one is uses in other instances
        Only a bom_item is removed
        """
        # second instance of v1 with reuse of assembly from first instance
        second_instance = instantiate_part(self.var1, self.maxbom_deep_wide)
        second_instance_expected_result = Subst(
            {
                "teilenummer": second_instance.teilenummer,
                "t_index": second_instance.t_index,
            },
            children=[maxbom_deep_wide_constants.t9508630],
        )

        self.assert_subassembly_structure(
            second_instance_expected_result, second_instance, assert_occurrences=True
        )
        self.assertRelationshipToMaxBOM(
            second_instance, self.maxbom_deep_wide, self.var1
        )

        bom_item_keys = {
            "baugruppe": maxbom_deep_wide_constants.t9508625_teilenummer,
            "b_index": maxbom_deep_wide_constants.t9508625_t_index,
            "teilenummer": maxbom_deep_wide_constants.t9508627_teilenummer,
            "t_index": maxbom_deep_wide_constants.t9508627_t_index,
            "position": 10,
        }
        bom_item_to_delete = AssemblyComponent.ByKeys(**bom_item_keys)
        self.assertIsNotNone(bom_item_to_delete)
        operation("CDB_Delete", bom_item_to_delete)

        part_to_reinstantiate = Item.ByKeys(**maxbom_deep_wide_constants.t9508629_keys)
        self.assertIsNotNone(part_to_reinstantiate)
        teilenummer_lookup = Item.Query().teilenummer

        reinstantiate_parts([part_to_reinstantiate], self.maxbom_deep_wide)

        def check_teilenummer(value):
            return value not in teilenummer_lookup

        expected_result = Subst(
            {
                "teilenummer": part_to_reinstantiate.teilenummer,
                "t_index": part_to_reinstantiate.t_index,
            },
            children=[Subst({"teilenummer": check_teilenummer, "t_index": ""})],
        )
        self.assert_subassembly_structure(expected_result, part_to_reinstantiate)
        self.assertRelationshipToMaxBOM(
            part_to_reinstantiate, self.maxbom_deep_wide, self.var1
        )

    @SwitchRoles.run_with_roles(["public", "Engineering"])
    def test_reinstantiate_var1_with_no_second_instance_and_released_pos(self):
        """
        Inplace update with new assembly on L5

        - 9508625 and 9508627, 9508628 are released
        - added new False rule to 9508627
        """
        t9508635 = Item.ByKeys(**maxbom_deep_wide_constants.t9508635_keys)
        t9508627 = Item.ByKeys(**maxbom_deep_wide_constants.t9508627_keys)
        t9508628 = Item.ByKeys(**maxbom_deep_wide_constants.t9508628_keys)

        t9508627.status = 200
        t9508628.status = 200
        t9508635.status = 200

        t9508627.Reload()
        t9508628.Reload()
        t9508635.Reload()

        new_sc = operation(
            "CDB_Create",
            SelectionCondition,
            variability_model_id=self.variability_model_id_multi,
            ref_object_id=maxbom_deep_wide_constants.t9508627_bom_item_object_id,
            expression="False",
        )
        self.assertIsNotNone(new_sc)

        teilenummer_lookup = Item.Query().teilenummer

        def check_teilenummer(value):
            return value not in teilenummer_lookup

        part_to_reinstantiate = Item.ByKeys(**maxbom_deep_wide_constants.t9508629_keys)
        self.assertIsNotNone(part_to_reinstantiate)

        reinstantiate_parts([part_to_reinstantiate], self.maxbom_deep_wide)

        t9508633 = Subst(
            maxbom_deep_wide_constants.t9508633_keys,
            children=[
                maxbom_deep_wide_constants.t9508634,
                Subst(
                    {"teilenummer": check_teilenummer},
                    occurrence_keys=[
                        maxbom_deep_wide_constants.VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2_OC0_keys
                    ],
                ),
            ],
            occurrence_keys=[
                maxbom_deep_wide_constants.VAR_TEST_MAXBOM_DEEP_WIDE_L4_P1_OC0_keys
            ],
        )

        t9508632 = Subst(
            maxbom_deep_wide_constants.t9508632_keys,
            children=[t9508633],
            occurrence_keys=[
                maxbom_deep_wide_constants.VAR_TEST_MAXBOM_DEEP_WIDE_L3_P1_OC0_keys
            ],
        )
        t9508631 = Subst(
            maxbom_deep_wide_constants.t9508631_keys,
            children=[t9508632],
            occurrence_keys=[
                maxbom_deep_wide_constants.VAR_TEST_MAXBOM_DEEP_WIDE_L2_P1_OC0_keys
            ],
        )
        t9508630 = Subst(
            maxbom_deep_wide_constants.t9508630_keys,
            children=[t9508631],
            occurrence_keys=[
                maxbom_deep_wide_constants.VAR_TEST_MAXBOM_DEEP_WIDE_L1_P1_OC0_keys
            ],
        )
        t9508629 = Subst(
            maxbom_deep_wide_constants.t9508629_keys,
            children=[t9508630],
        )

        self.assert_subassembly_structure(
            t9508629,
            part_to_reinstantiate,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            part_to_reinstantiate, self.maxbom_deep_wide, self.var1
        )

    @SwitchRoles.run_with_roles(["public", "Engineering"])
    def test_reinstantiate_var1_with_second_instance_and_released_pos(self):
        """
        create new assembly on L1

        - 9508625 and 9508627, 9508628 are released
        - second instance with reuse instantiated
        - added new False rule to 9508627
        """
        t9508635 = Item.ByKeys(**maxbom_deep_wide_constants.t9508635_keys)
        t9508627 = Item.ByKeys(**maxbom_deep_wide_constants.t9508627_keys)
        t9508628 = Item.ByKeys(**maxbom_deep_wide_constants.t9508628_keys)

        t9508627.status = 200
        t9508628.status = 200
        t9508635.status = 200

        t9508627.Reload()
        t9508628.Reload()
        t9508635.Reload()

        second_instance = instantiate_part(self.var1, self.maxbom_deep_wide)

        # check
        second_instance_expected_result = Subst(
            {
                "teilenummer": second_instance.teilenummer,
                "t_index": second_instance.t_index,
            },
            children=[maxbom_deep_wide_constants.t9508630],
        )
        self.assert_subassembly_structure(
            second_instance_expected_result, second_instance, assert_occurrences=True
        )
        self.assertRelationshipToMaxBOM(
            second_instance, self.maxbom_deep_wide, self.var1
        )

        new_sc = operation(
            "CDB_Create",
            SelectionCondition,
            variability_model_id=self.variability_model_id_multi,
            ref_object_id=maxbom_deep_wide_constants.t9508627_bom_item_object_id,
            expression="1 == 0",
        )

        self.assertIsNotNone(new_sc)

        teilenummer_lookup = Item.Query().teilenummer

        def check_teilenummer(value):
            return value not in teilenummer_lookup

        part_to_reinstantiate = Item.ByKeys(**maxbom_deep_wide_constants.t9508629_keys)
        self.assertIsNotNone(part_to_reinstantiate)

        reinstantiate_parts([part_to_reinstantiate], self.maxbom_deep_wide)

        t9508629 = Subst(
            maxbom_deep_wide_constants.t9508629_keys,
            children=[
                Subst(
                    {"teilenummer": check_teilenummer},
                    occurrence_keys=[
                        maxbom_deep_wide_constants.VAR_TEST_MAXBOM_DEEP_WIDE_L1_P1_OC0_keys
                    ],
                )
            ],
        )

        self.assert_subassembly_structure(
            t9508629,
            part_to_reinstantiate,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            part_to_reinstantiate, self.maxbom_deep_wide, self.var1
        )

    def test_reinstantiate_var1_with_indirect_reuse(self):
        """
        detect indirect usage and replace it with a new assembly

        mostly identicaly to the test `test_reinstantiate_var1_with_second_instance_and_released_pos`

        we are creating a new bom_item in another maxbom with the part 9508632.
        this part uses the part t9508635 indirect.

        :return:
        """
        t9508635 = Item.ByKeys(**maxbom_deep_wide_constants.t9508635_keys)
        t9508627 = Item.ByKeys(**maxbom_deep_wide_constants.t9508627_keys)
        t9508628 = Item.ByKeys(**maxbom_deep_wide_constants.t9508628_keys)

        t9508627.status = 200
        t9508628.status = 200
        t9508635.status = 200

        t9508627.Reload()
        t9508628.Reload()
        t9508635.Reload()

        new_sc = operation(
            "CDB_Create",
            SelectionCondition,
            variability_model_id=self.variability_model_id_multi,
            ref_object_id=maxbom_deep_wide_constants.t9508627_bom_item_object_id,
            expression="False",
        )
        self.assertIsNotNone(new_sc)

        # we are creating a new bom_item in another maxbom
        # this is the indirect usage of the bom_item 9508635 / 20
        bom_item = operation(
            "CDB_Create",
            AssemblyComponent,
            baugruppe="9508607",
            b_index="",
            teilenummer="9508632",
            t_index="",
            position=20,
            variante="0",
            auswahlmenge=0.0,
        )
        self.assertIsNotNone(bom_item)

        teilenummer_lookup = Item.Query().teilenummer

        def check_teilenummer(value):
            return value not in teilenummer_lookup

        part_to_reinstantiate = Item.ByKeys(**maxbom_deep_wide_constants.t9508629_keys)
        self.assertIsNotNone(part_to_reinstantiate)

        reinstantiate_parts([part_to_reinstantiate], self.maxbom_deep_wide)

        t9508631 = Subst(
            maxbom_deep_wide_constants.t9508631_keys,
            children=[
                Subst(
                    {"teilenummer": check_teilenummer},
                    occurrence_keys=[
                        maxbom_deep_wide_constants.VAR_TEST_MAXBOM_DEEP_WIDE_L3_P1_OC0_keys
                    ],
                ),
            ],
            occurrence_keys=[
                maxbom_deep_wide_constants.VAR_TEST_MAXBOM_DEEP_WIDE_L2_P1_OC0_keys
            ],
        )
        t9508630 = Subst(
            maxbom_deep_wide_constants.t9508630_keys,
            children=[t9508631],
            occurrence_keys=[
                maxbom_deep_wide_constants.VAR_TEST_MAXBOM_DEEP_WIDE_L1_P1_OC0_keys
            ],
        )
        t9508629 = Subst(
            maxbom_deep_wide_constants.t9508629_keys,
            children=[t9508630],
        )

        self.assert_subassembly_structure(
            t9508629,
            part_to_reinstantiate,
            assert_occurrences=True,
        )
        self.assertRelationshipToMaxBOM(
            part_to_reinstantiate, self.maxbom_deep_wide, self.var1
        )

    def test_reinstantiate_var1_extending_sc_another_usage(self):
        """
        after reinstantiate the additional cls properties must be updated (has_somewhere_deep_changed)

        creating a new sc (false) and make sure the part is used elsewhere

        we are testing the path with has_somewhere_deep_changed -> _replace_instance

        Note:
            This test is dependent on the correct flow path. I have tested this with a debug point.
            The test itself is also green if a different flow path is used.
            It would therefore be better to mock the corresponding functions and explicitly
            check that the correct functions are actually called.
        """
        part_to_reinstantiate = Item.ByKeys(**maxbom_deep_wide_constants.t9508629_keys)
        self.assertIsNotNone(part_to_reinstantiate)

        part_to_check = Item.ByKeys(**maxbom_deep_wide_constants.t9508635_keys)
        self.assertIsNotNone(part_to_check)

        new_sc = operation(
            "CDB_Create",
            SelectionCondition,
            variability_model_id=self.variability_model_id_multi,
            ref_object_id=maxbom_deep_wide_constants.t9508627_bom_item_object_id,
            expression='VAR_TEST_REINSTANTIATE_MULTI_VAR_TEST_TEXT == "VALUE1"',
        )
        self.assertIsNotNone(new_sc)

        # we are creating a new bom_item in another maxbom
        bom_item = operation(
            "CDB_Create",
            AssemblyComponent,
            baugruppe="9508607",
            b_index="",
            teilenummer="9508635",
            t_index="",
            position=20,
            variante="0",
            auswahlmenge=0.0,
        )
        self.assertIsNotNone(bom_item)

        reinstantiate_parts([part_to_reinstantiate], self.maxbom_deep_wide)
        part_to_reinstantiate.Reload()

        new_part = (
            part_to_reinstantiate.Components[0]
            .Item.Components[0]
            .Item.Components[0]
            .Item.Components[0]
            .Item.Components[1]
            .Item
        )
        self.assertEqual(new_part.benennung, "VAR_TEST_MAXBOM_DEEP_WIDE_L5_P2")
        self.assertRelationshipToMaxBOM(
            part_to_reinstantiate, self.maxbom_deep_wide, self.var1
        )

    def test_reinstantiate_reuse_over_inplace_update(self):
        # reuse existing instance is higher prior then inplace update existing
        second_instance = instantiate_part(self.var1, self.maxbom_deep_wide)
        expected_result = Subst(
            {
                "teilenummer": second_instance.teilenummer,
                "t_index": second_instance.t_index,
            },
            children=[maxbom_deep_wide_constants.t9508630],
        )

        self.assert_subassembly_structure(
            expected_result, second_instance, assert_occurrences=True
        )
        self.assertRelationshipToMaxBOM(
            second_instance, self.maxbom_deep_wide, self.var1
        )

        # create a new false rule on 9508627 must result in a new instance
        new_sc = operation(
            "CDB_Create",
            SelectionCondition,
            variability_model_id=self.variability_model_id_multi,
            ref_object_id=maxbom_deep_wide_constants.t9508627_bom_item_object_id,
            expression="False",
        )
        self.assertIsNotNone(new_sc)

        teilenummer_lookup = Item.Query().teilenummer

        def check_teilenummer(value):
            return value not in teilenummer_lookup

        reinstantiate_parts([second_instance])

        reinstantiated_expected_result = Subst(
            {
                "teilenummer": second_instance.teilenummer,
                "t_index": second_instance.t_index,
            },
            children=[
                Subst(
                    {"teilenummer": check_teilenummer},
                    occurrence_keys=[
                        maxbom_deep_wide_constants.VAR_TEST_MAXBOM_DEEP_WIDE_L1_P1_OC0_keys
                    ],
                ),
            ],
        )

        self.assert_subassembly_structure(
            reinstantiated_expected_result, second_instance, assert_occurrences=True
        )
        self.assertRelationshipToMaxBOM(
            second_instance, self.maxbom_deep_wide, self.var1
        )

        new_part = second_instance.Components[0].Item
        part_to_reinstantiate = Item.ByKeys(**maxbom_deep_wide_constants.t9508629_keys)
        self.assertIsNotNone(part_to_reinstantiate)

        reinstantiate_parts([part_to_reinstantiate])

        now_part = part_to_reinstantiate.Components[0].Item
        self.assertEqual(new_part.teilenummer, now_part.teilenummer)
        self.assertRelationshipToMaxBOM(
            part_to_reinstantiate, self.maxbom_deep_wide, self.var1
        )

    def test_no_reuse_if_lower_assembly_must_be_instantiated(self):
        """
        The checksum was previously only calculated at the top level of the assembly.
        This means that changes in lower structures were not taken into account in the
        checksum of the assemblies above. Therefore, assemblies were found for reuse
        which had changed deeply and therefore should not have been reused.
        This is what this test is intended to safeguard.

        The part 9508649 was instantiated with the Rule on 9508598/10. This is the
        reason we add this rule again.

        It is important that the second rule is at least 2 levels deeper than the first rule.

        :return:
        """
        part_to_reinstantiate = Item.ByKeys(teilenummer="9508649", t_index="")
        self.assertIsNotNone(part_to_reinstantiate)

        expected_structure = Subst(
            {"teilenummer": "9508649", "t_index": ""},
            children=[
                Subst(
                    {"teilenummer": "9508650", "t_index": ""},
                    children=[ReinstantiateTestCase.maxbom_deep_subassembly_level2],
                ),
            ],
        )

        self.assert_subassembly_structure(
            expected_structure, part_to_reinstantiate, assert_occurrences=False
        )

        # teilenummer=9508598
        new_sc = operation(
            "CDB_Create",
            SelectionCondition,
            variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c",
            ref_object_id="0fdd2038-ca9b-11eb-b955-98fa9bf98f6d",
            expression="True",
        )
        self.assertIsNotNone(new_sc)

        # teilenummer=9508600
        new_sc = operation(
            "CDB_Create",
            SelectionCondition,
            variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c",
            ref_object_id="22adcaf5-ca9b-11eb-b955-98fa9bf98f6d",
            expression="False",
        )
        self.assertIsNotNone(new_sc)

        teilenummer_lookup = Item.Query().teilenummer

        def check_teilenummer(value):
            return value not in teilenummer_lookup

        reinstantiate_parts([part_to_reinstantiate])

        expected_structure = Subst(
            {"teilenummer": "9508649", "t_index": ""},
            children=[
                Subst(
                    {"teilenummer": "9508650", "t_index": ""},
                    children=[
                        Subst(
                            {"teilenummer": check_teilenummer},
                        )
                    ],
                ),
            ],
        )

        self.assert_subassembly_structure(
            expected_structure, part_to_reinstantiate, assert_occurrences=False
        )
        self.assertRelationshipToMaxBOM(
            part_to_reinstantiate, self.maxbom_deep_without_index, self.var1_normal
        )
