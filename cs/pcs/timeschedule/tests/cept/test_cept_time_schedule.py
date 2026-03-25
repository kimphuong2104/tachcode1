#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import pytest
from cdb import testcase

from cs.pcs.projects.tests.common import assign_user_to_common_role, generate_user
from cs.pcs.projects.tests.common_data import create_project, create_time_schedule
from cs.pcs.timeschedule import TimeScheduleObject


@pytest.mark.cept
class TimeScheduleAccess(testcase.RollbackTestCase):
    __public__ = "public"
    __owner__ = "owner"
    __admin__ = "admin"
    __manager__ = "manager"

    def setUp(self):
        super().setUp()
        generate_user(self.__public__)
        generate_user(self.__owner__)
        generate_user(self.__admin__)
        assign_user_to_common_role(self.__admin__, "Administrator")

    def assertAccess(self, access_rights, obj, expected):
        granted = {
            user_id: [
                access for access in access_rights if obj.CheckAccess(access, user_id)
            ]
            for user_id in expected
        }
        self.assertEqual(granted, expected)

    def _create_schedule(self, with_project):
        if with_project:
            generate_user(self.__manager__)
            project, _ = create_project(user_id=self.__manager__)
            return create_time_schedule(project, self.__owner__)

        return create_time_schedule(None, self.__owner__)

    def _create_content(self, schedule):
        return TimeScheduleObject.Create(
            position=10,
            view_oid=schedule.cdb_object_id,
            content_oid="4d6e4edd-94ec-11e9-833d-d0577b2793bc",  # Ptest.msp.small
            cdb_content_classname="cdbpcs_project",
        )

    def test_schedule_without_project(self):
        """
        time schedule with empty project ID:

        - full access for owner and administrators
        - read access for public
        """
        self.assertAccess(
            ["read", "FULL ACCESS"],
            self._create_schedule(False),
            {
                self.__public__: ["read"],
                self.__owner__: ["read", "FULL ACCESS"],
                self.__admin__: ["read", "FULL ACCESS"],
            },
        )

    def test_schedule_with_project(self):
        """
        time schedule with primary project:

        - full access for owner, project managers and administrators
        - read access for public
        """
        self.assertAccess(
            ["read", "FULL ACCESS"],
            self._create_schedule(True),
            {
                self.__public__: ["read"],
                self.__owner__: ["read", "FULL ACCESS"],
                self.__admin__: ["read", "FULL ACCESS"],
                self.__manager__: ["read", "FULL ACCESS"],
            },
        )

    def test_content_without_project(self):
        """
        content of time schedule with empty project ID:

        - save, accept, create and delete for owner and administrators
        - read access for public
        """
        schedule = self._create_schedule(False)
        self.assertAccess(
            ["read", "save", "accept", "create", "delete"],
            self._create_content(schedule),
            {
                self.__public__: ["read"],
                self.__owner__: ["read", "save", "accept", "create", "delete"],
                self.__admin__: ["read", "save", "accept", "create", "delete"],
            },
        )

    def test_with_project(self):
        """
        content of time schedule with primary project:

        - save, accept, create and delete for owner, project managers and administrators
        - read access for public
        """
        schedule = self._create_schedule(True)
        self.assertAccess(
            ["read", "save", "accept", "create", "delete"],
            self._create_content(schedule),
            {
                self.__public__: ["read"],
                self.__owner__: ["read", "save", "accept", "create", "delete"],
                self.__admin__: ["read", "save", "accept", "create", "delete"],
                self.__manager__: ["read", "save", "accept", "create", "delete"],
            },
        )
