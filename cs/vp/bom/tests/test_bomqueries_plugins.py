# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import datetime
from dateutil.relativedelta import relativedelta
from dataclasses import dataclass
from unittest.mock import patch, MagicMock

import pytest

from cdb import constants, sqlapi
from cdb.objects import operations
from cdb.testcase import RollbackTestCase
from cdb.util import SkipAccessCheck

from cs.vp.bom import bomqueries
from cs.vp.bom.bomqueries_plugins import (
    EffectivityDatesPlugin,
    ComponentJoinPlugin,
    SiteBomAttributePlugin,
    Site2BomAttributePlugin,
    SiteBomAdditionalAttrFilterPlugin,
    SiteBomPurposeLoadPlugin,
    SiteBomPurposeSyncPlugin,
    SiteBomPurposeLoadDiffTablePlugin,
    SiteBomPurposeFindDifferencePlugin,
)
from cs.vp.bom.enhancement import EnhancementPluginError, FlatBomEnhancement
from cs.vp.bom.tests import generateAssemblyComponent
from cs.vp.items.tests import generateItem
from cs.vp.bom.web.bommanager.utils import SiteFilterPurpose


class TestBomQueriesPlugins(RollbackTestCase):
    def test_effectivity_filter(self):
        def get_date(filter_data, key, pos):
            if filter_data[key][pos]:
                return datetime.datetime.strptime(filter_data[key][pos], "%Y-%m-%d")
            return None

        def filter_flat_bom(filter_data, mode):
            if mode in ["part", "both"]:
                key = "p_data" if "p_data" in filter_data else "data__"
                for obj in [child_1, child_1_1]:
                    obj.getPersistentObject().Update(
                        ce_valid_from=get_date(filter_data, key, 0),
                        ce_valid_to=get_date(filter_data, key, 1),
                    )
            else:
                child_1.getPersistentObject().Update(
                    ce_valid_from=None, ce_valid_to=None
                )
            if mode in ["bom", "both"]:
                key = "b_data" if "b_data" in filter_data else "data__"
                for obj in [bom_item_child_1, bom_item_child_1_1]:
                    obj.getPersistentObject().Update(
                        ce_valid_from=get_date(filter_data, key, 0),
                        ce_valid_to=get_date(filter_data, key, 1),
                    )
            else:
                for obj in [bom_item_child_1, bom_item_child_1_1]:
                    obj.getPersistentObject().Update(
                        ce_valid_from=None, ce_valid_to=None
                    )

            bom_enhancement = FlatBomEnhancement()

            valid_from = get_date(filter_data, "filter", 0)
            valid_to = get_date(filter_data, "filter", 1)

            if valid_from is None and valid_to is None:
                with self.assertRaises(ValueError):
                    EffectivityDatesPlugin(
                        valid_from=valid_from,
                        valid_to=valid_to
                    )
            else:
                plugin_effectivity_dates = EffectivityDatesPlugin(
                    valid_from=valid_from,
                    valid_to=valid_to
                )

                bom_enhancement.add(plugin_effectivity_dates)
            return bomqueries.flat_bom_dict(bom, bom_enhancement=bom_enhancement)

        bom = generateItem(benennung="bom")
        child_1 = generateItem(benennung="child_1")
        bom_item_child_1 = generateAssemblyComponent(bom, child_1, position=10)
        child_1_1 = generateItem(benennung="child_1_1")
        bom_item_child_1_1 = generateAssemblyComponent(child_1, child_1_1, position=10)

        test_data = [
            {
                "description": "search without validity dates - no validity dates set for",
                "filter": ["", ""],
                "data__": ["", ""],
                "expected": 2,
            },
            {
                "description": "search without validity dates - valid from date set for",
                "filter": ["", ""],
                "data__": ["2018-06-01", ""],
                "expected": 2,
            },
            {
                "description": "search without validity dates - valid to date set for",
                "filter": ["", ""],
                "data__": ["", "2018-06-01"],
                "expected": 2,
            },
            {
                "description": "search without validity dates - valid from and to date set for",
                "filter": ["", ""],
                "data__": ["2018-06-01", "2019-06-01"],
                "expected": 2,
            },
            {
                "description": "search 'valid from' - no validity dates set for",
                "filter": ["2018-06-01", ""],
                "data__": ["", ""],
                "expected": 2,
            },
            {
                "description": "search 'valid to' - no validity dates set for",
                "filter": ["", "2018-06-01"],
                "data__": ["", ""],
                "expected": 2,
            },
            {
                "description": "search 'valid from-to' - no validity dates set for",
                "filter": ["2018-06-01", "2019-06-01"],
                "data__": ["", ""],
                "expected": 2,
            },
            {
                "description": "search 'valid from' for too early date - only valid_from set for",
                "filter": ["2018-06-01", ""],
                "data__": ["2019-01-01", ""],
                "expected": 0,
                "expected_part": 2,
            },
            {
                "description": "search 'valid from' for exact date - only valid_from set for",
                "filter": ["2019-01-01", ""],
                "data__": ["2019-01-01", ""],
                "expected": 2,
            },
            {
                "description": "search 'valid from' for later date - only valid_from set for",
                "filter": ["2019-04-01", ""],
                "data__": ["2019-01-01", ""],
                "expected": 2,
            },
            {
                "description": "search 'valid to' for too early date - only valid_from set for",
                "filter": ["", "2018-06-01"],
                "data__": ["2019-01-01", ""],
                "expected": 0,
                "expected_part": 2,
            },
            {
                "description": "search 'valid to' for exact date - only valid_from set for",
                "filter": ["", "2019-01-01"],
                "data__": ["2019-01-01", ""],
                "expected": 2,
            },
            {
                "description": "search 'valid to' for later date - only valid_from set for",
                "filter": ["", "2019-04-01"],
                "data__": ["2019-01-01", ""],
                "expected": 2,
                "expected_part": 2,
            },
            {
                "description": "search 'valid from-to' for too early date - only valid_from set for",
                "filter": ["2018-06-01", "2018-12-31"],
                "data__": ["2019-01-01", ""],
                "expected": 0,
                "expected_part": 2,
            },
            {
                "description": "search 'valid from-to' for exact date - only valid_from set for",
                "filter": ["2019-01-01", "2019-12-31"],
                "data__": ["2019-01-01", ""],
                "expected": 2,
            },
            {
                "description": "search 'valid from-to' for later date - only valid_from set for",
                "filter": ["2019-06-01", "2019-12-31"],
                "data__": ["2019-01-01", ""],
                "expected": 2,
            },
            {
                "description": "search 'valid from-to' for too late date - only valid_to set for",
                "filter": ["2019-06-01", "2019-12-31"],
                "data__": ["", "2018-01-01"],
                "expected": 0,
                "expected_part": 2,
            },
            {
                "description": "search 'valid from-to' for exact date - only valid_to set for",
                "filter": ["2019-06-01", "2019-12-31"],
                "data__": ["", "2019-12-31"],
                "expected": 2,
            },
            {
                "description": "search 'valid from-to' for earlier date - only valid_to set for",
                "filter": ["2019-01-01", "2019-06-01"],
                "data__": ["", "2019-12-31"],
                "expected": 2,
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
                "expected_part": 2,
            },
        ]

        for data in test_data:
            if "data__" in data:
                for mode in ["part", "bom", "both"]:
                    flat_bom = filter_flat_bom(data, mode)
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
                    len(filter_flat_bom(data, "both")),
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

        bom_enhancement = FlatBomEnhancement()
        bom_enhancement.add(
            EffectivityDatesPlugin(
                valid_from=datetime.datetime.strptime("2021-08-16", "%Y-%m-%d")
            )
        )
        children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement)
        self.assertEqual(1, len(children))
        for child in children:
            self.assertEqual(10, child["position"])

        bom_enhancement = FlatBomEnhancement()
        bom_enhancement.add(
            EffectivityDatesPlugin(
                valid_from=datetime.datetime.strptime("2021-08-17", "%Y-%m-%d")
            )
        )
        children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement)
        self.assertEqual(1, len(children))
        for child in children:
            self.assertEqual(20, child["position"])


    @classmethod
    def _create_part(cls, is_imprecise, benennung="part", assembly=None):
        part = generateItem(benennung=benennung)
        if assembly:
            generateAssemblyComponent(assembly, item=part, is_imprecise=is_imprecise)
        return part

    @classmethod
    def _create_draft_part(cls, is_imprecise, benennung="draft_part", assembly=None):
        return cls._create_part(is_imprecise, benennung=benennung, assembly=assembly)

    @classmethod
    def _create_released_part(cls, is_imprecise, benennung="released_part", assembly=None):
        part = cls._create_part(is_imprecise, benennung=benennung, assembly=assembly)
        cls._release_part(part)
        return part

    @classmethod
    def _create_revision_part(cls, is_imprecise, benennung="revision_part", assembly=None):
        part = cls._create_released_part(is_imprecise, benennung=benennung, assembly=assembly)
        part_index = operations.operation(constants.kOperationIndex, part)
        return part, part_index

    @classmethod
    def _create_obsolete_part(cls, is_imprecise, benennung="obsolete_part", assembly=None):
        part, part_index = cls._create_revision_part(is_imprecise, benennung=benennung, assembly=assembly)
        cls._release_part(part_index, part)
        return part, part_index

    @classmethod
    def _create_blocked_part(cls, is_imprecise, benennung="blocked_part", assembly=None):
        part, part_index = cls._create_revision_part(is_imprecise, benennung=benennung, assembly=assembly)
        cls._release_part(part_index, part)
        part_index.ChangeState(180)
        part_index.ce_valid_to = part_index.ce_valid_from + relativedelta(years=1)
        return part, part_index

    @classmethod
    def _release_part(cls, part, prev_index=None):
        part.ChangeState(100)
        part.ChangeState(200)
        if prev_index:
            part.ce_valid_from = prev_index.ce_valid_from + relativedelta(years=1)
            prev_index.ce_valid_to = part.ce_valid_from
            part.Reload()
            prev_index.Reload()
        else:
            part.ce_valid_from = datetime.date(2000, 12, 31)
            part.Reload()

    def _test_bom_item_records(self, bom_enhancement, bom_items, expected_bom_items):
        bom_item_ids = [bom_item.cdb_object_id for bom_item in bom_items]
        children = bomqueries.bom_item_records(*bom_item_ids, bom_enhancement=bom_enhancement)
        self.assertEqual(len(expected_bom_items), len(bom_items))
        for child in children:
            self.assertIn(
                (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_bom_items
            )

    def test_imprecise_bom_extension_component_join(self):

        with SkipAccessCheck():
            bom = generateItem(benennung="bom")
            child_draft = TestBomQueriesPlugins._create_draft_part(is_imprecise=1, assembly=bom)
            child_released = TestBomQueriesPlugins._create_released_part(is_imprecise=1, assembly=bom)
            child_revision, child_revision_index = TestBomQueriesPlugins._create_revision_part(
                is_imprecise=1, assembly=bom
            )
            child_obsolete, child_obsolete_index = TestBomQueriesPlugins._create_obsolete_part(
                is_imprecise=1, assembly=bom
            )
            child_blocked, child_blocked_index = TestBomQueriesPlugins._create_blocked_part(
                is_imprecise=1, assembly=bom
            )

            bom_enhancement = FlatBomEnhancement()
            bom_enhancement.add(ComponentJoinPlugin("unsupported view"))
            with pytest.raises(EnhancementPluginError) as ex:
                bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement)
            self.assertIn('view type \'unsupported view\' not supported', str(ex))

            bom_enhancement = FlatBomEnhancement()
            bom_enhancement.add(ComponentJoinPlugin("as_saved"))
            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement)
            expected_children = set([
                (bom.teilenummer, bom.t_index, child_draft.teilenummer, child_draft.t_index),
                (bom.teilenummer, bom.t_index, child_released.teilenummer, child_released.t_index),
                (bom.teilenummer, bom.t_index, child_revision.teilenummer, child_revision.t_index),
                (bom.teilenummer, bom.t_index, child_obsolete.teilenummer, child_obsolete.t_index),
                (bom.teilenummer, bom.t_index, child_blocked.teilenummer, child_blocked.t_index)
            ])
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )
            self._test_bom_item_records(bom_enhancement, children, expected_children)

            bom_enhancement = FlatBomEnhancement()
            bom_enhancement.add(ComponentJoinPlugin("latest_working"))
            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement)
            expected_children = set([
                (bom.teilenummer, bom.t_index, child_draft.teilenummer, child_draft.t_index),
                (bom.teilenummer, bom.t_index, child_released.teilenummer, child_released.t_index),
                (bom.teilenummer, bom.t_index, child_revision.teilenummer, child_revision_index.t_index),
                (bom.teilenummer, bom.t_index, child_obsolete.teilenummer, child_obsolete_index.t_index),
                (bom.teilenummer, bom.t_index, child_blocked.teilenummer, child_blocked_index.t_index)
            ])
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )
            self._test_bom_item_records(bom_enhancement, children, expected_children)

            bom_enhancement = FlatBomEnhancement()
            bom_enhancement.add(ComponentJoinPlugin("released_at"))
            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement)
            expected_children = set([
                (bom.teilenummer, bom.t_index, child_draft.teilenummer, child_draft.t_index),
                (bom.teilenummer, bom.t_index, child_released.teilenummer, child_released.t_index),
                (bom.teilenummer, bom.t_index, child_revision.teilenummer, child_revision.t_index),
                (bom.teilenummer, bom.t_index, child_obsolete.teilenummer, child_obsolete_index.t_index),
                (bom.teilenummer, bom.t_index, child_blocked.teilenummer, child_blocked_index.t_index)
            ])
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )
            self._test_bom_item_records(bom_enhancement, children, expected_children)

            bom_enhancement = FlatBomEnhancement()
            bom_enhancement.add(ComponentJoinPlugin("released_at", datetime.date(2000, 12, 31)))
            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement)
            expected_children = set([
                (bom.teilenummer, bom.t_index, child_draft.teilenummer, child_draft.t_index),
                (bom.teilenummer, bom.t_index, child_released.teilenummer, child_released.t_index),
                (bom.teilenummer, bom.t_index, child_revision.teilenummer, child_revision.t_index),
                (bom.teilenummer, bom.t_index, child_obsolete.teilenummer, child_obsolete.t_index),
                (bom.teilenummer, bom.t_index, child_blocked.teilenummer, child_blocked.t_index)
            ])
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )
            self._test_bom_item_records(bom_enhancement, children, expected_children)

    def test_imprecise_bom_extension_component_join_with_levels(self):
        # pylint: disable=too-many-locals, too-many-statements

        with SkipAccessCheck():
            bom = generateItem(benennung="bom")

            child_draft = TestBomQueriesPlugins._create_draft_part(is_imprecise=1, assembly=bom)
            child_draft_part = TestBomQueriesPlugins._create_draft_part(is_imprecise=1, assembly=child_draft)

            child_released = TestBomQueriesPlugins._create_released_part(is_imprecise=1, assembly=bom)
            child_released_part = TestBomQueriesPlugins._create_released_part(
                is_imprecise=1, assembly=child_released
            )

            child_revision, child_revision_index = TestBomQueriesPlugins._create_revision_part(
                is_imprecise=1, assembly=bom
            )
            child_revision_part, _ = TestBomQueriesPlugins._create_revision_part(
                is_imprecise=1, assembly=child_revision
            )
            _, child_revision_index_part_index = \
                TestBomQueriesPlugins._create_revision_part(is_imprecise=1, assembly=child_revision_index)

            child_obsolete, child_obsolete_index = TestBomQueriesPlugins._create_obsolete_part(
                is_imprecise=1, assembly=bom
            )
            child_obsolete_part, _ = TestBomQueriesPlugins._create_obsolete_part(
                is_imprecise=1, assembly=child_obsolete
            )
            _, child_obsolete_index_part_index = \
                TestBomQueriesPlugins._create_obsolete_part(is_imprecise=1, assembly=child_obsolete_index)

            child_blocked, child_blocked_index = TestBomQueriesPlugins._create_blocked_part(
                is_imprecise=1, assembly=bom
            )
            child_blocked_part, _ = TestBomQueriesPlugins._create_blocked_part(
                is_imprecise=1, assembly=child_blocked
            )
            _, child_blocked_index_part_index = \
                TestBomQueriesPlugins._create_blocked_part(is_imprecise=1, assembly=child_blocked_index)

            bom_enhancement = FlatBomEnhancement()
            bom_enhancement.add(ComponentJoinPlugin("as_saved"))
            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement, levels=1)
            expected_children = set([
                (bom.teilenummer, bom.t_index, child_draft.teilenummer, child_draft.t_index),
                (bom.teilenummer, bom.t_index, child_released.teilenummer, child_released.t_index),
                (bom.teilenummer, bom.t_index, child_revision.teilenummer, child_revision.t_index),
                (bom.teilenummer, bom.t_index, child_obsolete.teilenummer, child_obsolete.t_index),
                (bom.teilenummer, bom.t_index, child_blocked.teilenummer, child_blocked.t_index)
            ])
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )
            self._test_bom_item_records(bom_enhancement, children, expected_children)

            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement, levels=-1)
            expected_children.add((
                child_draft.teilenummer, child_draft.t_index,
                child_draft_part.teilenummer, child_draft_part.t_index
            ))
            expected_children.add((
                child_released.teilenummer, child_released.t_index,
                child_released_part.teilenummer, child_released_part.t_index
            ))
            expected_children.add((
                child_revision.teilenummer, child_revision.t_index,
                child_revision_part.teilenummer, child_revision_part.t_index
            ))
            expected_children.add((
                child_obsolete.teilenummer, child_obsolete.t_index,
                child_obsolete_part.teilenummer, child_obsolete_part.t_index
            ))
            expected_children.add((
                child_blocked.teilenummer, child_blocked.t_index,
                child_blocked_part.teilenummer, child_blocked_part.t_index
            ))
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )

            bom_enhancement = FlatBomEnhancement()
            bom_enhancement.add(ComponentJoinPlugin("latest_working"))
            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement, levels=1)
            expected_children = set([
                (bom.teilenummer, bom.t_index, child_draft.teilenummer, child_draft.t_index),
                (bom.teilenummer, bom.t_index, child_released.teilenummer, child_released.t_index),
                (bom.teilenummer, bom.t_index, child_revision.teilenummer, child_revision_index.t_index),
                (bom.teilenummer, bom.t_index, child_obsolete.teilenummer, child_obsolete_index.t_index),
                (bom.teilenummer, bom.t_index, child_blocked.teilenummer, child_blocked_index.t_index)
            ])
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )
            self._test_bom_item_records(bom_enhancement, children, expected_children)

            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement, levels=-1)
            expected_children.add((
                child_draft.teilenummer, child_draft.t_index,
                child_draft_part.teilenummer, child_draft_part.t_index
            ))
            expected_children.add((
                child_released.teilenummer, child_released.t_index,
                child_released_part.teilenummer, child_released_part.t_index
            ))
            expected_children.add((
                child_revision_index.teilenummer, child_revision_index.t_index,
                child_revision_index_part_index.teilenummer, child_revision_index_part_index.t_index
            ))
            expected_children.add((
                child_obsolete_index.teilenummer, child_obsolete_index.t_index,
                child_obsolete_index_part_index.teilenummer, child_obsolete_index_part_index.t_index
            ))
            expected_children.add((
                child_blocked_index.teilenummer, child_blocked_index.t_index,
                child_blocked_index_part_index.teilenummer, child_blocked_index_part_index.t_index
            ))
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )
            self._test_bom_item_records(bom_enhancement, children, expected_children)

            bom_enhancement = FlatBomEnhancement()
            bom_enhancement.add(ComponentJoinPlugin("released_at"))
            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement, levels=1)
            expected_children = set([
                (bom.teilenummer, bom.t_index, child_draft.teilenummer, child_draft.t_index),
                (bom.teilenummer, bom.t_index, child_released.teilenummer, child_released.t_index),
                (bom.teilenummer, bom.t_index, child_revision.teilenummer, child_revision.t_index),
                (bom.teilenummer, bom.t_index, child_obsolete.teilenummer, child_obsolete_index.t_index),
                (bom.teilenummer, bom.t_index, child_blocked.teilenummer, child_blocked_index.t_index)
            ])
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )
            self._test_bom_item_records(bom_enhancement, children, expected_children)

            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement, levels=-1)
            expected_children.add((
                child_draft.teilenummer, child_draft.t_index,
                child_draft_part.teilenummer, child_draft_part.t_index
            ))
            expected_children.add((
                child_released.teilenummer, child_released.t_index,
                child_released_part.teilenummer, child_released_part.t_index
            ))
            expected_children.add((
                child_revision.teilenummer, child_revision.t_index,
                child_revision_part.teilenummer, child_revision_part.t_index
            ))
            expected_children.add((
                child_obsolete_index.teilenummer, child_obsolete_index.t_index,
                child_obsolete_index_part_index.teilenummer, child_obsolete_index_part_index.t_index
            ))
            expected_children.add((
                child_blocked_index.teilenummer, child_blocked_index.t_index,
                child_blocked_index_part_index.teilenummer, child_blocked_index_part_index.t_index
            ))
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )
            self._test_bom_item_records(bom_enhancement, children, expected_children)

            bom_enhancement = FlatBomEnhancement()
            bom_enhancement.add(ComponentJoinPlugin("latest_released"))
            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement, levels=1)
            expected_children = set([
                (bom.teilenummer, bom.t_index, child_draft.teilenummer, child_draft.t_index),
                (bom.teilenummer, bom.t_index, child_released.teilenummer, child_released.t_index),
                (bom.teilenummer, bom.t_index, child_revision.teilenummer, child_revision.t_index),
                (bom.teilenummer, bom.t_index, child_obsolete.teilenummer, child_obsolete_index.t_index),
                (bom.teilenummer, bom.t_index, child_blocked.teilenummer, child_blocked_index.t_index)
            ])
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )
            self._test_bom_item_records(bom_enhancement, children, expected_children)

            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement, levels=-1)
            expected_children.add((
                child_draft.teilenummer, child_draft.t_index,
                child_draft_part.teilenummer, child_draft_part.t_index
            ))
            expected_children.add((
                child_released.teilenummer, child_released.t_index,
                child_released_part.teilenummer, child_released_part.t_index
            ))
            expected_children.add((
                child_revision.teilenummer, child_revision.t_index,
                child_revision_part.teilenummer, child_revision_part.t_index
            ))
            expected_children.add((
                child_obsolete_index.teilenummer, child_obsolete_index.t_index,
                child_obsolete_index_part_index.teilenummer, child_obsolete_index_part_index.t_index
            ))
            expected_children.add((
                child_blocked_index.teilenummer, child_blocked_index.t_index,
                child_blocked_index_part_index.teilenummer, child_blocked_index_part_index.t_index
            ))
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )
            self._test_bom_item_records(bom_enhancement, children, expected_children)

            bom_enhancement = FlatBomEnhancement()
            bom_enhancement.add(ComponentJoinPlugin("latest_released", datetime.date(2000, 12, 31)))
            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement, levels=1)
            expected_children = set([
                (bom.teilenummer, bom.t_index, child_draft.teilenummer, child_draft.t_index),
                (bom.teilenummer, bom.t_index, child_released.teilenummer, child_released.t_index),
                (bom.teilenummer, bom.t_index, child_revision.teilenummer, child_revision.t_index),
                (bom.teilenummer, bom.t_index, child_obsolete_index.teilenummer, child_obsolete_index.t_index),
                (bom.teilenummer, bom.t_index, child_blocked_index.teilenummer, child_blocked_index.t_index)
            ])
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )

            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement, levels=-1)
            expected_children.add((
                child_draft.teilenummer, child_draft.t_index,
                child_draft_part.teilenummer, child_draft_part.t_index
            ))
            expected_children.add((
                child_released.teilenummer, child_released.t_index,
                child_released_part.teilenummer, child_released_part.t_index
            ))
            expected_children.add((
                child_revision.teilenummer, child_revision.t_index,
                child_revision_part.teilenummer, child_revision_part.t_index
            ))
            expected_children.add((
                child_obsolete_index.teilenummer, child_obsolete_index.t_index,
                child_obsolete_index_part_index.teilenummer, child_obsolete_index_part_index.t_index
            ))
            expected_children.add((
                child_blocked_index.teilenummer, child_blocked_index.t_index,
                child_blocked_index_part_index.teilenummer, child_blocked_index_part_index.t_index
            ))
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )
            self._test_bom_item_records(bom_enhancement, children, expected_children)

            bom_enhancement = FlatBomEnhancement()
            bom_enhancement.add(ComponentJoinPlugin("released_at", datetime.date(2000, 12, 31)))
            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement, levels=1)
            expected_children = set([
                (bom.teilenummer, bom.t_index, child_draft.teilenummer, child_draft.t_index),
                (bom.teilenummer, bom.t_index, child_released.teilenummer, child_released.t_index),
                (bom.teilenummer, bom.t_index, child_revision.teilenummer, child_revision.t_index),
                (bom.teilenummer, bom.t_index, child_obsolete.teilenummer, child_obsolete.t_index),
                (bom.teilenummer, bom.t_index, child_blocked.teilenummer, child_blocked.t_index)
            ])
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )
            self._test_bom_item_records(bom_enhancement, children, expected_children)

            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement, levels=-1)
            expected_children.add((
                child_draft.teilenummer, child_draft.t_index,
                child_draft_part.teilenummer, child_draft_part.t_index
            ))
            expected_children.add((
                child_released.teilenummer, child_released.t_index,
                child_released_part.teilenummer, child_released_part.t_index
            ))
            expected_children.add((
                child_revision.teilenummer, child_revision.t_index,
                child_revision_part.teilenummer, child_revision_part.t_index
            ))
            expected_children.add((
                child_obsolete.teilenummer, child_obsolete.t_index,
                child_obsolete_part.teilenummer, child_obsolete_part.t_index
            ))
            expected_children.add((
                child_blocked.teilenummer, child_blocked.t_index,
                child_blocked_part.teilenummer, child_blocked_part.t_index
            ))
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )
            self._test_bom_item_records(bom_enhancement, children, expected_children)

    def test_mixed_bom_extension_component_join_with_levels(self):

        with SkipAccessCheck():
            bom = generateItem(benennung="bom")

            imprecise_assembly = TestBomQueriesPlugins._create_draft_part(is_imprecise=1, assembly=bom)
            imprecise_child_draft = TestBomQueriesPlugins._create_draft_part(
                is_imprecise=1, assembly=imprecise_assembly
            )
            imprecise_child_released = TestBomQueriesPlugins._create_released_part(
                is_imprecise=1, assembly=imprecise_assembly
            )
            imprecise_child_revision, imprecise_child_revision_index = TestBomQueriesPlugins._create_revision_part(
                is_imprecise=1, assembly=imprecise_assembly
            )
            imprecise_child_obsolete, imprecise_child_obsolete_index = TestBomQueriesPlugins._create_obsolete_part(
                is_imprecise=1, assembly=imprecise_assembly
            )

            precise_assembly = TestBomQueriesPlugins._create_draft_part(is_imprecise=1, assembly=bom)
            precise_child_draft = TestBomQueriesPlugins._create_draft_part(
                is_imprecise=0, assembly=precise_assembly
            )
            precise_child_released = TestBomQueriesPlugins._create_released_part(
                is_imprecise=0, assembly=precise_assembly
            )
            precise_child_revision, _ = TestBomQueriesPlugins._create_revision_part(
                is_imprecise=0, assembly=precise_assembly
            )
            precise_child_obsolete, _ = TestBomQueriesPlugins._create_obsolete_part(
                is_imprecise=0, assembly=precise_assembly
            )

            bom_enhancement = FlatBomEnhancement()
            bom_enhancement.add(ComponentJoinPlugin("as_saved"))
            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement)
            expected_children = set([
                (
                    bom.teilenummer, bom.t_index,
                    imprecise_assembly.teilenummer, imprecise_assembly.t_index
                ),
                (
                    imprecise_assembly.teilenummer, imprecise_assembly.t_index,
                    imprecise_child_draft.teilenummer, imprecise_child_draft.t_index
                ),
                (
                    imprecise_assembly.teilenummer, imprecise_assembly.t_index,
                    imprecise_child_released.teilenummer, imprecise_child_released.t_index
                ),
                (
                    imprecise_assembly.teilenummer, imprecise_assembly.t_index,
                    imprecise_child_revision.teilenummer, imprecise_child_revision.t_index
                ),
                (
                    imprecise_assembly.teilenummer, imprecise_assembly.t_index,
                    imprecise_child_obsolete.teilenummer, imprecise_child_obsolete.t_index
                ),
                (
                    bom.teilenummer, bom.t_index,
                    precise_assembly.teilenummer, precise_assembly.t_index
                ),
                (
                    precise_assembly.teilenummer, precise_assembly.t_index,
                    precise_child_draft.teilenummer, precise_child_draft.t_index
                ),
                (
                    precise_assembly.teilenummer, precise_assembly.t_index,
                    precise_child_released.teilenummer, precise_child_released.t_index
                ),
                (
                    precise_assembly.teilenummer, precise_assembly.t_index,
                    precise_child_revision.teilenummer, precise_child_revision.t_index
                ),
                (
                    precise_assembly.teilenummer, precise_assembly.t_index,
                    precise_child_obsolete.teilenummer, precise_child_obsolete.t_index
                )
            ])
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )

            bom_enhancement = FlatBomEnhancement()
            bom_enhancement.add(ComponentJoinPlugin("latest_working"))
            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement)
            expected_children = set([
                (
                    bom.teilenummer, bom.t_index,
                    imprecise_assembly.teilenummer, imprecise_assembly.t_index
                ),
                (
                    imprecise_assembly.teilenummer, imprecise_assembly.t_index,
                    imprecise_child_draft.teilenummer, imprecise_child_draft.t_index
                ),
                (
                    imprecise_assembly.teilenummer, imprecise_assembly.t_index,
                    imprecise_child_released.teilenummer, imprecise_child_released.t_index
                ),
                (
                    imprecise_assembly.teilenummer, imprecise_assembly.t_index,
                    imprecise_child_revision_index.teilenummer, imprecise_child_revision_index.t_index
                ),
                (
                    imprecise_assembly.teilenummer, imprecise_assembly.t_index,
                    imprecise_child_obsolete_index.teilenummer, imprecise_child_obsolete_index.t_index
                ),
                (
                    bom.teilenummer, bom.t_index,
                    precise_assembly.teilenummer, precise_assembly.t_index
                ),
                (
                    precise_assembly.teilenummer, precise_assembly.t_index,
                    precise_child_draft.teilenummer, precise_child_draft.t_index
                ),
                (
                    precise_assembly.teilenummer, precise_assembly.t_index,
                    precise_child_released.teilenummer, precise_child_released.t_index
                ),
                (
                    precise_assembly.teilenummer, precise_assembly.t_index,
                    precise_child_revision.teilenummer, precise_child_revision.t_index
                ),
                (
                    precise_assembly.teilenummer, precise_assembly.t_index,
                    precise_child_obsolete.teilenummer, precise_child_obsolete.t_index
                )
            ])
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )

            bom_enhancement = FlatBomEnhancement()
            bom_enhancement.add(ComponentJoinPlugin("released_at"))
            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement)
            expected_children = set([
                (
                    bom.teilenummer, bom.t_index,
                    imprecise_assembly.teilenummer, imprecise_assembly.t_index
                ),
                (
                    imprecise_assembly.teilenummer, imprecise_assembly.t_index,
                    imprecise_child_draft.teilenummer, imprecise_child_draft.t_index
                ),
                (
                    imprecise_assembly.teilenummer, imprecise_assembly.t_index,
                    imprecise_child_released.teilenummer, imprecise_child_released.t_index
                ),
                (
                    imprecise_assembly.teilenummer, imprecise_assembly.t_index,
                    imprecise_child_revision.teilenummer, imprecise_child_revision.t_index
                ),
                (
                    imprecise_assembly.teilenummer, imprecise_assembly.t_index,
                    imprecise_child_obsolete_index.teilenummer, imprecise_child_obsolete_index.t_index
                ),
                (
                    bom.teilenummer, bom.t_index,
                    precise_assembly.teilenummer, precise_assembly.t_index
                ),
                (
                    precise_assembly.teilenummer, precise_assembly.t_index,
                    precise_child_draft.teilenummer, precise_child_draft.t_index
                ),
                (
                    precise_assembly.teilenummer, precise_assembly.t_index,
                    precise_child_released.teilenummer, precise_child_released.t_index
                ),
                (
                    precise_assembly.teilenummer, precise_assembly.t_index,
                    precise_child_revision.teilenummer, precise_child_revision.t_index
                ),
                (
                    precise_assembly.teilenummer, precise_assembly.t_index,
                    precise_child_obsolete.teilenummer, precise_child_obsolete.t_index
                )
            ])
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )

            bom_enhancement = FlatBomEnhancement()
            bom_enhancement.add(ComponentJoinPlugin("latest_released"))
            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement)
            expected_children = set([
                (
                    bom.teilenummer, bom.t_index,
                    imprecise_assembly.teilenummer, imprecise_assembly.t_index
                ),
                (
                    imprecise_assembly.teilenummer, imprecise_assembly.t_index,
                    imprecise_child_draft.teilenummer, imprecise_child_draft.t_index
                ),
                (
                    imprecise_assembly.teilenummer, imprecise_assembly.t_index,
                    imprecise_child_released.teilenummer, imprecise_child_released.t_index
                ),
                (
                    imprecise_assembly.teilenummer, imprecise_assembly.t_index,
                    imprecise_child_revision.teilenummer, imprecise_child_revision.t_index
                ),
                (
                    imprecise_assembly.teilenummer, imprecise_assembly.t_index,
                    imprecise_child_obsolete_index.teilenummer, imprecise_child_obsolete_index.t_index
                ),
                (
                    bom.teilenummer, bom.t_index,
                    precise_assembly.teilenummer, precise_assembly.t_index
                ),
                (
                    precise_assembly.teilenummer, precise_assembly.t_index,
                    precise_child_draft.teilenummer, precise_child_draft.t_index
                ),
                (
                    precise_assembly.teilenummer, precise_assembly.t_index,
                    precise_child_released.teilenummer, precise_child_released.t_index
                ),
                (
                    precise_assembly.teilenummer, precise_assembly.t_index,
                    precise_child_revision.teilenummer, precise_child_revision.t_index
                ),
                (
                    precise_assembly.teilenummer, precise_assembly.t_index,
                    precise_child_obsolete.teilenummer, precise_child_obsolete.t_index
                )
            ])
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )

    def test_component_join_plugins(self):
        with SkipAccessCheck():
            bom = generateItem(benennung="bom")
            child_revision, child_revision_index = TestBomQueriesPlugins._create_revision_part(
                is_imprecise=1, assembly=bom
            )
            children = bomqueries.flat_bom(bom)
            expected_children = set([
                (
                    bom.teilenummer, bom.t_index,
                    child_revision.teilenummer, child_revision.t_index
                )
            ])
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )

            bom_enhancement = FlatBomEnhancement()
            bom_enhancement.add(ComponentJoinPlugin("latest_working"))
            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement)
            expected_children = set([
                (
                    bom.teilenummer, bom.t_index,
                    child_revision_index.teilenummer, child_revision_index.t_index
                )
            ])
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )

    def test_component_join_without_valid_dates(self):
        with SkipAccessCheck():
            bom = generateItem(benennung="bom")
            child_obsolete, child_obsolete_index = TestBomQueriesPlugins._create_obsolete_part(
                is_imprecise=1,
                assembly=bom
            )
            sqlapi.SQLupdate(
                f"teile_stamm SET ce_valid_from=NULL, ce_valid_to=NULL where teilenummer='{child_obsolete.teilenummer}'"
            )
            bom_enhancement = FlatBomEnhancement()
            bom_enhancement.add(ComponentJoinPlugin("as_saved"))
            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement)
            expected_children = set([
                (
                    bom.teilenummer, bom.t_index,
                    child_obsolete.teilenummer, child_obsolete.t_index
                )
            ])
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )

            bom_enhancement = FlatBomEnhancement()
            bom_enhancement.add(ComponentJoinPlugin("latest_released"))
            children = bomqueries.flat_bom(bom, bom_enhancement=bom_enhancement)
            expected_children = set([
                (
                    bom.teilenummer, bom.t_index,
                    child_obsolete_index.teilenummer, None
                )
            ])
            self.assertEqual(len(expected_children), len(children))
            for child in children:
                self.assertIn(
                    (child.baugruppe, child.b_index, child.teilenummer, child.t_index), expected_children
                )


