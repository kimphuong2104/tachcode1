#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import pytest

from cs.pcs.projects.project_structure.util import PCS_LEVEL
from cs.pcs.resources.structure.plugins import demand
from cs.pcs.resources.structure.plugins.tests.integration import common


@pytest.mark.integration
class DemandPluginIntegration(common.PluginIntegrationTestCase):
    def test_ResolveStructure(self):
        "returns structure sorted by position and cdb_object_id (Demand A)"
        demand_A = self.new_demand("demand_A", self.pool)

        self.assertListEqual(
            self.ResolveStructure(demand.DemandPlugin, demand_A),
            [PCS_LEVEL("demand_A", "cdbpcs_prj_demand", level=0)],
        )
