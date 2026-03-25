#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2023 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/

from cdb.objects import OBJECT_STORE
from cs.variants import VariantSubPart
from cs.variants.api import helpers, instantiate_part
from cs.variants.api.constants_api import OBSOLETE_CHECKSUM_KEY
from cs.variants.api.tests.reuse_test_case import ReuseTestCase
from cs.variants.api.tests.subassembly_structure import SubassemblyStructure as Subst


class ChecksumSelfHealingTest(ReuseTestCase):
    def tearDown(self):
        super().tearDown()
        helpers.REUSE_ENABLED = False

    def setUp(self):
        super().setUp()
        helpers.REUSE_ENABLED = True

    def test_magic_key_matches(self) -> None:
        """reuse an old instantiated subpart with magic key

        Notes:
        - an old instantiated subpart has the magic key (after update to 15.8)
        - the old subpart matches the structure and must be reused during instantiate
        - the subpart checksum must be updated (magic key must ge gone)
        - test is the same as 'test_deep_reuse'
        """

        # change the checksum for t9508614 to magic key
        subpart = VariantSubPart.ByKeys(
            variability_model_id="1771fe02-f5e3-11eb-923d-f875a45b4131",
            part_object_id="6b5033bb-f6a5-11eb-923d-f875a45b4131",
            instantiated_of_part_object_id="ae11f303-ca9a-11eb-b955-98fa9bf98f6d",
        )

        assert subpart is not None
        subpart.structure_checksum = OBSOLETE_CHECKSUM_KEY

        OBJECT_STORE.clear()

        result = instantiate_part(self.var2, self.maxbom_deep)
        expected_result = Subst(
            {"teilenummer": result.teilenummer, "t_index": result.t_index},
            children=[self.t9508614],
        )

        self.assert_subassembly_structure(
            expected_result, result, assert_occurrences=True
        )

        subpart.Reload()
        assert subpart.structure_checksum != OBSOLETE_CHECKSUM_KEY

    def test_self_healing_extended(self):
        """
        All assemblies from maxbom are obsolete

        All subparts have obsolete checksum but matching structure
        Test is the same as 'test_deep_reuse'
        """
        from cs.variants.api.tests.update_checksums import mapping_t9508614

        all_subparts = []

        for each_sub_part in mapping_t9508614.values():
            sub_part = VariantSubPart.ByKeys(**each_sub_part)
            assert sub_part is not None
            sub_part.structure_checksum = OBSOLETE_CHECKSUM_KEY
            all_subparts.append(sub_part)

        OBJECT_STORE.clear()

        result = instantiate_part(self.var2, self.maxbom_deep)
        expected_result = Subst(
            {"teilenummer": result.teilenummer, "t_index": result.t_index},
            children=[self.t9508614],
        )

        self.assert_subassembly_structure(
            expected_result, result, assert_occurrences=True
        )

        for each_sub_part in all_subparts:
            each_sub_part.Reload()
            assert each_sub_part.structure_checksum != OBSOLETE_CHECKSUM_KEY
