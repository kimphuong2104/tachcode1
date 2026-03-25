#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from os import listdir, path, unlink

import mock
import pytest

from cdb import CADDOK, ddl, sqlapi, testcase
from cdb.objects.org import Organization, Person
from cs.pcs.projects import Project
from cs.pcs.resources.pools import ResourcePool, ResourcePool2Schedule
from cs.pcs.resources.pools.assignments import Resource, ResourcePoolAssignment
from cs.pcs.resources.resourceschedule import (
    CombinedResourceSchedule,
    ResourceSchedule,
    ResourceScheduleObject,
)
from cs.pcs.resources.updates import v15_5_0
from cs.pcs.timeschedule import TimeSchedule


def setup_module():
    testcase.run_level_setup()


@pytest.mark.integration
class TestRemovePredefinedFields(testcase.RollbackTestCase):
    "integration test simulating update from <15.5.0 to 15.5.0 and removing old table fields"

    def setUp(self):
        super().setUp()
        self.changes = [
            {
                "table": "cdbpcs_resource",
                "fields": ["name", "capacity", "calendar_profile_id"],
            },
            {"table": "cdbpcs_pool_assignment", "fields": ["capacity"]},
        ]
        for change in self.changes:
            table = ddl.Table(change["table"])
            for field in change["fields"]:
                if not table.hasColumn(field):
                    table.addAttributes(ddl.Char(field, 20))

        self.removeFiles()

    def tearDown(self):
        super().tearDown()
        for change in self.changes:
            table = ddl.Table(change["table"])
            for field in change["fields"]:
                if table.hasColumn(field):
                    table.dropAttributes(field)
        self.removeFiles()

    def searchFiles(self):
        prefix = "resources15.5.0-predefined-fields"
        files = []
        for fname in listdir(CADDOK.TMPDIR):
            fpath = path.join(CADDOK.TMPDIR, fname)
            if path.isfile(fpath) and fname.startswith(prefix):
                files.append(fpath)
        return files

    def removeFiles(self):
        files = self.searchFiles()
        for f in files:
            unlink(f)

    def test_RemoveOldFields(self):
        update = v15_5_0.RemovePredefinedFields()
        update.run()

        errors = []
        passed = True

        # check if fields were actually removed from table
        for change in self.changes:
            table = ddl.Table(change["table"])
            for field in change["fields"]:
                if table.hasColumn(field):
                    passed = False
                    errors.append(
                        "Field '{0}' still in {1}".format(field, change["table"])
                    )
        self.assertTrue(passed, ("\n").join(errors))

    def test_correctExport(self):
        update = v15_5_0.RemovePredefinedFields()
        update.run()

        errors = []
        passed = True

        # Check if file was correctly written
        files = self.searchFiles()
        fileContent = ""
        with open(files[0], "r", encoding="utf-8") as myfile:
            fileContent = myfile.read()
        for change in self.changes:
            if "T" + change["table"] not in fileContent:
                passed = False
                errors.append("Table not in exported file")
        self.assertTrue(passed, ("\n").join(errors))

    def test_MultipleFiles(self):
        update = v15_5_0.RemovePredefinedFields()
        # run test two times to verify file won't be overwritten
        update.run()
        update.run()
        files = self.searchFiles()
        self.assertEqual(len(files), 2)


