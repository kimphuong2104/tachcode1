# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from cdb import testcase
from cdbwrapc import StatusInfo
from cs.classification.api import compare_classification
from cs.variants import Variant, VariantPart, VariantSubPart
from cs.variants.api import instantiate_part
from cs.variants.api.instantiate import (
    _copy_bom_item,
    _create_instance,
    _make_bom_item_occurrence_only_specific_keys,
    _update_occurrences,
    get_instantiated_of,
    make_indexed_instance,
    make_root_instance,
    make_sub_instance,
)
from cs.variants.api.instantiate_lookup import InstantiateLookup
from cs.variants.api.instantiate_options import InstantiateOptions
from cs.variants.api.tests.reinstantiate_test_case import ReinstantiateTestCase
from cs.variants.api.tests.subassembly_structure import SubassemblyStructure
from cs.variants.api.variant_bom_node import VariantBomNode
from cs.variants.exceptions import SelectionConditionEvaluationError
from cs.variants.selection_condition import SelectionCondition
from cs.vp import items
from cs.vp.bom import AssemblyComponent, AssemblyComponentOccurrence


class TestGetInstantiatedOf(testcase.RollbackTestCase):
    def test_get_non_existing_var_model(self):
        result = get_instantiated_of("nix", "4b8d39c6-ea0c-11eb-923d-f875a45b4131")
        self.assertEqual(None, result)

    def test_get_non_existing_part(self):
        result = get_instantiated_of("39a54ecc-2401-11eb-9218-24418cdf379c", "nix")
        self.assertEqual(None, result)

    def test_get_existing(self):
        result = get_instantiated_of(
            "39a54ecc-2401-11eb-9218-24418cdf379c",
            "4b8d39c6-ea0c-11eb-923d-f875a45b4131",
        )
        self.assertEqual("b1752105-a1d9-11eb-b94b-98fa9bf98f6d", result)


class DummyLookup:
    def __init__(self, variant):
        self.variant = variant
        self.reinstantiate_lookup = {}


