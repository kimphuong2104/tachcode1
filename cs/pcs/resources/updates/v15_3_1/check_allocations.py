# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module check_allocations

If resource demands and/or resource allocations exist in your system, this script
will check the need for the data migration of the primary keys for demands and assignments.
"""

from cdb.comparch import protocol
from cs.pcs.resources.updates.v15_3_1 import CheckResourcesPrimaryKeys

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

upd_classes = [
    CheckResourcesPrimaryKeys,
]


def main():
    for cls in upd_classes:
        printable_name = cls().__class__.__name__
        start_message = "\nCheck task {} running...".format(printable_name)
        end_message = "nCheck {} has been executed.".format(printable_name)
        protocol.logMessage(start_message)
        print(start_message)
        cls().run()
        protocol.logMessage(end_message)
        print(end_message)


# Guard importing as main module
if __name__ == "__main__":
    main()
