# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import gc

from cdb.objects import paginated
from cdb.transactions import Transaction

from cs.classification import ClassificationChecksum
from cs.classification.object_classification import ClassificationUpdater


def update_existing_checksums():
    with Transaction():
        for checksums in paginated(ClassificationChecksum.Query(), 5000):
            for checksum in checksums:
                ClassificationUpdater.update_persistent_checksum_for_id(
                    checksum.ref_object_id,
                    checksum
                )
            gc.collect()

if __name__ == "__main__":
    update_existing_checksums()