class TestMakeInstantiate(testcase.RollbackTestCase):
    def test_make_root_instance_wrong_maxbom_type(self):
        variant = Variant.ByKeys(
            variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="1"
        )
        with self.assertRaises(TypeError):
            make_root_instance(variant, variant)

    def test_make_root_instance(self):
        """
        The make_instance method will generate a link to the variant and the maxbom

        we also check the following
            * status
            * materialnr_erp
            * cdb_copy_of_item_id attribute
            * no new entry in variant_sub_part table
            * classification copied from variant
            * instance prefixed with variant number
        """
        VariantSubPart.Query().Delete()
        variant = Variant.ByKeys(
            variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="1"
        )
        maxbom = items.Item.ByKeys(teilenummer="9508575", t_index="")
        self.assertIsNotNone(maxbom, "maxbom not found")
        expected_status = 0

        maxbom_name = maxbom.GetLocalizedValue("i18n_benennung", "de")
        self.assertNotEqual(maxbom_name, "")
        expected_instance_name = "Var{0}-{1}".format(variant.id, maxbom_name)

        instance = make_root_instance(maxbom, variant)
        self.assertIsNotNone(instance, "instance not created")

        self.assertEqual(
            instance.GetLocalizedValue("i18n_benennung", "de"), expected_instance_name
        )
        self.assertEqual(instance.materialnr_erp, instance.teilenummer)

        instance_link = VariantPart.ByKeys(
            variability_model_id=variant.variability_model_id,
            variant_id=variant.id,
            maxbom_teilenummer=maxbom.teilenummer,
            maxbom_t_index=maxbom.t_index,
            teilenummer=instance.teilenummer,
            t_index=instance.t_index,
        )

        self.assertIsNotNone(instance_link)

        self.assertEqual(instance.status, expected_status)

        sub_parts = VariantSubPart.Query().Execute()

        self.assertEqual(len(sub_parts), 0)

        cls_compare = compare_classification(variant, instance)
        self.assertTrue(cls_compare["classification_is_equal"])

    def test_make_sub_instance_wrong_type(self):
        variant = Variant.ByKeys(
            variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="1"
        )
        with self.assertRaises(TypeError):
            make_sub_instance(variant, VariantBomNode(None), DummyLookup(variant))

    def test_make_sub_instance_from_item(self):
        VariantSubPart.Query().Delete()
        variant = Variant.ByKeys(
            variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="1"
        )
        maxbom = items.Item.ByKeys(teilenummer="9508579", t_index="")
        self.assertIsNotNone(maxbom, "maxbom not found")
        expected_status = 0

        instance = make_sub_instance(maxbom, VariantBomNode(None), DummyLookup(variant))
        self.assertIsNotNone(instance, "instance not created")
        self.assertEqual(instance.materialnr_erp, instance.teilenummer)

        instance_link = VariantPart.ByKeys(
            variability_model_id=variant.variability_model_id,
            variant_id=variant.id,
            maxbom_teilenummer=maxbom.teilenummer,
            maxbom_t_index=maxbom.t_index,
            teilenummer=instance.teilenummer,
            t_index=instance.t_index,
        )

        self.assertIsNone(instance_link)

        self.assertEqual(instance.status, expected_status)

        sub_parts = VariantSubPart.Query().Execute()

        self.assertEqual(len(sub_parts), 1)

    def test_make_sub_instance_from_bom_item(self):
        VariantSubPart.Query().Delete()
        variant = Variant.ByKeys(
            variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="1"
        )
        bom_item = AssemblyComponent.ByKeys(
            cdb_object_id="c5d91658-a1da-11eb-b94b-98fa9bf98f6d"
        )
        self.assertIsNotNone(bom_item, "bom_item not found")
        expected_status = 0

        instance = make_sub_instance(
            bom_item, VariantBomNode(None), DummyLookup(variant)
        )
        self.assertIsNotNone(instance, "instance not created")
        self.assertEqual(instance.materialnr_erp, instance.teilenummer)

        instance_link = VariantPart.ByKeys(
            variability_model_id=variant.variability_model_id,
            variant_id=variant.id,
            maxbom_teilenummer=bom_item.teilenummer,
            maxbom_t_index=bom_item.t_index,
            teilenummer=instance.teilenummer,
            t_index=instance.t_index,
        )

        self.assertIsNone(instance_link)

        self.assertEqual(instance.status, expected_status)

        sub_parts = VariantSubPart.Query().Execute()

        self.assertEqual(len(sub_parts), 1)

    def test_make_indexed_instance(self):
        """
        create an index of a variant part.

        this also checks that the variant classification has been copied.

        :return:
        """
        VariantSubPart.Query().Delete()
        variant = Variant.ByKeys(
            variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="1"
        )
        maxbom_test = items.Item.KeywordQuery(teilenummer="9508605")
        self.assertEqual(len(maxbom_test), 1)
        maxbom_to_index = items.Item.ByKeys(teilenummer="9508605", t_index="")

        indexed_part = make_indexed_instance(maxbom_to_index)
        self.assertIsNotNone(indexed_part, "instance not created")
        self.assertEqual(indexed_part.materialnr_erp, indexed_part.teilenummer)

        instance_link = VariantPart.ByKeys(
            variability_model_id=variant.variability_model_id,
            variant_id=variant.id,
            maxbom_teilenummer=maxbom_test.teilenummer,
            maxbom_t_index=maxbom_test.t_index,
            teilenummer=indexed_part.teilenummer,
            t_index=indexed_part.t_index,
        )

        self.assertIsNotNone(instance_link)

        sub_parts = VariantSubPart.Query().Execute()
        self.assertEqual(len(sub_parts), 0)

        cls_compare = compare_classification(variant, indexed_part)
        self.assertTrue(cls_compare["classification_is_equal"])

    def test_make_subinstance_new_part_state_correct_maxbom_not_released(self):
        """The make_instance method will copy the variant classification"""
        maxbom = items.Item.ByKeys(teilenummer="9508602", t_index="")
        variant = Variant.ByKeys(
            variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="1"
        )
        instance = make_sub_instance(maxbom, VariantBomNode(None), DummyLookup(variant))

        expected_status_txt = StatusInfo(maxbom.cdb_objektart, 0).getStatusTxt()

        self.assertEqual(0, instance.status)
        self.assertEqual(expected_status_txt, instance.cdb_status_txt)
        self.assertEqual(instance.materialnr_erp, instance.teilenummer)

    def test_make_subinstance_new_part_state_correct_maxbom_is_released(self):
        """The make_instance method will copy the variant classification"""
        maxbom = items.Item.ByKeys(teilenummer="9508602", t_index="")
        variant = Variant.ByKeys(
            variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="1"
        )
        maxbom.ChangeState(200)

        instance = make_sub_instance(maxbom, VariantBomNode(None), DummyLookup(variant))

        expected_status_txt = StatusInfo(maxbom.cdb_objektart, 0).getStatusTxt()

        self.assertEqual(0, instance.status)
        self.assertEqual(expected_status_txt, instance.cdb_status_txt)
        self.assertEqual(instance.materialnr_erp, instance.teilenummer)

    def test_create_instance_no_copy_relships(self):
        item = items.Item.ByKeys(teilenummer="9508391", t_index="")
        self.assertIsNotNone(item)

        new_instance = _create_instance(item)

        self.assertIsNotNone(new_instance)

        self.assertEqual(len(new_instance.Documents), 0)
        self.assertEqual(len(new_instance.Components), 0)
        self.assertEqual(len(new_instance.Products), 0)

    def test_create_instance_customizing_function_called(self):
        """check if customizing methods are called"""
        item = items.Item.ByKeys(teilenummer="9508391", t_index="")
        self.assertIsNotNone(item)

        self.copy_pre_callback_called = False
        self.relship_copy_pre_callback_called = False
        expected_instance_type = "blub"

        def _copy_pre_callback(cls, ctx, flag):
            self.copy_pre_callback_called = True
            self.assertEqual(flag, expected_instance_type)

        def _relship_copy_callback(cls, ctx, flag):
            self.relship_copy_pre_callback_called = True
            self.assertEqual(flag, expected_instance_type)

        orig_copy_pre = items.Item.handle_instantiate_copy_pre
        orig_copyrelship = items.Item.handle_instantiate_copy_relships
        items.Item.handle_instantiate_copy_pre = _copy_pre_callback
        items.Item.handle_instantiate_copy_relships = _relship_copy_callback

        _create_instance(item, instance_type=expected_instance_type)

        items.Item.handle_instantiate_copy_pre = orig_copy_pre
        items.Item.handle_instantiate_copy_relships = orig_copyrelship

        self.assertTrue(self.copy_pre_callback_called)
        self.assertTrue(self.relship_copy_pre_callback_called)


