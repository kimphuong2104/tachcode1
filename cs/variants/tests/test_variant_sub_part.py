#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from cdb import testcase
from cdb.objects.operations import operation
from cs.variants import VariantSubPart
from cs.variants.items import AssemblyComponent
from cs.vp.items import Item


class TestVariantSubPart(testcase.RollbackTestCase):
    def test_delete_instantiated_item_deletes_sub_part_entry(self):
        t9508635_bom_item_id = "edc325dc-fc37-11eb-923e-f875a45b4131"
        t9508635_id = "edc325d6-fc37-11eb-923e-f875a45b4131"

        bom_item_to_delete = AssemblyComponent.ByKeys(
            cdb_object_id=t9508635_bom_item_id
        )
        operation("CDB_Delete", bom_item_to_delete)

        instantiated_item = Item.ByKeys(cdb_object_id=t9508635_id)

        prev_sub_part = VariantSubPart.ByKeys(part_object_id=t9508635_id)
        self.assertIsNotNone(prev_sub_part)

        operation("CDB_Delete", instantiated_item)

        post_sub_part = VariantSubPart.ByKeys(part_object_id=t9508635_id)
        self.assertIsNone(post_sub_part, "sub part entry not removed")
