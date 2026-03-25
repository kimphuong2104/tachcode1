# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from functools import partial
from typing import Optional, Any, Callable

import pytest

from cdb.sqlapi import Record
from cdb.testcase import RollbackTestCase

from cs.vp.bom import bomqueries
from cs.vp.bom.enhancement import FlatBomEnhancement
from cs.vp.bom.enhancement import EnhancementPluginError
from cs.vp.bom.enhancement.plugin import AbstractPlugin
from cs.vp.bom.tests import (
    generateAssemblyComponent,
    generateAssemblyComponentOccurrence,
)
from cs.vp.items.tests import generateItem
from cs.vp.bom import Item


class TestEnhancement(RollbackTestCase):
    def test_bom_extension_get_bom_item_select_stmt_extension(self):
        class TestBomEnhancementPlugin(AbstractPlugin):
            def get_bom_item_select_stmt_extension(self) -> Optional[str]:
                return """, CASE
                    WHEN NOT EXISTS (
                        SELECT * FROM einzelteile et
                        WHERE et.baugruppe={0}.teilenummer
                            AND et.b_index={0}.t_index
                    ) THEN 1
                    ELSE 0
                END is_leaf""".format(
                    self.BOM_ITEM_TABLE_ALIAS
                )

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

        bom_enhancement = FlatBomEnhancement()
        bom_enhancement.add(TestBomEnhancementPlugin())
        children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement)
        self.assertEqual(2, len(children))

        for child in children:
            expected_is_leaf = 1 if child["position"] == 456 else 0
            self.assertEqual(expected_is_leaf, getattr(child, "is_leaf"))
            self.assertEqual(expected_is_leaf, child["is_leaf"])
            self.assertEqual(expected_is_leaf, child.is_leaf)

    def test_bom_extension_get_sql_join_stmt_extension(self):
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

        bom_enhancement = FlatBomEnhancement()
        bom_enhancement.add(TestBomEnhancementPlugin())
        children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement)
        self.assertEqual(2, len(children))

        expected_in = {"oc_1", "oc_2"}

        for child in children:
            self.assertIn(getattr(child, "oc_occurrence_id"), expected_in)
            self.assertIn(child["oc_occurrence_id"], expected_in)
            self.assertIn(child.oc_occurrence_id, expected_in)

    def test_bom_extension_get_additional_bom_item_attributes(self):
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

        bom_enhancement = FlatBomEnhancement()
        bom_enhancement.add(TestBomEnhancementPlugin())
        children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement)
        self.assertEqual(1, len(children))

        child = children[0]

        with self.assertRaises(AttributeError):
            self.assertNotEqual(expected_value, child[expected_key])

        additional_bom_item_attributes = (
            bom_enhancement.get_additional_bom_item_attributes(child)
        )
        self.assertDictEqual(
            additional_bom_item_attributes, {expected_key: expected_value}
        )


def test_multiple_plugin_registration() -> None:
    """registration the same plugin twice raises Error"""
    enhancement = FlatBomEnhancement()

    class FakePlugin(AbstractPlugin):
        pass

    enhancement.add(FakePlugin())

    with pytest.raises(ValueError) as ex:
        enhancement.add(FakePlugin())

    assert "FakePlugin already created" in ex.value.args[0]


class FakeExceptionPlugin(AbstractPlugin):
    """used to test if the correct error is raised

    Note:
        Should be containing *all* (overridable) methods
    """

    def get_sql_join_stmt_extension(self) -> Optional[str]:
        raise AttributeError("This is an attribute error")

    def get_part_where_stmt_extension(self) -> Optional[str]:
        raise AttributeError("This is an attribute error")

    def get_bom_item_select_stmt_extension(self) -> Optional[str]:
        raise AttributeError("This is an attribute error")

    def get_bom_item_where_stmt_extension(self) -> Optional[str]:
        raise AttributeError("This is an attribute error")

    def get_additional_bom_item_attributes(self, bom_item_record: Record) -> Optional[dict[Any, Any]]:
        raise AttributeError("This is an attribute error")

    def filter_bom_item_records(self, bom_item_records: list[Record]) -> list[Record]:
        raise AttributeError("This is an attribute error")

    def resolve_bom_item_children(self, bom_item_record: Record) -> bool:
        raise AttributeError("This is an attribute error")


def test_plugin_raises_exception_used_in_flat_bom() -> None:
    """
    simple test if plugin raises an exception

    we expect to get the original exception from the plugin
    """
    enhancement = FlatBomEnhancement()
    enhancement.add(FakeExceptionPlugin())

    bom = Item.ByKeys(teilenummer="9502657", t_index="")
    assert bom is not None
    with pytest.raises(EnhancementPluginError) as ex:
        bomqueries.flat_bom(bom, bom_enhancement=enhancement)

    assert "This is an attribute error" in str(ex.value)


def test_plugin_raises_enhancement_error() -> None:
    """if plugin raise error an enhancement error should be raised"""

    enhancement = FlatBomEnhancement()
    enhancement.add(FakeExceptionPlugin())

    test_map: dict[str, Callable] = {
        "get_sql_join_stmt_extension": enhancement.get_sql_join_stmt_extension,
        "get_part_where_stmt_extension": enhancement.get_part_where_stmt_extension,
        "get_bom_item_select_stmt_extension": enhancement.get_bom_item_select_stmt_extension,
        "get_bom_item_where_stmt_extension": enhancement.get_bom_item_where_stmt_extension,
        "get_additional_bom_item_attributes": partial(enhancement.get_additional_bom_item_attributes, None),
        "filter_bom_item_records": partial(enhancement.filter_bom_item_records,[]),
        "resolve_bom_item_children": partial(enhancement.resolve_bom_item_children, None)
    }

    for each_key, each_item in test_map.items():
        with pytest.raises(EnhancementPluginError) as ex:
            each_item()

        # check original exception msg present
        assert "This is an attribute error" in str(ex.value)
        # check funcname present
        assert each_key in str(ex.value)


def test_enhancement_resolve_bom_item_children() -> None:
    class BooleanPlugin(AbstractPlugin):

        def __init__(self, true_or_false: bool) -> None:
            super().__init__()
            self.true_or_false = true_or_false

        def resolve_bom_item_children(self, bom_item_record: Record) -> bool:
            return self.true_or_false

    class Boolean2Plugin(BooleanPlugin):
        pass

    enhancement = FlatBomEnhancement()

    # all Plugins return True
    enhancement.add(BooleanPlugin(True))
    enhancement.add(Boolean2Plugin(True))

    assert enhancement.resolve_bom_item_children(None)

    enhancement = FlatBomEnhancement()
    # all Plugins return False
    enhancement.add(BooleanPlugin(False))
    enhancement.add(Boolean2Plugin(False))

    assert not enhancement.resolve_bom_item_children(None)

    enhancement = FlatBomEnhancement()
    # one Plugin return False
    enhancement.add(BooleanPlugin(True))
    enhancement.add(Boolean2Plugin(False))

    assert not enhancement.resolve_bom_item_children(None)