class TestUpdateOccurrence(testcase.RollbackTestCase):
    def test_bom_item_has_no_occ(self):
        bom_item = AssemblyComponent.ByKeys(
            cdb_object_id="8d9746d4-8ca5-11eb-b944-98fa9bf98f6d"
        )
        item = items.Item.ByKeys(teilenummer="9508580", t_index="")
        subinstance = _create_instance(item)

        v_bom_node = VariantBomNode(bom_item)
        expected_menge = bom_item.menge
        occ = bom_item.Occurrences.Execute()
        self.assertEqual(len(occ), 0)

        new_bom_item = _copy_bom_item(v_bom_node, item, subinstance)
        self.assertIsNotNone(new_bom_item)
        self.assertEqual(len(new_bom_item.Occurrences.Execute()), 0)

        _update_occurrences(v_bom_node, new_bom_item, False)
        bom_item.Reload()
        self.assertEqual(bom_item.menge, expected_menge)

    def test_update_occurrences(self):
        # teilenummer=9508580
        # baugruppe=9508575
        bom_item_to_copy = AssemblyComponent.ByKeys(
            cdb_object_id="b83b3015-a1da-11eb-b94b-98fa9bf98f6d"
        )
        occ_to_copy = bom_item_to_copy.Occurrences.Execute()
        self.assertEqual(len(occ_to_copy), 2)

        item = items.Item.ByKeys(teilenummer="9508580", t_index="")
        v_bom_node = VariantBomNode(bom_item_to_copy)
        v_bom_node.has_sc_on_oc = True  # we set this manually to avoid build the tree
        v_bom_node.occurrences = occ_to_copy

        subinstance = _create_instance(item)
        new_bom_item = _copy_bom_item(v_bom_node, item, subinstance)
        self.assertIsNotNone(new_bom_item)
        self.assertEqual(len(new_bom_item.Occurrences.Execute()), 0)

        _update_occurrences(v_bom_node, new_bom_item, False)
        new_bom_item.Reload()

        self.assertEqual(new_bom_item.menge, 2)

        occ = new_bom_item.Occurrences.Execute()
        self.assertEqual(len(occ), 2)


