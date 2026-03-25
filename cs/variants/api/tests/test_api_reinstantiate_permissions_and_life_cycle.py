#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from cdb import validationkit
from cs.variants import api
from cs.variants.api import helpers
from cs.variants.api.tests.base_test_case import BaseTestCase
from cs.variants.exceptions import (
    MultiplePartsReinstantiateWithFailedPartsError,
    NotAllowedToReinstantiateError,
)
from cs.vp.items import Item


class TestApiReinstantiatePermissionAndLifeCycle(BaseTestCase):
    def tearDown(self):
        super().tearDown()
        helpers.REUSE_ENABLED = self.reuse_neabled

    def setUp(self):
        super().setUp()
        self.reuse_neabled = helpers.REUSE_ENABLED
        helpers.REUSE_ENABLED = False
        self.t9508643_teilenummer = "9508643"
        self.t9508645_teilenummer = "9508645"
        self.t9508647_teilenummer = "9508647"

        self.t9508643 = Item.ByKeys(teilenummer=self.t9508643_teilenummer, t_index="")
        self.t9508645 = Item.ByKeys(teilenummer=self.t9508645_teilenummer, t_index="")
        self.t9508647 = Item.ByKeys(teilenummer=self.t9508647_teilenummer, t_index="")

    def pre_check(self):
        self.assertEqual(self.t9508643.status, 0)  # draft
        self.assertEqual(self.t9508645.status, 100)  # review
        self.assertEqual(self.t9508647.status, 200)  # released

        t9508643_all = Item.KeywordQuery(teilenummer=self.t9508643_teilenummer)
        self.assertEqual(len(t9508643_all), 1)
        t9508645_all = Item.KeywordQuery(teilenummer=self.t9508645_teilenummer)
        self.assertEqual(len(t9508645_all), 1)

        t9508647_all = Item.KeywordQuery(teilenummer=self.t9508647_teilenummer)
        self.assertEqual(len(t9508647_all), 1)

    @validationkit.run_with_roles(["public", "Engineering"])
    def test_reinstantiate_review(self):
        with self.assertRaises(NotAllowedToReinstantiateError):
            api.reinstantiate_parts([self.t9508645])

    @validationkit.run_with_roles(["public", "Engineering"])
    def test_reinstantiate_released(self):
        num_parts_pre = len(Item.Query().Execute())
        api.reinstantiate_parts([self.t9508647])

        indexed = Item.ByKeys(teilenummer=self.t9508647_teilenummer, t_index="a")
        self.assertIsNotNone(indexed)
        num_parts_post = len(Item.Query().Execute())
        self.assertEqual(num_parts_pre + 2, num_parts_post)

        indexed = Item.ByKeys(teilenummer=self.t9508647_teilenummer, t_index="a")
        self.assertIsNotNone(indexed)

    @validationkit.run_with_roles(["public", "Engineering"])
    def test_reinstantiate_draft(self):
        num_parts_pre = len(Item.Query().Execute())

        api.reinstantiate_parts([self.t9508643])

        num_parts_post = len(Item.Query().Execute())
        self.assertEqual(num_parts_pre, num_parts_post)

        indexed = Item.ByKeys(teilenummer=self.t9508643_teilenummer, t_index="a")
        self.assertIsNone(indexed)

    @validationkit.run_with_roles(["public", "Engineering"])
    def test_reinstantiate_mixed_selection_no_error(self):
        num_parts_pre = len(Item.Query().Execute())

        api.reinstantiate_parts([self.t9508643, self.t9508647])

        num_parts_post = len(Item.Query().Execute())
        self.assertEqual(num_parts_post, num_parts_pre + 2)

        indexed = Item.ByKeys(teilenummer=self.t9508647_teilenummer, t_index="a")
        self.assertIsNotNone(indexed)

        indexed = Item.ByKeys(teilenummer=self.t9508643_teilenummer, t_index="a")
        self.assertIsNone(indexed)

    @validationkit.run_with_roles(["public", "Engineering"])
    def test_reinstantiate_mixed_selection_with_error(self):
        num_parts_pre = len(Item.Query().Execute())
        with self.assertRaises(
            MultiplePartsReinstantiateWithFailedPartsError
        ) as assert_raises:
            api.reinstantiate_parts([self.t9508643, self.t9508645, self.t9508647])

        self.assertIn("1", str(assert_raises.exception))
        self.assertIn("3", str(assert_raises.exception))
        self.assertIn(self.t9508645.GetDescription(), str(assert_raises.exception))

        num_parts_post = len(Item.Query().Execute())
        self.assertEqual(num_parts_post, num_parts_pre + 2)

        indexed = Item.ByKeys(teilenummer=self.t9508647_teilenummer, t_index="a")
        self.assertIsNotNone(indexed)

        indexed = Item.ByKeys(teilenummer=self.t9508643_teilenummer, t_index="a")
        self.assertIsNone(indexed)
