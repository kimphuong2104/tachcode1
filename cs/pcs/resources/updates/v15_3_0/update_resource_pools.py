# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module update_resource_pools

If resource demands and/or resource allocations exist in your system, and you continue to use these data,
this script will be initiate the data migration
.
"""

from cdb.comparch import protocol
from cs.pcs.resources.updates.v15_3_0 import (
    AdjustAssignments,
    AdjustBackendRelations,
    AdjustDemands,
    CreatePoolStructureByOrgStructure,
    FillCapacityTables,
)

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

upd_classes = [
    CreatePoolStructureByOrgStructure,
    FillCapacityTables,
    AdjustDemands,
    AdjustAssignments,
    AdjustBackendRelations,
]


def main():
    prot = protocol.ModuleProtocol.createProtocol("migrate", "cs.pcs.resources")
    with protocol.ProtocolContext(prot):
        for cls in upd_classes:
            printable_name = cls().__class__.__name__
            start_message = "\nUpdate task {} running...".format(printable_name)
            end_message = "Update {} has been executed.".format(printable_name)
            protocol.logMessage(start_message)
            print(start_message)
            cls().run()
            protocol.logMessage(end_message)
            print(end_message)


# Guard importing as main module
if __name__ == "__main__":
    main()
