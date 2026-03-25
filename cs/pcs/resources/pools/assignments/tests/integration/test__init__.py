#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=broad-except

import datetime
import unittest

import pytest

from cdb import testcase
from cdb.objects.operations import operation
from cdb.objects.org import Organization, User
from cs.calendar import CalendarProfile
from cs.pcs.resources.pools import ResourcePool
from cs.pcs.resources.pools.assignments import Resource
from cs.pcs.resources.pools.assignments.person import ResourcePoolAssignmentPerson

CALENDAR_PROFILE_ID = "1cb4cf41-0f40-11df-a6f9-9435b380e702"


@pytest.mark.integration
class TestResourceIntegration(testcase.RollbackTestCase):
    def _create_pool(self, pool_id, **kwargs):
        new_kwargs = {
            "cdb_object_id": f"oid{pool_id}",
            "name": f"pool{pool_id}",
            "parent_oid": "",
        }
        if kwargs:
            new_kwargs.update(**kwargs)
        return ResourcePool.Create(**new_kwargs)

    def _create_person(self, personalnummer, isResource, capacity):
        org_id = Organization.Query()[0].org_id
        new_kwargs = {
            "personalnummer": personalnummer,
            "is_resource": isResource,
            "capacity": capacity,
            "calendar_profile_id": CALENDAR_PROFILE_ID,
            "org_id": org_id,
            "login": personalnummer,
            "visibility_flag": True,
            "lastname": personalnummer,
        }
        # use operation so that user exits run and resource creation is triggered
        return operation("CDB_Create", User, **new_kwargs)

    def _modify_object(self, obj, kwargs):
        # use operation so that user exits run and resource modification is triggered
        operation("CDB_Modify", obj, **kwargs)

    def _assign_to_pool(self, person, pool):
        resource = Resource.KeywordQuery(referenced_oid=person.cdb_object_id)[0]
        kwargs = {
            "resource_oid": resource.cdb_object_id,
            "pool_oid": pool.cdb_object_id,
            "person_id": person.personalnummer,
            "start_date": datetime.date(2023, 1, 1),
            "end_date": datetime.date(2023, 12, 31),
        }
        # use operation so that user exits run
        return operation("CDB_Create", ResourcePoolAssignmentPerson, **kwargs)

    def test_capacity_update(self):
        pool = self._create_pool(1)
        person = self._create_person("user1", True, 4)
        resource = Resource.ByKeys(referenced_oid=person.cdb_object_id)
        self.assertEqual(resource.capacity, person.capacity)

        assignment = self._assign_to_pool(person, pool)
        self.assertEqual(assignment.capacity, person.capacity)
        self.assertEqual(resource.capacity, person.capacity)

        newCapacity = 5
        self._modify_object(person, {"capacity": newCapacity})
        resource.Reload()
        assignment.Reload()
        self.assertEqual(assignment.capacity, newCapacity)
        self.assertEqual(resource.capacity, newCapacity)

    def test_resource_updates(self):
        person = self._create_person("user1", True, 4)
        resource = Resource.ByKeys(referenced_oid=person.cdb_object_id)
        self.assertEqual(resource.capacity, person.capacity)
        self.assertEqual(resource.name, person.name)
        self.assertEqual(resource.calendar_profile_id, person.calendar_profile_id)

        CalendarProfile.Create(cdb_object_id="newCal", name="newCal")
        changes = {
            "name": "newName",
            "capacity": 5,
            "calendar_profile_id": "newCal",
        }
        self._modify_object(person, changes)
        resource.Reload()
        self.assertEqual(resource.capacity, 5)
        self.assertEqual(resource.name, "newName")
        self.assertEqual(resource.calendar_profile_id, "newCal")

    def _test_access_right(self, right, personalnummer, expected):
        person = self._create_person("user1", True, 4)
        resource = Resource.ByKeys(referenced_oid=person.cdb_object_id)
        self.assertEqual(resource.CheckAccess(right, personalnummer), expected)

    def test_accept_right(self):
        self._test_access_right("accept", "caddok", True)

    def test_create_right(self):
        self._test_access_right("create", "caddok", True)

    def test_delete_right(self):
        self._test_access_right("delete", "caddok", True)

    def test_read_right(self):
        self._test_access_right("read", "caddok", True)

    def test_save_right(self):
        self._test_access_right("save", "caddok", True)


if __name__ == "__main__":
    unittest.main()
