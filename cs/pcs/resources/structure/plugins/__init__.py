#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import sig

GET_SCHEDULE_PLUGINS = sig.signal()


@sig.connect(GET_SCHEDULE_PLUGINS)
def _register_resource_plugins(register_callback):
    from cs.pcs.resources.structure.plugins.alloc import AllocationPlugin
    from cs.pcs.resources.structure.plugins.demand import DemandPlugin
    from cs.pcs.resources.structure.plugins.organization import OrganizationPlugin
    from cs.pcs.resources.structure.plugins.person import PersonPlugin
    from cs.pcs.resources.structure.plugins.pool import PoolPlugin
    from cs.pcs.resources.structure.plugins.pool_assign import PoolAssignmentPlugin

    PLUGINS = [
        OrganizationPlugin,
        PersonPlugin,
        PoolPlugin,
        PoolAssignmentPlugin,
        DemandPlugin,
        AllocationPlugin,
    ]

    for plugin in PLUGINS:
        register_callback(plugin)
