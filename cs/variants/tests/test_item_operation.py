#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
import cs
from cdb import ue, validationkit
from cs.variants.api.tests.base_test_case import BaseTestCase
from cs.vp.items import Item


class MockContext:
    def __init__(self):
        self.data = {}

    def set(self, key, value):
        self.data[key] = value


class TestItemOperation(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.t9508643_teilenummer = "9508643"
        self.t9508645_teilenummer = "9508645"

        self.t9508643 = Item.ByKeys(teilenummer=self.t9508643_teilenummer, t_index="")
        self.t9508645 = Item.ByKeys(teilenummer=self.t9508645_teilenummer, t_index="")

    @validationkit.run_with_roles(["public", "Engineering"])
    def test_precheck_life_cycle_with_mixed_selection(self):
        ctx_mock = MockContext()

        with self.assertRaises(ue.Exception) as ex:
            cs.variants.items._reinstantiate_part_pre_mask(  # pylint: disable=protected-access
                [self.t9508643, self.t9508645], ctx_mock
            )

        self.assertIn("Ausprägen", str(ex.exception))
