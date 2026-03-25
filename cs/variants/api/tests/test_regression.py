# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
from cs.variants.api import helpers, reinstantiate_parts
from cs.variants.api.tests.reinstantiate_test_case import ReinstantiateTestCase
from cs.variants.api.tests.subassembly_structure import SubassemblyStructure
from cs.vp.bom import AssemblyComponent, Item

t9508710_keys = {"teilenummer": "9508710", "t_index": ""}
t9508711_keys = {"teilenummer": "9508711", "t_index": ""}
t9508712_keys = {"teilenummer": "9508712", "t_index": ""}
t9508713_keys = {"teilenummer": "9508713", "t_index": ""}
t9508714_keys = {"teilenummer": "9508714", "t_index": ""}
t9508715_keys = {"teilenummer": "9508715", "t_index": ""}
t9508716_keys = {"teilenummer": "9508716", "t_index": ""}
t9508717_keys = {"teilenummer": "9508717", "t_index": ""}

t9508712 = SubassemblyStructure(t9508712_keys, {"menge": 1})
t9508713 = SubassemblyStructure(t9508713_keys, {"menge": 1})
t9508714 = SubassemblyStructure(t9508714_keys, {"menge": 1})

t9508711 = SubassemblyStructure(t9508711_keys, children=[t9508712, t9508713, t9508714])

# maxbom
t9508710 = SubassemblyStructure(t9508710_keys, children=[t9508711])

# first level for both v1 and v2
t9508716 = SubassemblyStructure(t9508716_keys, children=[t9508712, t9508713])

# v1
t9508715 = SubassemblyStructure(t9508715_keys, children=[t9508716])

# v2
t9508717 = SubassemblyStructure(t9508717_keys, children=[t9508716])


class TestRegression(ReinstantiateTestCase):
    def tearDown(self):
        super().tearDown()
        helpers.REUSE_ENABLED = self._old_reuse

    def setUp(self):
        super().setUp()
        self._old_reuse = helpers.REUSE_ENABLED
        helpers.REUSE_ENABLED = True

    def test_E073446(self):
        """
        E073446: change quantity on maxbom does not result in a new sub item

        Given is a MaxBOM *without* occurrences (this is important).

        - 9508710
            - 9508711
                - 9508712
                - 9508713
                - 9508714    <- sc - just 'False'

        Reuse is enabled
        There are 2 variants and every variant has one variant part.

        - 9508715 (v1) / 9508717 (v2)
            - 9508716           <- shared by both v1 and v2
                - 9508712
                - 9508713

        If you change the attribute 'menge' on part 9508713 (maxbom)
        and reinstantiate the variant v1 (only one variant) the expectation is that a new subpart
        for part 9508716 is created (with the new menge) and replaced only in v1.

        The bug was the check for occurrences has not considered the situation if the MaxBOM has no
        occurrences at all.

        """
        maxbom = Item.KeywordQuery(**t9508710_keys)[0]
        self.assert_subassembly_structure(t9508710, maxbom)

        v1 = Item.KeywordQuery(**t9508715_keys)[0]
        self.assert_subassembly_structure(t9508715, v1)

        v2 = Item.KeywordQuery(**t9508717_keys)[0]
        self.assert_subassembly_structure(t9508717, v2)

        # maxbom t9508711 -> t9508713
        bom_item = AssemblyComponent.ByKeys(
            cdb_object_id="901ab994-0e6e-11ee-928b-f875a45b4131"
        )
        self.assertIsNotNone(bom_item)
        self.assertEqual(bom_item.menge, 1)
        bom_item.menge = 10

        bom_item.Reload()

        # reinstantiate only v1 must result in a new subpart
        # for the first level (because menge changed in maxbom and existing subpart is
        # used in more than one bom)
        reinstantiate_parts([v1], maxbom)

        v1.Reload()
        v2.Reload()

        # note:
        # check for new teilenummer and new menge
        expected_structure = SubassemblyStructure(
            t9508715_keys,
            children=[
                SubassemblyStructure(
                    {"teilenummer": self.check_teilenummer_not_exists, "t_index": ""},
                    children=[
                        t9508712,
                        SubassemblyStructure(t9508713_keys, {"menge": 10}),
                    ],
                )
            ],
        )

        self.assert_subassembly_structure(expected_structure, v1)
        # no changes on v2
        self.assert_subassembly_structure(t9508717, v2)