class TestCopy(testcase.RollbackTestCase):
    def test_copy_bom_item(self):
        bom_item_to_copy = AssemblyComponent.ByKeys(
            cdb_object_id="b83b3015-a1da-11eb-b94b-98fa9bf98f6d"
        )

        item = items.Item.ByKeys(teilenummer="9508580", t_index="")
        v_bom_node = VariantBomNode(bom_item_to_copy)

        subinstance = _create_instance(item)

        existing_bom_items = AssemblyComponent.KeywordQuery(
            baugruppe=item.teilenummer,
            b_index=item.t_index,
            teilenummer=subinstance.teilenummer,
            t_index=subinstance.t_index,
        )

        self.assertEqual(len(existing_bom_items), 0)

        new_bom_item = _copy_bom_item(v_bom_node, item, subinstance)

        self.assertIsNotNone(new_bom_item)

        self.assertEqual(new_bom_item.baugruppe, item.teilenummer)
        self.assertEqual(new_bom_item.b_index, item.t_index)
        self.assertEqual(new_bom_item.teilenummer, subinstance.teilenummer)
        self.assertEqual(new_bom_item.t_index, subinstance.t_index)


class TestCollectModifications(ReinstantiateTestCase):
    def test_no_changes(self):
        variant = Variant.ByKeys(
            variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="1"
        )
        maxbom = items.Item.ByKeys(**ReinstantiateTestCase.maxbom_keys)
        instance_to_clean = items.Item.ByKeys(**ReinstantiateTestCase.var1_part3_keys)
        lookup = InstantiateLookup(maxbom, variant)
        lookup.build_variant_bom()
        lookup.collect_modifications(instance_to_clean)

        self.assert_keys(
            self.maxbom_part2_keys, lookup.variant_bom.children[1].ref_to_bom_item
        )
        self.assert_keys(
            self.var1_part3_subassembly1_keys,
            lookup.variant_bom.children[0].ref_to_bom_item,
        )
        self.assertListEqual(lookup.variant_bom.bom_items_to_delete, [])

    def test_removed_bom_item_from_variant_bom(self):
        variant = Variant.ByKeys(
            variability_model_id="39a54ecc-2401-11eb-9218-24418cdf379c", id="1"
        )
        maxbom = items.Item.ByKeys(**ReinstantiateTestCase.maxbom_keys)
        instance_to_clean = items.Item.ByKeys(**ReinstantiateTestCase.var1_part3_keys)
        lookup = InstantiateLookup(maxbom, variant)
        lookup.build_variant_bom()
        del lookup.variant_bom.children[1]

        self.assert_subassembly_structure(
            SubassemblyStructure(
                self.var1_part3_keys,
                children=[
                    self.expected_maxbom_part2,
                    self.expected_var1_part3_subassembly1_structure,
                ],
            ),
            instance_to_clean,
        )
        lookup.collect_modifications(instance_to_clean)

        self.assertEqual(len(lookup.variant_bom.bom_items_to_delete), 1)

        self.assertEqual(
            lookup.variant_bom.bom_items_to_delete[0].teilenummer, "9508580"
        )

    def test_selection_condition_syntax_error(self):
        ref_object_ids = [each.cdb_object_id for each in self.maxbom.Components]
        selection_condition = SelectionCondition.KeywordQuery(
            ref_object_id=ref_object_ids
        )
        selection_condition.Update(expression="abc == 'Syntax Error")

        with self.assertRaises(SelectionConditionEvaluationError) as assert_raises:
            instantiate_part(self.var2, self.maxbom)

        self.assertIn(assert_raises.exception.ref_object_id, ref_object_ids)


