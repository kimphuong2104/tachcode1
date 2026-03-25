#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import pytest

from cs.pcs.projects.project_structure.util import PCS_LEVEL
from cs.pcs.resources.structure.plugins import alloc
from cs.pcs.resources.structure.plugins.tests.integration import common


@pytest.mark.integration
class AllocationPluginIntegration(common.PluginIntegrationTestCase):
    def test_ResolveStructure(self):
        "returns structure sorted by position and cdb_object_id (Allocation A)"
        demand = self.new_demand("demand_A")
        alloc_A = self.new_alloc("alloc_A", demand)
        self.assertListEqual(
            self.ResolveStructure(alloc.AllocationPlugin, alloc_A),
            [PCS_LEVEL("alloc_A", "cdbpcs_prj_alloc", level=0)],
        )
