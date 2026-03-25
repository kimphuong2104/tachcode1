import datetime
from typing import Optional

from cdb.sqlapi import Record
from cdb.testcase import RollbackTestCase

from cs.vp.bom.enhancement import FlatBomRestEnhancement
from cs.vp.bom.enhancement.plugin import AbstractPlugin
from cs.vp.bom.bomqueries_plugins import EffectivityDatesPlugin
from cs.vp.bom.enhancement.register import BomTableScope
from cs.vp.bom.tests import (
    generateAssemblyComponent,
    generateAssemblyComponentOccurrence,
)
from cs.vp.bom.web.bommanager.internal import BommanagerInternalModel
from cs.vp.items.tests import generateItem
from cs.vp.variants.filter import (
    CsVpVariantsProductContextPlugin,
    CsVpVariantsAttributePlugin, CsVpVariantsFilterPlugin, CsVpVariantsFilterContextPlugin,
)
from cs.vp.variants.tests import (
    generateProductWithEnumValues,
    generateVariantForProduct,
)


def get_bom_enhancement():
    return FlatBomRestEnhancement(BomTableScope.LOAD)


def create_bommanager_internal_model(*args, **kwargs):
    model = BommanagerInternalModel(*args, **kwargs)
    model.bom_enhancement = get_bom_enhancement()
    return model