class TestRemoveUnsupportedScheduleElements(testcase.RollbackTestCase):
    def setUp(self):
        super().setUp()
        self.update = v15_5_0.RemoveUnsupportedScheduleElements()

    def _create_content(self):
        self.content = [
            ResourcePool.Create(
                cdb_object_id="pool",
                name="pool",
            ),
            Person.Create(
                cdb_object_id="person",
                personalnummer="person",
            ),
            Resource.Create(
                cdb_object_id="resource",
                referenced_oid="person",
            ),
            ResourcePoolAssignment.Create(
                cdb_object_id="pool_asgn",
                pool_oid="pool",
                resource_oid="resource",
                cdb_classname="cdbpcs_pool_person_assign",
            ),
            Organization.Create(
                cdb_object_id="org",
                org_id="org",
                name="org",
            ),
        ]

    def _assign_content(self, schedule_uuid):
        for x in self.content:
            try:
                classname = x.GetClassDef().getBaseClassNames()[0]
            except IndexError:
                classname = x.GetClassname()
            ResourceScheduleObject.Create(
                position=10,
                view_oid=schedule_uuid,
                content_oid=x.cdb_object_id,
                cdb_content_classname=classname,
            )

    def _create_schedule_no_refs(self):
        no_refs = ResourceSchedule.Create(
            cdb_object_id="no_refs",
            name="no_refs",
        )
        self._assign_content(no_refs.cdb_object_id)
        return no_refs.cdb_object_id

    def _create_schedule_multi(self):
        multi = ResourceSchedule.Create(
            cdb_object_id="multi",
            name="multi",
        )
        ResourcePool2Schedule.Create(
            resource_schedule_oid=multi.cdb_object_id,
            pool_oid="pool1",
        )
        ResourcePool2Schedule.Create(
            resource_schedule_oid=multi.cdb_object_id,
            pool_oid="pool2",
        )
        self._assign_content(multi.cdb_object_id)
        return multi.cdb_object_id

    def _create_schedule_multi_ref(self):
        multi_ref = ResourceSchedule.Create(
            cdb_object_id="multi_ref",
            name="multi_ref",
        )
        ResourcePool2Schedule.Create(
            resource_schedule_oid=multi_ref.cdb_object_id,
            pool_oid="original_pool",
        )
        CombinedResourceSchedule.Create(
            resource_schedule_oid=multi_ref.cdb_object_id,
            time_schedule_oid="time",
        )
        self._assign_content(multi_ref.cdb_object_id)
        return multi_ref.cdb_object_id

    def _create_schedule_with_pool(self):
        with_pool = ResourceSchedule.Create(
            cdb_object_id="with_pool",
            name="with_pool",
        )
        sqlapi.Record(
            "cdb_object",
            id="original_pool",
            relation="cdbpcs_resource_pool",
        ).insert()
        ResourcePool2Schedule.Create(
            resource_schedule_oid=with_pool.cdb_object_id,
            pool_oid="original_pool",
        )
        self._assign_content(with_pool.cdb_object_id)
        return with_pool.cdb_object_id

    def _create_schedule_with_org(self):
        with_org = ResourceSchedule.Create(
            cdb_object_id="with_org",
            name="with_org",
        )
        sqlapi.Record(
            "cdb_object",
            id="original_org",
            relation="cdb_org",
        ).insert()
        ResourcePool2Schedule.Create(
            resource_schedule_oid=with_org.cdb_object_id,
            pool_oid="original_org",
        )
        self._assign_content(with_org.cdb_object_id)
        return with_org.cdb_object_id

    def _create_schedule_with_ts(self):
        with_ts = ResourceSchedule.Create(
            cdb_object_id="with_ts",
            name="with_ts",
        )
        CombinedResourceSchedule.Create(
            resource_schedule_oid=with_ts.cdb_object_id,
            time_schedule_oid="time",
        )
        self._assign_content(with_ts.cdb_object_id)
        return with_ts.cdb_object_id

    def _create_schedule_with_ts_and_project(self):
        with_ts_proj = ResourceSchedule.Create(
            cdb_object_id="with_ts_proj",
            name="with_ts_proj",
        )
        project = Project.Create(
            cdb_object_id="Ptest.sched_upd",
            cdb_project_id="Ptest.sched_upd",
        )
        time_schedule = TimeSchedule.Create(
            cdb_object_id="time_project",
            name="time_project",
            cdb_project_id=project.cdb_project_id,
        )
        CombinedResourceSchedule.Create(
            resource_schedule_oid=with_ts_proj.cdb_object_id,
            time_schedule_oid=time_schedule.cdb_object_id,
        )
        self._assign_content(with_ts_proj.cdb_object_id)
        return with_ts_proj.cdb_object_id

    def test_remove(self):
        self._create_content()
        a = self._create_schedule_no_refs()
        b = self._create_schedule_multi_ref()
        c = self._create_schedule_with_pool()
        d = self._create_schedule_with_org()
        e = self._create_schedule_with_ts()
        f = self._create_schedule_with_ts_and_project()
        g = self._create_schedule_multi()

        sqlapi.SQLdelete(
            "FROM cdbpcs_resource_schedule "
            f"WHERE cdb_object_id NOT IN ('{a}', '{b}', '{c}', '{d}', '{e}', '{f}', '{g}')"
        )

        with mock.patch.object(v15_5_0.protocol, "logError") as log_error:
            self.update.run()

        log_error.assert_has_calls([
            mock.call(
                "ignoring invalid resource schedule 'multi_ref':"
                "\n    cdbpcs_resource_pool 'original_pool'"
                "\n    cdbpcs_time_schedule 'time'"
            ),
            mock.call(
                "ignoring invalid resource schedule 'no_refs':"
                "\n    None 'None'"
                "\n    cdbpcs_time_schedule 'None'"
            ),
            mock.call("ignoring invalid resource schedule 'multi': multiple assignments"),
        ], any_order=True)
        self.assertEqual(log_error.call_count, 3)

        elements = [
            (x["view_oid"], x["content_oid"], x["cdb_content_classname"])
            for x in sqlapi.RecordSet2(
                "cdbpcs_rs_content",
                f"view_oid IN ('{a}', '{b}', '{c}', '{d}', '{e}', '{f}', '{g}')"
            )
        ]
        self.assertEqual(set(elements), set([
            # ignore invalid schedule "no_ref" (neither pool nor time schedule assigned)
            (a, 'org', 'cdb_organization'),
            (a, 'person', 'cdb_person'),
            (a, 'pool', 'cdbpcs_resource_pool'),
            (a, 'resource', 'cdbpcs_resource'),
            (a, 'pool_asgn', 'cdbpcs_pool_assignment'),
            # ignore invalid schedule "multi_ref" (both pool and time schedule assigned)
            (b, 'org', 'cdb_organization'),
            (b, 'person', 'cdb_person'),
            (b, 'pool', 'cdbpcs_resource_pool'),
            (b, 'resource', 'cdbpcs_resource'),
            (b, 'pool_asgn', 'cdbpcs_pool_assignment'),
            # standalone "with_pool" and "with_org": remove everything and add original pool or org
            (c, "original_pool", 'cdbpcs_resource_pool'),
            (d, "original_org", 'cdb_organization'),
            # time schedule - project: keep pool + resource only
            (e, 'pool_asgn', 'cdbpcs_pool_assignment'),
            (e, "pool", 'cdbpcs_resource_pool'),
            # time schedule + project: keep pool + resource only
            (f, 'pool_asgn', 'cdbpcs_pool_assignment'),
            (f, "pool", 'cdbpcs_resource_pool'),
            # ignore invalid schedule "multi" (two different pools assigned)
            (g, 'org', 'cdb_organization'),
            (g, 'person', 'cdb_person'),
            (g, 'pool', 'cdbpcs_resource_pool'),
            (g, 'resource', 'cdbpcs_resource'),
            (g, 'pool_asgn', 'cdbpcs_pool_assignment'),
        ]))