def test_site_bom_attribute_plugin_metadata() -> None:
    assert SiteBomAttributePlugin.DISCRIMINATOR == "cs.vp.siteBomAttributePlugin"
    assert SiteBomAttributePlugin.DEPENDENCIES == tuple()


def test_site_bom_attribute_plugin_init() -> None:
    obj = SiteBomAttributePlugin("dummy")
    assert obj.site_object_id == "dummy"

    with pytest.raises(ValueError) as ex:
        SiteBomAttributePlugin(None)

    assert str(ex.value) == "site_object_id is needed"


def test_site_bom_attribute_plugin_create_default() -> None:
    # wrong or no instance_name - no plugin
    obj = SiteBomAttributePlugin.create_for_default_data({})
    assert obj is None

    obj = SiteBomAttributePlugin.create_for_default_data({}, instance_name="left")
    assert obj is None

    # parameter site is missing in url
    obj = SiteBomAttributePlugin.create_for_default_data(
        {}, instance_name="bommanager_right", bom_table_url="http://blub.de?s=1"
    )
    assert obj is None

    # correct call
    obj = SiteBomAttributePlugin.create_for_default_data(
        {}, instance_name="bommanager_right", bom_table_url="http://blub.de?site=1"
    )
    assert obj is not None
    assert obj.site_object_id == "1"


