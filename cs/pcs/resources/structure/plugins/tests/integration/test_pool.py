#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import pytest

from cs.pcs.projects.project_structure.util import PCS_LEVEL
from cs.pcs.resources.structure.plugins import pool
from cs.pcs.resources.structure.plugins.tests.integration import common
from cs.pcs.resources.structure.plugins.tests.integration.common import (
    date_to_date_object,
)


@pytest.mark.integration
class PoolPluginIntegration(common.PluginIntegrationTestCase):

    def setup_structure(self):
        """
        returns structure sorted by position and cdb_object_id

        ResourcePool A
            Demand A.1
            Allocation A.2
            ResourcePool A.3
                Resource A.3.1
                    Demand A.3.1.1
                    Allocation A.3.1.2
            Resource A.4
                Demand A.4.1
                Allocation A.4.2
        """

        person_2 = self.new_person("person_2")
        demand_A_1 = self.new_demand("demand_A_1")
        self.new_alloc("alloc_A_2", demand_A_1)
        subpool_A_3 = self.new_pool("subpool_A_3", self.pool)
        res_A_3_1 = self.assign_resource(
            "res_A_3_1",
            subpool_A_3,
            person_2,
            date_to_date_object("2021-01-01"),
            date_to_date_object("2022-01-01"),
        )
        demand_A_3_1_1 = self.new_demand(
            "demand_A_3_1_1", pool=self.EMPTY, res=res_A_3_1
        )
        self.new_alloc("alloc_A_3_1_2", demand_A_3_1_1, pool=self.EMPTY, res=res_A_3_1)
        res_A_4 = self.assign_resource(
            "res_A_4",
            None,
            None,
            date_to_date_object("2023-05-01"),
            date_to_date_object("2023-07-01"),
        )
        demand_A_4_1 = self.new_demand("demand_A_4_1", res=res_A_4)
        self.new_alloc("alloc_A_4_2", demand_A_4_1, res=res_A_4)

        self.new_demand("demand_outside", res=res_A_4, future=True)
        self.new_alloc("alloc_outside", demand_A_4_1, res=res_A_4, future=True)

    def test_ResolveStructure_complete_time_frame(self):
        self.setup_structure()
        time_frame = (1, 2022, 4, 2023)
        self.assertListEqual(
            self.ResolveStructure(pool.PoolPlugin, self.pool, time_frame),
            [
                PCS_LEVEL(
                    str("pool_A"),
                    str("cdbpcs_resource_pool"),
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
                PCS_LEVEL(
                    str("subpool_A_3"),
                    str("cdbpcs_resource_pool"),
                    level=1,
                ),
                PCS_LEVEL(
                    str("res_A_3_1"),
                    str("cdbpcs_pool_assignment"),
                    level=2,
                ),
                PCS_LEVEL(
                    str("demand_A_3_1_1"),
                    str("cdbpcs_prj_demand"),
                    level=3,
                ),
                PCS_LEVEL(
                    str("alloc_A_3_1_2"),
                    str("cdbpcs_prj_alloc"),
                    level=3,
                ),
                PCS_LEVEL(
                    str("res_A_4"),
                    str("cdbpcs_pool_assignment"),
                    level=1,
                ),
                PCS_LEVEL(
                    str("demand_A_4_1"),
                    str("cdbpcs_prj_demand"),
                    level=2,
                ),
                PCS_LEVEL(
                    str("alloc_A_4_2"),
                    str("cdbpcs_prj_alloc"),
                    level=2,
                ),
            ],
        )

    def test_ResolveStructure_partial_time_frame(self):
        self.setup_structure()
        time_frame = (2, 2022, 2, 2023)
        result = self.ResolveStructure(pool.PoolPlugin, self.pool, time_frame)
        self.assertListEqual(
            result,
            [
                PCS_LEVEL(
                    str("pool_A"),
                    str("cdbpcs_resource_pool"),
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
                PCS_LEVEL(
                    str("subpool_A_3"),
                    str("cdbpcs_resource_pool"),
                    level=1,
                ),
                PCS_LEVEL(
                    str("res_A_4"),
                    str("cdbpcs_pool_assignment"),
                    level=1,
                ),
                PCS_LEVEL(
                    str("demand_A_4_1"),
                    str("cdbpcs_prj_demand"),
                    level=2,
                ),
                PCS_LEVEL(
                    str("alloc_A_4_2"),
                    str("cdbpcs_prj_alloc"),
                    level=2,
                ),
            ],
            f"unexpected result: {result}"
        )
