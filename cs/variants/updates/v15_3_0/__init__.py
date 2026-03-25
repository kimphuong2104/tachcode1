#  -*- mode: python; coding: utf-8 -*-
#
#  Copyright (C) 1990 - 2021 CONTACT Software GmbH
#  All rights reserved.
#  https://www.contact-software.com/
from cdb.comparch import protocol
from cdb.transactions import Transaction
from cs.variants import Variant


class CalculateVariantClassificationChecksum:
    _halt_on_error_ = False

    def run(self):
        # Has to be done manually because checks read rights but update task has no user/login information
        protocol.logMessage(
            "Please execute:\npowerscript -m cs.variants.updates.v15_3_0.__init__"
        )


pre = []
post = [CalculateVariantClassificationChecksum]


if __name__ == "__main__":
    with Transaction():
        for each in Variant.Query():
            each.update_classification_checksum()