@patch("cs.vp.bom.bomqueries_plugins.Organization.ByKeys")
def test_site_bom_attribute_plugin_get_default(organization_mock: MagicMock) -> None:
    # return None if no site_object_id
    obj = SiteBomAttributePlugin("dummy")
    obj.site_object_id = None  # reset do None

    data = obj.get_default_data()
    assert data is None

    # return None if no organization exists
    organization_mock.return_value = None
    obj = SiteBomAttributePlugin("dummy")

    data = obj.get_default_data()
    assert data is None
    assert organization_mock.called
    organization_mock.assert_called_with(cdb_object_id="dummy")

    # now with organization exists
    class OrganizationFake:
        def GetDescription(self) -> str:
            return "the description"

    organization_mock.return_value = OrganizationFake()
    obj = SiteBomAttributePlugin("dummy")
    data = obj.get_default_data()

    assert data == ({"cdb_object_id": "dummy", "system:description": "the description"}, None)


def test_site_bom_attribute_plugin_create_rest() -> None:
    # no rest data - no plugin
    obj = SiteBomAttributePlugin.create_from_rest_data(None, {})
    assert obj is None

    # extract the cdb_object_id from rest data
    obj = SiteBomAttributePlugin.create_from_rest_data({"cdb_object_id": "dummy"}, {})
    assert obj is not None
    assert obj.site_object_id == "dummy"

    # no cdb_object_id in rest data - no plugin
    obj = SiteBomAttributePlugin.create_from_rest_data({"cdb_object_id": None}, {})
    assert obj is None