class TestInternal(RollbackTestCase):
    def test_effectivity_bom_filter(self):
        def get_date(filter_data, key, pos):
            if filter_data[key][pos]:
                return datetime.datetime.strptime(filter_data[key][pos], "%Y-%m-%d")
            return None

        def filter_bom_info(filter_data, mode):
            if mode in ["part", "both"]:
                key = "p_data" if "p_data" in filter_data else "data__"
                child_1.getPersistentObject().Update(
                    ce_valid_from=get_date(filter_data, key, 0),
                    ce_valid_to=get_date(filter_data, key, 1),
                )
            else:
                child_1.getPersistentObject().Update(
                    ce_valid_from=None, ce_valid_to=None
                )
            if mode in ["bom", "both"]:
                key = "b_data" if "b_data" in filter_data else "data__"
                bom_item_child_1.getPersistentObject().Update(
                    ce_valid_from=get_date(filter_data, key, 0),
                    ce_valid_to=get_date(filter_data, key, 1),
                )
            else:
                bom_item_child_1.getPersistentObject().Update(
                    ce_valid_from=None, ce_valid_to=None
                )

            model.bom_enhancement = get_bom_enhancement()

            valid_from = get_date(filter_data, "filter", 0)
            valid_to = get_date(filter_data, "filter", 1)

            if valid_from is None and valid_to is None:
                with self.assertRaises(ValueError):
                    EffectivityDatesPlugin(
                        valid_from=valid_from,
                        valid_to=valid_to
                    )
            else:
                plugin_effectivity_dates = (
                    EffectivityDatesPlugin(
                        valid_from=valid_from,
                        valid_to=valid_to
                    )
                )

                model.bom_enhancement.add(plugin_effectivity_dates)
            return model.bom_info([bom])[0]

        bom = generateItem(benennung="bom")
        child_1 = generateItem(benennung="child_1")
        bom_item_child_1 = generateAssemblyComponent(bom, child_1, position=10)
        model = create_bommanager_internal_model(bom.cdb_object_id)

        test_data = [
            {
                "description": "search without validity dates - no validity dates set for",
                "filter": ["", ""],
                "data__": ["", ""],
                "expected": 1,
            },
            {
                "description": "search without validity dates - valid from date set for",
                "filter": ["", ""],
                "data__": ["2018-06-01", ""],
                "expected": 1,
            },
            {
                "description": "search without validity dates - valid to date set for",
                "filter": ["", ""],
                "data__": ["", "2018-06-01"],
                "expected": 1,
            },
            {
                "description": "search without validity dates - valid from and to date set for",
                "filter": ["", ""],
                "data__": ["2018-06-01", "2019-06-01"],
                "expected": 1,
            },
            {
                "description": "search 'valid from' - no validity dates set for",
                "filter": ["2018-06-01", ""],
                "data__": ["", ""],
                "expected": 1,
            },
            {
                "description": "search 'valid to' - no validity dates set for",
                "filter": ["", "2018-06-01"],
                "data__": ["", ""],
                "expected": 1,
            },
            {
                "description": "search 'valid from-to' - no validity dates set for",
                "filter": ["2018-06-01", "2019-06-01"],
                "data__": ["", ""],
                "expected": 1,
            },
            {
                "description": "search 'valid from' for too early date - only valid_from set for",
                "filter": ["2018-06-01", ""],
                "data__": ["2019-01-01", ""],
                "expected": 0,
                "expected_part": 1,
            },
            {
                "description": "search 'valid from' for exact date - only valid_from set for",
                "filter": ["2019-01-01", ""],
                "data__": ["2019-01-01", ""],
                "expected": 1,
            },
            {
                "description": "search 'valid from' for later date - only valid_from set for",
                "filter": ["2019-04-01", ""],
                "data__": ["2019-01-01", ""],
                "expected": 1,
            },
            {
                "description": "search 'valid to' for too early date - only valid_from set for",
                "filter": ["", "2018-06-01"],
                "data__": ["2019-01-01", ""],
                "expected": 0,
                "expected_part": 1,
            },
            {
                "description": "search 'valid to' for exact date - only valid_from set for",
                "filter": ["", "2019-01-01"],
                "data__": ["2019-01-01", ""],
                "expected": 1,
            },
            {
                "description": "search 'valid to' for later date - only valid_from set for",
                "filter": ["", "2019-04-01"],
                "data__": ["2019-01-01", ""],
                "expected": 1,
            },
            {
                "description": "search 'valid from-to' for too early date - only valid_from set for",
                "filter": ["2018-06-01", "2018-12-31"],
                "data__": ["2019-01-01", ""],
                "expected": 0,
                "expected_part": 1,
            },
            {
                "description": "search 'valid from-to' for exact date - only valid_from set for",
                "filter": ["2019-01-01", "2019-12-31"],
                "data__": ["2019-01-01", ""],
                "expected": 1,
            },
            {
                "description": "search 'valid from-to' for later date - only valid_from set for",
                "filter": ["2019-06-01", "2019-12-31"],
                "data__": ["2019-01-01", ""],
                "expected": 1,
            },
            {
                "description": "search 'valid from-to' for too late date - only valid_to set for",
                "filter": ["2019-06-01", "2019-12-31"],
                "data__": ["", "2018-01-01"],
                "expected": 0,
                "expected_part": 1,
            },
            {
                "description": "search 'valid from-to' for exact date - only valid_to set for",
                "filter": ["2019-06-01", "2019-12-31"],
                "data__": ["", "2019-12-31"],
                "expected": 1,
            },
            {
                "description": "search 'valid from-to' for earlier date - only valid_to set for",
                "filter": ["2019-01-01", "2019-06-01"],
                "data__": ["", "2019-12-31"],
                "expected": 1,
            },
            {
                "description": "search 'valid from-to' only part valid",
                "filter": ["2019-01-01", "2019-06-01"],
                "b_data": ["2020-01-01", "2020-06-01"],
                "p_data": ["2018-01-01", "2021-01-01"],
                "expected": 0,
            },
            {
                "description": "search 'valid from-to' only bom item valid",
                "filter": ["2019-01-01", "2019-06-01"],
                "b_data": ["2018-01-01", "2021-01-01"],
                "p_data": ["2020-01-01", "2020-06-01"],
                "expected": 0,
                "expected_part": 1,
            },
        ]

        for data in test_data:
            if "data__" in data:
                for mode in ["part", "bom", "both"]:
                    flat_bom = filter_bom_info(data, mode)
                    expected = data["expected"]
                    if "expected_part" in data and "part" == mode:
                        expected = data["expected_part"]
                    self.assertEqual(
                        expected,
                        len(flat_bom),
                        "{} {}".format(data.get("description", ""), mode),
                    )
            else:
                expected = (
                    data["expected_part"]
                    if "expected_part" in data
                    else data["expected"]
                )
                self.assertEqual(
                    expected,
                    len(filter_bom_info(data, "both")),
                    "{} {}".format(data.get("description", ""), "both"),
                )

    def test_effectivity_filter_same_part_different_positions(self):
        bom = generateItem(benennung="bom")
        child_1 = generateItem(benennung="child_1")
        generateAssemblyComponent(
            bom,
            child_1,
            position=10,
            ce_valid_from=datetime.datetime.strptime("2021-08-02", "%Y-%m-%d"),
            ce_valid_to=datetime.datetime.strptime("2021-08-16", "%Y-%m-%d"),
        )
        generateAssemblyComponent(
            bom,
            child_1,
            position=20,
            ce_valid_from=datetime.datetime.strptime("2021-08-17", "%Y-%m-%d"),
            ce_valid_to=datetime.datetime.strptime("2021-08-23", "%Y-%m-%d"),
        )

        model = create_bommanager_internal_model(bom.cdb_object_id)

        model.bom_enhancement = get_bom_enhancement()
        model.bom_enhancement.add(
            EffectivityDatesPlugin(
                valid_from=datetime.datetime.strptime("2021-08-16", "%Y-%m-%d")
            )
        )
        children = model.bom_info([bom])[0]
        self.assertEqual(1, len(children))
        for child in children:
            self.assertEqual(10, child["position"])

        model.bom_enhancement = get_bom_enhancement()
        model.bom_enhancement.add(
            EffectivityDatesPlugin(
                valid_from=datetime.datetime.strptime("2021-08-17", "%Y-%m-%d")
            )
        )
        children = model.bom_info([bom])[0]
        self.assertEqual(1, len(children))
        for child in children:
            self.assertEqual(20, child["position"])

    def test_bom_filter_get_bom_item_select_stmt_extension(self):
        bom = generateItem(benennung="bom")
        child_1 = generateItem(benennung="child_1")
        generateAssemblyComponent(
            bom,
            item=child_1,
            position=123,
        )
        child_1_1 = generateItem(benennung="child_1_1")
        generateAssemblyComponent(
            child_1,
            item=child_1_1,
            position=456,
        )

        model = create_bommanager_internal_model(bom.cdb_object_id)
        bom_info_result = model.bom_info([bom, child_1])
        self.assertEqual(2, len(bom_info_result))

        for children in bom_info_result:
            self.assertEqual(1, len(children))
            child = children[0]
            expected_is_leaf = 1 if child["position"] == 456 else 0
            self.assertEqual(expected_is_leaf, child["is_leaf"])

    def test_bom_filter_get_sql_join_stmt_extension(self):
        class TestBomEnhancementPlugin(AbstractPlugin):
            def get_bom_item_select_stmt_extension(self) -> Optional[str]:
                return ", o.occurrence_id as oc_occurrence_id"

            def get_sql_join_stmt_extension(self) -> Optional[str]:
                return """
                LEFT JOIN bom_item_occurrence o
                    ON o.bompos_object_id={0}.cdb_object_id
                        """.format(
                    self.BOM_ITEM_TABLE_ALIAS
                )

        bom = generateItem(benennung="bom")
        child_1 = generateItem(benennung="child_1")
        child_1_bom_item = generateAssemblyComponent(
            bom, item=child_1, position=123, menge=2
        )
        generateAssemblyComponentOccurrence(child_1_bom_item, occurrence_id="oc_1")
        generateAssemblyComponentOccurrence(child_1_bom_item, occurrence_id="oc_2")
        self.assertEqual(2, len(child_1_bom_item.Occurrences))

        model = create_bommanager_internal_model(bom.cdb_object_id)
        model.bom_enhancement.add(TestBomEnhancementPlugin())
        bom_info_result = model.bom_info([bom])
        self.assertEqual(1, len(bom_info_result))

        children = bom_info_result[0]
        self.assertEqual(2, len(children))

        expected_in = {"oc_1", "oc_2"}

        for child in children:
            self.assertIn(child["oc_occurrence_id"], expected_in)

    def test_bom_filter_get_additional_bom_item_attributes(self):
        expected_key = "to_test_key"
        expected_value = "to_test_value"

        class TestBomEnhancementPlugin(AbstractPlugin):
            def get_additional_bom_item_attributes(
                    self, bom_item_record: Record
            ) -> Optional[dict]:
                return {expected_key: expected_value}

        bom = generateItem(benennung="bom")
        child_1 = generateItem(benennung="child_1")
        generateAssemblyComponent(bom, item=child_1, position=123, menge=2)

        model = create_bommanager_internal_model(bom.cdb_object_id)
        model.bom_enhancement.add(TestBomEnhancementPlugin())
        bom_info_result = model.bom_info([bom])
        self.assertEqual(1, len(bom_info_result))

        children = bom_info_result[0]
        self.assertEqual(1, len(children))

        child = children[0]

        self.assertEqual(expected_value, child[expected_key])

    def test_cs_vp_variants_attribute_extension_for_variant(self):
        bom = generateItem(benennung="bom")
        child_1 = generateItem(benennung="child_1")
        generateAssemblyComponent(bom, item=child_1, position=123, menge=2)

        product = generateProductWithEnumValues()
        variant = generateVariantForProduct(product)

        model = create_bommanager_internal_model(bom.cdb_object_id)
        context_plugin = CsVpVariantsProductContextPlugin(variant["product_object_id"])
        filter_context = CsVpVariantsFilterContextPlugin(context_plugin, variant["cdb_object_id"])
        attr_plugin = CsVpVariantsAttributePlugin(filter_context)

        model.bom_enhancement.add(attr_plugin)

        bom_info_result = model.bom_info([bom])
        self.assertEqual(1, len(bom_info_result))

        children = bom_info_result[0]
        self.assertEqual(1, len(children))

        child = children[0]

        self.assertFalse(False, child["in_variant"])

    def test_find_in_lbom(self):
        ebom = generateItem(benennung="ebom")
        child_1 = generateItem(benennung="child_1")
        child_1_1 = generateItem(benennung="child_1_1")
        child_2 = generateItem(benennung="child_2")
        bom_item_1 = generateAssemblyComponent(ebom, child_1, position=10)
        bom_item_1_1 = generateAssemblyComponent(child_1, child_1_1, position=10)
        bom_item_2_1 = generateAssemblyComponent(ebom, child_2, position=20)
        bom_item_2_2 = generateAssemblyComponent(ebom, child_2, position=21)

        not_in_ebom = generateItem(benennung="not_in_ebom")

        model = create_bommanager_internal_model(ebom.cdb_object_id)

        # Expect to find one occurrence on first level.
        lbom_paths = model.find_in_lbom(child_1.teilenummer, child_1.t_index)
        # Ensure number of paths is as expected.
        self.assertEqual(1, len(lbom_paths))
        # Ensure path has correct length.
        self.assertEqual(1, len(lbom_paths[0]))
        # Ensure path references correct BOM item.
        self.assertEqual(bom_item_1.cdb_object_id, lbom_paths[0][0]['cdb_object_id'])

        # Expect to find one occurrence on second level.
        lbom_paths = model.find_in_lbom(child_1_1.teilenummer, child_1_1.t_index)
        # Ensure number of paths is as expected.
        self.assertEqual(1, len(lbom_paths))
        # Ensure path has correct length.
        self.assertEqual(2, len(lbom_paths[0]))
        # Ensure paths reference correct BOM items.
        self.assertEqual(bom_item_1.cdb_object_id, lbom_paths[0][0]['cdb_object_id'])
        self.assertEqual(bom_item_1_1.cdb_object_id, lbom_paths[0][1]['cdb_object_id'])

        # Expect to find two occurrences on first level.
        lbom_paths = model.find_in_lbom(child_2.teilenummer, child_2.t_index)
        # Ensure number of paths is as expected.
        self.assertEqual(2, len(lbom_paths))
        # Ensure paths reference correct BOM items.
        self.assertEqual(bom_item_2_1.cdb_object_id, lbom_paths[0][0]['cdb_object_id'])
        self.assertEqual(bom_item_2_2.cdb_object_id, lbom_paths[1][0]['cdb_object_id'])

        # Expect to find no occurrence.
        lbom_paths = model.find_in_lbom(not_in_ebom.teilenummer, not_in_ebom.t_index)
        self.assertEqual(0, len(lbom_paths))
