#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import pytest

from cdb import auth, sqlapi, testcase
from cdb.constants import kOperationDelete, kOperationNew
from cdb.objects.operations import operation
from cdb.objects.org import Organization, Person
from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task
from cs.pcs.resources import RessourceDemand
from cs.pcs.resources.pools import ResourcePool
from cs.pcs.resources.pools.assignments import Resource
from cs.pcs.resources.resourceschedule import ResourceSchedule, ResourceScheduleObject

ORG = "ORGANISATION"
USER_PREFIX = "USER"
CALENDAR_PROFILE_ID = "1cb4cf41-0f40-11df-a6f9-9435b380e702"
PID = "TEST_PRJ_RS_DEL"
TID = "TEST_TASK_RS_DEL"
DID = "TEST_DMD_RS_DEL"


def _create_org(name):
    return Organization.Create(org_id=name, name=name, org_type="Partner", country="DE")


def _create_user(login, org):
    return Person.Create(
        personalnummer=login,
        name=login,
        login=login,
        password="",
        firstname="test",
        lastname="user",
        title="",
        org_id=org.org_id,
        active_account="1",
        visibility_flag="1",
        password_rule="Unsafe",
        force_pwdchange="0",
        is_resource="1",
        capacity="8.0",
        cdb_classname="angestellter",
        calendar_profile_id=CALENDAR_PROFILE_ID,
    )


def _create_resource(user):
    kwargs = {
        "name": user.name,
        "capacity": user.capacity,
        "referenced_oid": user.cdb_object_id,
        "calendar_profile_id": user.calendar_profile_id,
    }
    return operation(kOperationNew, Resource, **kwargs)


def create_resources():
    org = _create_org(ORG)
    user1 = _create_user(USER_PREFIX + "1", org)
    r1 = _create_resource(user1)
    user2 = _create_user(USER_PREFIX + "2", org)
    r2 = _create_resource(user2)
    return r1, r2


def _get_resource_schedule_content_oids(rs_oid):
    return [
        e.content_oid
        for e in sqlapi.RecordSet2(
            sql="""SELECT content_oid FROM cdbpcs_rs_content WHERE view_oid = '{}'""".format(
                rs_oid
            )
        )
    ]


@pytest.mark.integration
class TestDeletionResourceScheduleContent(testcase.RollbackTestCase):
    def test_deletion_of_connections(self):
        # Deleting Objects shall also delete the corresponding pinned resource schedule entries (cdbpcs_rs_content)
        # Test Setup:
        #   ResourcePool with Resource 1 and Resource 2
        #   Project with Task 1 and Demand 1.1 and Demand 1.2 for Resource 1 and Task 2 and Demand 2 for Resource 2
        #   ResourceSchedule for Project with Resource 1 and 2 as well as Demand 1 and Demand 2 pinned
        # Test Cases:
        #   1) Deleting Pinned Object directly
        #      Deleting Demand 1.1 also removes the pinned entry
        #   2) Deleting Pinned Object indirectly
        #       2.a) Deleting Task 1 deletes remaining Demand 1.2, too. So, Demand 1.2 is not pinned anymore
        #       2.b) Deleting Project deletes Task1 and thus Demand 2. So, Demand 2 is not pinned anymore
        #   3) Deleting ResourceSchedule
        #      Deleting ResourceSchedule also deletes all pinned entries, but not the corresponding objects
        #      Thus Resource 1 and 2 still exist

        prj = Project.Create(cdb_project_id=PID, status=0, calendar_profile_id=CALENDAR_PROFILE_ID)
        task1 = Task.Create(cdb_project_id=PID, task_id=TID + "1", status=0)
        task2 = Task.Create(cdb_project_id=PID, task_id=TID + "2", status=0)

        resource1, resource2 = create_resources()
        rp = ResourcePool.Create(name="TEST RESOURCE POOL")

        demand1_1 = RessourceDemand.Create(
            cdb_project_id=PID,
            task_id=task1.task_id,
            pool_oid=rp.cdb_object_id,
            resource_oid=resource1.cdb_object_id,
            cdb_demand_id=DID + "1_1",
            hours=1.0,
        )
        demand1_2 = RessourceDemand.Create(
            cdb_project_id=PID,
            task_id=task1.task_id,
            pool_oid=rp.cdb_object_id,
            resource_oid=resource1.cdb_object_id,
            cdb_demand_id=DID + "1_2",
            hours=1.0,
        )
        demand2 = RessourceDemand.Create(
            cdb_project_id=PID,
            task_id=task2.task_id,
            pool_oid=rp.cdb_object_id,
            resource_oid=resource2.cdb_object_id,
            cdb_demand_id=DID + "2",
            hours=1.0,
        )

        kwargs = {
            "cdb_project_id": PID,
            "name": prj.project_name,
            "subject_id": auth.persno,
            "subject_type": "Person",
            "cdb_objektart": "cdbpcs_res_schedule",
        }
        rs = ResourceSchedule.createObject(**kwargs)
        rs_oid = rs.cdb_object_id

        pinned_oids = []
        i = 0
        for obj in [resource1, resource2, demand1_1, demand1_2, demand2]:
            pinned_oids.append(obj.cdb_object_id)
            kwargs = {}
            kwargs["view_oid"] = rs.cdb_object_id
            kwargs["content_oid"] = obj.cdb_object_id
            kwargs["cdb_content_classname"] = obj.GetClassname()
            kwargs["position"] = i
            kwargs["unremovable"] = 0
            ResourceScheduleObject.createObject(**kwargs)
            i += 10

        # Check if all four objects are pinned
        self.assertListEqual(pinned_oids, _get_resource_schedule_content_oids(rs_oid))

        # Delete Demand 1.1 -> Demand 1.1 is not pinned anymore
        operation(kOperationDelete, demand1_1)
        self.assertNotIn(
            demand1_1.cdb_object_id, _get_resource_schedule_content_oids(rs_oid)
        )

        # Delete t1 -> Demand 1.2 is not pinned anymore
        operation(kOperationDelete, task1)
        self.assertNotIn(
            demand1_2.cdb_object_id, _get_resource_schedule_content_oids(rs_oid)
        )

        # Delete prj -> demand2 is not pinned anymore
        operation(kOperationDelete, prj)
        self.assertNotIn(
            demand2.cdb_object_id, _get_resource_schedule_content_oids(rs_oid)
        )

        # Delete ResourceSchedule -> Nothing is pinned anymore
        operation(kOperationDelete, rs)
        remaining_pinned_oids = _get_resource_schedule_content_oids(rs_oid)
        self.assertNotIn(resource1.cdb_object_id, remaining_pinned_oids)
        self.assertNotIn(resource2.cdb_object_id, remaining_pinned_oids)
        # But Resource 1 and 2 still exist
        self.assertEqual(
            1, len(Resource.KeywordQuery(cdb_object_id=resource1.cdb_object_id))
        )
        self.assertEqual(
            1, len(Resource.KeywordQuery(cdb_object_id=resource2.cdb_object_id))
        )


if __name__ == "__main__":
    unittest.main()