def test_site2_bom_attribute_plugin_metadata() -> None:
    assert Site2BomAttributePlugin.DISCRIMINATOR == "cs.vp.site2BomAttributePlugin"
    assert Site2BomAttributePlugin.DEPENDENCIES == tuple()


def test_site2_bom_attribute_plugin_create_default() -> None:
    # wrong or no instance_name - no plugin
    obj = Site2BomAttributePlugin.create_for_default_data({})
    assert obj is None

    obj = Site2BomAttributePlugin.create_for_default_data({}, instance_name="left")
    assert obj is None

    # site parameter must be ignored
    obj = Site2BomAttributePlugin.create_for_default_data(
        {}, instance_name="bommanager_right", bom_table_url="http://blub.de?site=1"
    )
    assert obj is None

    # correct call
    obj = Site2BomAttributePlugin.create_for_default_data(
        {}, instance_name="bommanager_right", bom_table_url="http://blub.de?site2=1"
    )
    assert obj is not None
    assert obj.site_object_id == "1"


def test_site_bom_attribute_filter_plugin_metadata() -> None:
    assert (
            SiteBomAdditionalAttrFilterPlugin.DISCRIMINATOR == "cs.vp.siteBomFilterPlugin"
    )
    assert SiteBomAdditionalAttrFilterPlugin.DEPENDENCIES == (
        SiteBomAttributePlugin,
        Site2BomAttributePlugin,
    )


