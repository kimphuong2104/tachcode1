#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from cdb.objects.operations import operation
from cs.variants import Variant
from cs.variants.api import helpers, instantiate_part, reinstantiate_parts
from cs.variants.api.tests import maxbom_multi_reuse_constants
from cs.variants.api.tests.base_test_case import BaseTestCase
from cs.variants.api.tests.subassembly_structure import SubassemblyStructure as Subst
from cs.variants.selection_condition import SelectionCondition
from cs.vp import bom, items


class TestApiReinstantiateMulitReuse(BaseTestCase):
    def setUp(self):
        super().setUp()
        self._reuse_enabled = helpers.REUSE_ENABLED
        helpers.REUSE_ENABLED = True

    def tearDown(self):
        super().tearDown()
        helpers.REUSE_ENABLED = self._reuse_enabled

    def test_instantiate_reuse_instantiated_part_while_instantiate(self):
        """
        Must reuse a previously instantiated part
        :return:
        """
        max_bom = items.Item.ByKeys(**maxbom_multi_reuse_constants.t9508651_keys)
        self.assertIsNotNone(max_bom)
        self.assert_subassembly_structure(
            maxbom_multi_reuse_constants.t9508651, max_bom
        )

        variant = Variant.ByKeys(
            variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="1"
        )
        self.assertIsNotNone(variant)

        new_instance = instantiate_part(variant, max_bom)

        first_teilenummer = new_instance.Components[0].Item.Components[0].teilenummer
        second_teilenummer = new_instance.Components[1].Item.Components[0].teilenummer

        self.assertRelationshipToMaxBOM(new_instance, max_bom, variant)
        self.assertEqual(first_teilenummer, second_teilenummer)

    def test_reinstantiate_reuse_part_while_instantiate(self):
        """
        Must reuse an instantiated part during same reinstantiation process

        Part is created in position a and must be reused in position b
        :return:
        """
        max_bom = items.Item.ByKeys(**maxbom_multi_reuse_constants.t9508651_keys)
        self.assertIsNotNone(max_bom)
        self.assert_subassembly_structure(
            maxbom_multi_reuse_constants.t9508651, max_bom
        )
        variant = Variant.ByKeys(
            variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="1"
        )
        self.assertIsNotNone(variant)

        selection_con = SelectionCondition.ByKeys(
            cdb_object_id="1c392441-4c50-11ec-924b-f875a45b4131"
        )
        self.assertIsNotNone(selection_con)
        operation("CDB_Delete", selection_con)

        new_instance = instantiate_part(variant, max_bom)

        expected_st = Subst(
            {
                "teilenummer": new_instance.teilenummer,
                "t_index": new_instance.t_index,
            },
            children=[
                maxbom_multi_reuse_constants.t9508652,
                maxbom_multi_reuse_constants.t9508653,
            ],
        )
        self.assert_subassembly_structure(expected_st, new_instance)
        self.assertRelationshipToMaxBOM(new_instance, max_bom, variant)

        new_sc = operation(
            "CDB_Create",
            SelectionCondition,
            variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c",
            ref_object_id="86a2be61-4c4f-11ec-924b-f875a45b4131",
            expression="False",
        )
        self.assertIsNotNone(new_sc)

        reinstantiate_parts([new_instance])

        # the same part must be reused on other position
        first_teilenummer = new_instance.Components[0].Item.Components[0].teilenummer
        second_teilenummer = new_instance.Components[1].Item.Components[0].teilenummer

        self.assertEqual(first_teilenummer, second_teilenummer)
        self.assertRelationshipToMaxBOM(new_instance, max_bom, variant)

    def test_instantiate_without_occ(self):
        """
        without occ and no other changes must reuse existing parts

        Test for checking menge attribute

        :return:
        """
        max_bom = items.Item.ByKeys(**maxbom_multi_reuse_constants.t9508651_keys)
        self.assertIsNotNone(max_bom)
        self.assert_subassembly_structure(
            maxbom_multi_reuse_constants.t9508651, max_bom
        )
        variant = Variant.ByKeys(
            variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="1"
        )
        self.assertIsNotNone(variant)

        new_instance = instantiate_part(variant, max_bom)
        expected_st = Subst(
            {
                "teilenummer": new_instance.teilenummer,
                "t_index": new_instance.t_index,
            },
            children=[
                maxbom_multi_reuse_constants.t9508657,
                maxbom_multi_reuse_constants.t9508659,
            ],
        )
        self.assert_subassembly_structure(expected_st, new_instance)

    def test_instantiate_without_occ_and_changed_menge(self):
        """
        without occ and changed menge in already instantiated part must create new one

        Test for checking menge attribute

        :return:
        """
        max_bom = items.Item.ByKeys(**maxbom_multi_reuse_constants.t9508651_keys)
        self.assertIsNotNone(max_bom)
        self.assert_subassembly_structure(
            maxbom_multi_reuse_constants.t9508651, max_bom
        )
        variant = Variant.ByKeys(
            variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="1"
        )
        self.assertIsNotNone(variant)

        bom_item = bom.AssemblyComponent.ByKeys(
            **{
                "b_index": "",
                "baugruppe": "9508657",
                "t_index": "",
                "teilenummer": "9508658",
            }
        )
        bom_item.menge = 2

        teilenummer_lookup = items.Item.Query().teilenummer

        def check_teilenummer(value):
            return value not in teilenummer_lookup

        new_instance = instantiate_part(variant, max_bom)
        expected_st = Subst(
            {
                "teilenummer": new_instance.teilenummer,
                "t_index": new_instance.t_index,
            },
            children=[
                Subst({"teilenummer": check_teilenummer, "t_index": ""}),
                maxbom_multi_reuse_constants.t9508659,
            ],
        )
        self.assert_subassembly_structure(expected_st, new_instance)
