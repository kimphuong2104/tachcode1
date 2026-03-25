#  -*- mode: python; coding: utf-8 -*-
#  #
#  Copyright (C) 1990 - 2023 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from cdb.sqlapi import SQLupdate
from cs.variants.api.constants_api import OBSOLETE_CHECKSUM_KEY


class ResetChecksum:
    """Reset the checksum from previous version"""

    _halt_on_error_ = False

    def run(self):
        SQLupdate(
            f"cs_variant_sub_part SET structure_checksum = '{OBSOLETE_CHECKSUM_KEY}'"
        )


pre = []
post = [ResetChecksum]

if __name__ == "__main__":
    ResetChecksum().run()