def test_site_bom_attribute_filter_plugin_init() -> None:
    obj = SiteBomAdditionalAttrFilterPlugin("s1", "s2")

    assert obj.site_plugin == "s1"
    assert obj.site2_plugin == "s2"


def test_site_bom_attribute_filter_plugin_from_rest() -> None:
    dependencies = {SiteBomAttributePlugin: "site1", Site2BomAttributePlugin: "site2"}
    obj = SiteBomAdditionalAttrFilterPlugin.create_from_rest_data(None, dependencies)

    assert obj.site_plugin == "site1"
    assert obj.site2_plugin == "site2"


@patch(
    "cs.vp.bom.web.bommanager.utils.StandardSiteFilter.get_other_site_transparency_behavior"
)
def test_site_bom_attribute_filter_plugin_additional_attr(
        transparent_behaviour_mock: MagicMock,
) -> None:
    transparent_behaviour_mock.return_value = "behaviour"

    class FakeRecord:
        _from_other_site = "the_other_side"

    obj = SiteBomAdditionalAttrFilterPlugin()

    result = obj.get_additional_bom_item_attributes(FakeRecord())

    assert result == {
        "from_other_site": "the_other_side",
        "site_transparency_behavior": "behaviour",
    }


def test_site_bom_purpose_load_plugin_metadata() -> None:
    assert SiteBomPurposeLoadPlugin.DISCRIMINATOR == "cs.vp.siteBomPurposePlugin"
    assert SiteBomPurposeLoadPlugin.DEPENDENCIES == (
        SiteBomAttributePlugin,
        Site2BomAttributePlugin,
    )


