#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import pytest

from cs.pcs.projects.project_structure.util import PCS_LEVEL
from cs.pcs.resources.structure.plugins import pool_assign
from cs.pcs.resources.structure.plugins.tests.integration import common


@pytest.mark.integration
class PoolAssignmentPluginIntegration(common.PluginIntegrationTestCase):
    maxDiff = None

    def test_ResolveStructure(self):
        """
        returns structure sorted by position and cdb_object_id

        Resource A
            Demand A.1
            Allocation A.2
        """
        res_A = self.assign_resource("res_A")
        demand_A_1 = self.new_demand("demand_A_1", self.pool, res_A)
        self.new_alloc("alloc_A_2", demand_A_1, res=res_A)

        # these will be filtered out
        self.new_demand("demand_outside", self.pool, res_A, future=True)
        self.new_alloc("alloc_outside", demand_A_1, res=res_A, future=True)

        time_frame = (1, 2022, 4, 2022)
        result = self.ResolveStructure(pool_assign.PoolAssignmentPlugin, res_A, time_frame)
        self.assertListEqual(
            result,
            [
                PCS_LEVEL(
                    str("res_A"),
                    str("cdbpcs_pool_assignment"),
                    level=0,
                ),
                PCS_LEVEL(
                    str("demand_A_1"),
                    str("cdbpcs_prj_demand"),
                    level=1,
                ),
                PCS_LEVEL(
                    str("alloc_A_2"),
                    str("cdbpcs_prj_alloc"),
                    level=1,
                ),
            ],
        )