@pytest.mark.integration
class TestUpdateClassName(testcase.RollbackTestCase):
    def setUp(self):
        super().setUp()
        self.update = v15_5_0.UpdateClassName()

    def _setup_testdata(self):
        # cdbpcs_resource_schedule
        sql_delete = """
        FROM cdbpcs_resource_schedule
        """
        sqlapi.SQLdelete(sql_delete)
        for (uuid, classname) in [
            ("oid0", ""),
            ("oid1", ""),
            ("oid2", "FOO"),
            ("oid3", "FOO"),
            ("oid4", None),
            ("oid5", None),
        ]:
            sqlapi.Record(
                "cdbpcs_resource_schedule",
                name="name",
                cdb_object_id=uuid,
                cdb_classname=classname,
            ).insert()
        # cdbpcs_time2res_schedule
        sql_delete = """
        FROM cdbpcs_time2res_schedule
        """
        sqlapi.SQLdelete(sql_delete)
        for (r_oid, t_oid) in [
            ("oid1", "toid1",),
            ("oid3", "toid3"),
            ("oid5", "toid5"),
        ]:
            sqlapi.Record(
                "cdbpcs_time2res_schedule",
                resource_schedule_oid=r_oid,
                time_schedule_oid=t_oid,
            ).insert()

    def test_update(self):
        self._setup_testdata()

        updateObj = self.update
        updateObj.run()

        schedules = [
            (sched["name"], sched["cdb_object_id"], sched["cdb_classname"])
            for sched in sqlapi.RecordSet2("cdbpcs_resource_schedule")
        ]

        self.assertEqual(set(schedules), set([
            ('name', 'oid0', 'cdbpcs_resource_schedule'),
            ('name', 'oid1', 'cdbpcs_resource_schedule_time'),
            ('name', 'oid2', 'cdbpcs_resource_schedule'),
            ('name', 'oid3', 'cdbpcs_resource_schedule_time'),
            ('name', 'oid4', 'cdbpcs_resource_schedule'),
            ('name', 'oid5', 'cdbpcs_resource_schedule_time'),
        ]))