def test_site_bom_purpose_load_plugin_init() -> None:
    obj = SiteBomPurposeLoadPlugin("p1", "p2")

    assert obj.site_plugin == "p1"
    assert obj.site2_plugin == "p2"


def test_site_bom_purpose_load_plugin_from_rest() -> None:
    dependencies = {SiteBomAttributePlugin: "site1", Site2BomAttributePlugin: "site2"}
    obj = SiteBomPurposeLoadPlugin.create_from_rest_data(None, dependencies)

    assert obj.site_plugin == "site1"
    assert obj.site2_plugin == "site2"


def test_site_bom_purpose_load_plugin_get_selected_sites() -> None:
    @dataclass
    class FakeSitePlugin:
        site_object_id: str = ""

    obj = SiteBomPurposeLoadPlugin()
    assert obj.get_selected_sites() == []

    fake_p1 = FakeSitePlugin("f1")
    fake_p2 = FakeSitePlugin("f2")

    obj = SiteBomPurposeLoadPlugin(site_plugin=fake_p1)
    assert obj.get_selected_sites() == ["f1"]

    obj = SiteBomPurposeLoadPlugin(site2_plugin=fake_p2)
    assert obj.get_selected_sites() == ["f2"]

    obj = SiteBomPurposeLoadPlugin(site_plugin=fake_p1, site2_plugin=fake_p2)
    assert obj.get_selected_sites() == ["f1", "f2"]


