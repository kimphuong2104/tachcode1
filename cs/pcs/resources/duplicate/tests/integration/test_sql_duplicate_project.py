#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=too-many-locals,too-many-nested-blocks

import unittest

import pytest

from cdb import testcase
from cs.pcs.projects import Project
from cs.pcs.resources import RessourceAssignment, RessourceDemand
from cs.pcs.resources.duplicate.sql_duplicate_project import (
    delete_duplicated_project_with_resources,
    duplicate_project_with_resources,
)
from cs.pcs.resources.pools import ResourcePool
from cs.pcs.resources.pools.assignments import ResourcePoolAssignment
from cs.pcs.resources.resourceschedule import ResourceSchedule

PID = 'Ptest.ResSched'
DUPLICATED_PID = 'Ptest.Duplicated'


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


@pytest.mark.integration
class DuplicatingProjectWithResourcesTestCase(testcase.RollbackTestCase):
    # Duplicating Project with Resources related objects
    # and affirm, that the relevant objects exist.
    # Then delete the duplicated project
    # and affirm, that the relevant objects do not exist anymore.
    def test_duplicating_project_with_resources(self):
        original_project = Project.KeywordQuery(cdb_project_id=PID)[0]
        duplicated_project = duplicate_project_with_resources(PID, DUPLICATED_PID)
        # Allocations
        assert len(duplicated_project.RessourceAssignments) == len(original_project.RessourceAssignments)
        # Demands
        assert len(duplicated_project.RessourceDemands) == len(original_project.RessourceDemands)
        # TimeSchedules
        dprj_ts = duplicated_project.PrimaryTimeSchedule
        oprj_ts = original_project.PrimaryTimeSchedule
        assert len(dprj_ts) == len(oprj_ts)
        # ComninedSchedules
        dprj_cts = dprj_ts[0].CombinedResourceSchedules
        oprj_cts = oprj_ts[0].CombinedResourceSchedules
        assert len(dprj_cts) == len(oprj_cts)
        # ResourceSchedule
        dprj_rs = dprj_cts[0].ResourceSchedule
        oprj_rs = dprj_cts[0].ResourceSchedule
        # ResourceSchedule Content
        dprj_rs_c = dprj_rs.ResourceScheduleContents
        oprj_rs_c = oprj_rs.ResourceScheduleContents
        assert len(dprj_rs_c) == len(oprj_rs_c)
        # ResourcePools
        # Note: Original Project's RS has only one Element: The Resource Pool
        dprj_rps = ResourcePool.KeywordQuery(cdb_object_id=dprj_rs_c[0].content_oid)
        oprj_rps = ResourcePool.KeywordQuery(cdb_object_id=oprj_rs_c[0].content_oid)
        assert len(dprj_rps) == len(oprj_rps)
        dprj_rp = dprj_rps[0]
        oprj_rp = oprj_rps[0]
        # ResourcePool Memberships - at least one
        dprj_rp_m = dprj_rp.PoolAssignments
        oprj_rp_m = oprj_rp.PoolAssignments
        assert len(dprj_rp_m) == len(oprj_rp_m)

        dprj_rp_membership = dprj_rp_m[0]
        delete_duplicated_project_with_resources(DUPLICATED_PID)

        assert len(Project.KeywordQuery(cdb_project_id=DUPLICATED_PID)) == 0
        assert len(RessourceAssignment.KeywordQuery(cdb_project_id=DUPLICATED_PID)) == 0
        assert len(RessourceDemand.KeywordQuery(cdb_project_id=DUPLICATED_PID)) == 0
        assert len(ResourceSchedule.KeywordQuery(cdb_object_id=dprj_rs.cdb_object_id)) == 0
        assert len(ResourcePool.KeywordQuery(cdb_object_id=dprj_rp.cdb_object_id)) == 0
        assert len(ResourcePoolAssignment.KeywordQuery(
            cdb_object_id=dprj_rp_membership.cdb_object_id)) == 0


if __name__ == "__main__":
    unittest.main()
