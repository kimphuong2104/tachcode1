#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2022 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from cdb import sqlapi
from cdb.testcase import rollback
from cs.variants import VariantSubPart
from cs.variants.api.constants_api import OBSOLETE_CHECKSUM_KEY
from cs.variants.updates.v15_8_0 import ResetChecksum


@rollback
def test_update_reset_checksum() -> None:
    # first - reset all data to specific value (but not magic key)
    sqlapi.SQLupdate("cs_variant_sub_part SET structure_checksum = 'NONE'")
    # check
    result = VariantSubPart.KeywordQuery(structure_checksum=OBSOLETE_CHECKSUM_KEY)
    assert not result

    reset_object = ResetChecksum()
    reset_object.run()

    # check again
    result = VariantSubPart.KeywordQuery(structure_checksum=OBSOLETE_CHECKSUM_KEY)
    assert result