@patch("cs.vp.bom.bomqueries_plugins.site_bom_filter")
def test_site_bom_purpose_load_plugin_filter_records(
        site_filter_mock: MagicMock,
) -> None:
    records = ["record1", "record2"]
    obj = SiteBomPurposeLoadPlugin()
    obj.filter_bom_item_records(records)

    assert site_filter_mock.called
    site_filter_mock.assert_called_with(
        records, selected_sites=[], purpose=SiteFilterPurpose.LOAD_TREE_DATA
    )


@patch(
    "cs.vp.bom.web.bommanager.utils.StandardSiteFilter.get_other_site_transparency_behavior"
)
def test_site_bom_purpose_load_plugin_additional_attr(
        transparent_behaviour_mock: MagicMock,
) -> None:
    transparent_behaviour_mock.return_value = "behaviour"

    class FakeRecord:
        _from_other_site = "the_other_side"

    obj = SiteBomPurposeLoadPlugin()

    result = obj.get_additional_bom_item_attributes(FakeRecord())

    assert result == {
        "from_other_site": "the_other_side",
        "site_transparency_behavior": "behaviour",
    }


@patch("cs.vp.bom.bomqueries_plugins.site_bom_filter")
def test_site_bom_purpose_sync_plugin_filter_records(
        site_filter_mock: MagicMock,
) -> None:
    records = ["record1", "record2"]
    obj = SiteBomPurposeSyncPlugin()
    obj.filter_bom_item_records(records)

    assert site_filter_mock.called
    site_filter_mock.assert_called_with(
        records, selected_sites=[], purpose=SiteFilterPurpose.SYNC_VIEW
    )


@patch("cs.vp.bom.bomqueries_plugins.site_bom_filter")
def test_site_bom_purpose_find_plugin_filter_records(
        site_filter_mock: MagicMock,
) -> None:
    records = ["record1", "record2"]
    obj = SiteBomPurposeFindDifferencePlugin()
    obj.filter_bom_item_records(records)

    assert site_filter_mock.called
    site_filter_mock.assert_called_with(
        records, selected_sites=[], purpose=SiteFilterPurpose.FIND_DIFFERENCE
    )


@patch("cs.vp.bom.bomqueries_plugins.site_bom_filter")
def test_site_bom_purpose_diff_plugin_filter_records(
        site_filter_mock: MagicMock,
) -> None:
    records = ["record1", "record2"]
    obj = SiteBomPurposeLoadDiffTablePlugin()
    obj.filter_bom_item_records(records)

    assert site_filter_mock.called
    site_filter_mock.assert_called_with(
        records, selected_sites=[], purpose=SiteFilterPurpose.LOAD_DIFF_TABLE_DATA
    )