class TestAttributeUpdates(testcase.RollbackTestCase):
    def setUp(self):
        super().setUp()
        self.options = InstantiateOptions.ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM
        InstantiateOptions.ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM = [
            "menge",
            "occurence_id",
            "variant_id",
            "stlbemerkung",
            "netto_durchm",
            "netto_hoehe",
            "netto_laenge",
            "netto_breite",
            "position_el",
            "auftr_z_index",
            "cadsource",
            "ce_valid_to",
            "ce_valid_from",
            "st_fertart",
            "ap_fertart",
            "ap_bemerkung",
            "pos_x",
            "pos_y",
            "pos_z",
            "strukturzaehler",
            "mbom_mapping_tag",
        ]
        self.occ_options = (
            InstantiateOptions.ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM_OCCURRENCE
        )

    def tearDown(self):
        super().tearDown()
        InstantiateOptions.ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM = self.options
        InstantiateOptions.ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM_OCCURRENCE = (
            self.occ_options
        )

    def test_get_bom_item_attributes(self):
        bom_item = AssemblyComponent.ByKeys(
            cdb_object_id="8d9746a1-8ca5-11eb-b944-98fa9bf98f6d"
        )
        self.assertIsNotNone(bom_item)

        expected_result = {
            "occurence_id": bom_item.occurence_id,
            "variant_id": bom_item.variant_id,
            "stlbemerkung": bom_item.stlbemerkung,
            "netto_durchm": bom_item.netto_durchm,
            "netto_hoehe": bom_item.netto_hoehe,
            "netto_laenge": bom_item.netto_laenge,
            "netto_breite": bom_item.netto_breite,
            "position_el": bom_item.position_el,
            "auftr_z_index": bom_item.auftr_z_index,
            "cadsource": bom_item.cadsource,
            "ce_valid_to": bom_item.ce_valid_to,
            "ce_valid_from": bom_item.ce_valid_from,
            "st_fertart": bom_item.st_fertart,
            "ap_fertart": bom_item.ap_fertart,
            "ap_bemerkung": bom_item.ap_bemerkung,
            "pos_x": bom_item.pos_x,
            "pos_y": bom_item.pos_y,
            "pos_z": bom_item.pos_z,
            "strukturzaehler": bom_item.strukturzaehler,
            "mbom_mapping_tag": bom_item.mbom_mapping_tag,
        }

        result = InstantiateOptions.get_bom_item_attributes_to_update(bom_item)
        self.assertDictEqual(result, expected_result)

    def test_get_bom_item_attributes_no_blacklisted_keys(self):
        InstantiateOptions.ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM = list(
            VariantBomNode.bom_item_keys
        )
        InstantiateOptions.ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM.extend(
            ["menge", "netto_laenge"]
        )
        bom_item = AssemblyComponent.ByKeys(
            cdb_object_id="8d9746a1-8ca5-11eb-b944-98fa9bf98f6d"
        )
        expected_result = {
            "netto_laenge": bom_item.netto_laenge,
        }
        result = InstantiateOptions.get_bom_item_attributes_to_update(bom_item)
        self.assertDictEqual(result, expected_result)

    def test_get_occurrence_attributes(self):
        InstantiateOptions.ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM_OCCURRENCE = [
            "reference_path",
            "occurrence_variant_id",
            "relative_transformation",
        ]
        occ = AssemblyComponentOccurrence.ByKeys(
            cdb_object_id="40783ebb-a1dd-11eb-b94b-98fa9bf98f6d"
        )
        self.assertIsNotNone(occ)
        expected_result = {
            "reference_path": occ.reference_path,
            "occurrence_variant_id": occ.occurrence_variant_id,
            "relative_transformation": occ.relative_transformation,
        }

        result = InstantiateOptions.get_bom_item_occurrences_attributes_to_update(occ)
        self.assertDictEqual(result, expected_result)

    def test_get_occurrence_attributes_blacklisted_filtered(self):
        InstantiateOptions.ATTRIBUTES_TO_UPDATE_FOR_BOM_ITEM_OCCURRENCE = list(
            VariantBomNode.occurrence_keys
        )
        occ = AssemblyComponentOccurrence.ByKeys(
            cdb_object_id="40783ebb-a1dd-11eb-b94b-98fa9bf98f6d"
        )
        self.assertIsNotNone(occ)
        expected_result = {}

        result = InstantiateOptions.get_bom_item_occurrences_attributes_to_update(occ)
        self.assertDictEqual(result, expected_result)

    def test_make_occ_only_specific_keys(self):
        occ = AssemblyComponentOccurrence.ByKeys(
            cdb_object_id="40783ebb-a1dd-11eb-b94b-98fa9bf98f6d"
        )
        self.assertIsNotNone(occ)
        expected_result = occ.occurrence_id + "#" + occ.assembly_path

        result = _make_bom_item_occurrence_only_specific_keys(occ)

        self.assertEqual(result, expected_result)
