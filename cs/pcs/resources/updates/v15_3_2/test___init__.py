#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import pytest

from cdb import sqlapi, testcase
from cs.pcs.resources.updates.v15_3_2 import (
    RemoveOrphanedResourceScheduleObjects,
    get_classes_and_tables,
)


@pytest.mark.integration
class TestRemoveOrphanedResourceScheduleObjects(testcase.RollbackTestCase):
    maxDiff = None

    def test_run(self):
        uuids_ok = set()
        uuids_all = set()

        def get_pinned_uuids():
            rset = sqlapi.RecordSet2("cdbpcs_rs_content")
            return {x.content_oid for x in rset}

        def setup_data():
            sqlapi.Record(
                "cdbpcs_resource_schedule",
                cdb_object_id="integr_test_schedule",
                name="Integration Test",
            ).insert()
            sqlapi.Record(
                "cdbpcs_prj_demand",
                cdb_object_id="integr_test_demand",
                cdb_project_id="integr_test_demand",
                cdb_demand_id="integr_test_demand",
            ).insert()
            sqlapi.Record(
                "cdbpcs_prj_alloc",
                cdb_object_id="integr_test_alloc",
                cdb_project_id="integr_test_alloc",
                cdb_alloc_id="integr_test_alloc",
            ).insert()
            sqlapi.Record(
                "cdbpcs_resource_pool",
                cdb_object_id="integr_test_pool",
                name="Integration Test",
            ).insert()
            sqlapi.Record(
                "cdbpcs_pool_assignment",
                cdb_object_id="integr_test_asgn",
                pool_oid="some pool",
                resource_oid="some resource",
                capacity=42,
            ).insert()

            sqlapi.SQLdelete("FROM cdbpcs_rs_content")
            generator = get_classes_and_tables(
                RemoveOrphanedResourceScheduleObjects.__base_classes__
            )

            for counter, (classname, table) in enumerate(generator):
                try:
                    # this test relies on at least one entry in all
                    # tables from other packages,
                    # namely "cdb_org" and "angestellter"
                    uuid_ok = sqlapi.RecordSet2(table, max_rows=1)[0].cdb_object_id
                except IndexError:
                    raise RuntimeError("cannot find entry in {}".format(table))

                uuids_ok.add(uuid_ok)
                uuids_all.add(uuid_ok)
                sqlapi.Record(
                    "cdbpcs_rs_content",
                    position=42,
                    view_oid="{}".format(counter),
                    content_oid=uuid_ok,
                    cdb_content_classname=classname,
                ).insert()

                uuid_orphan = "{} orphan {}".format(classname, counter)
                uuids_all.add(uuid_orphan)
                sqlapi.Record(
                    "cdbpcs_rs_content",
                    position=42,
                    view_oid="{}".format(counter),
                    content_oid=uuid_orphan,
                    cdb_content_classname=classname,
                ).insert()

        setup_data()
        self.assertEqual(get_pinned_uuids(), uuids_all)
        RemoveOrphanedResourceScheduleObjects().run()
        self.assertEqual(get_pinned_uuids(), uuids_ok)


if __name__ == "__main__":
    unittest.main()
