#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access,no-value-for-parameter

import unittest

import mock
import pytest
from cdb import sqlapi, testcase
from cdbwrapc import CDBClassDef

from cs.pcs.projects.catalogs import CatalogResponsibleData
from cs.pcs.projects.tests import common


@pytest.mark.integration
class TestCatalogResponsibleData(testcase.RollbackTestCase):
    maxDiff = None
    PROJECT_ID = "myProjectId"

    def setUp(self):
        super().setUp()
        sqlapi.SQLdelete("FROM angestellter WHERE personalnummer != 'caddok'")
        sqlapi.SQLdelete("FROM cdbpcs_subject WHERE 1=1")
        self.project = common.generate_project(cdb_project_id=self.PROJECT_ID)

    @mock.patch("cs.pcs.projects.catalogs.CatalogResponsible")
    @mock.patch.object(CatalogResponsibleData, "getSQLCondition")
    def getData(self, project_id, getSQLCondition, catalog):
        # a little convoluted, but cdbwrapc expects some kernel-internal setup
        catalog.getTabularDataDefName.return_value = "cdbwf_resp_brows"
        catalog.getClassDefSearchedOn.return_value = CDBClassDef("cdbwf_resp_browser")
        crd = CatalogResponsibleData(project_id, catalog)
        getSQLCondition.return_value = f"cdb_project_id = '{project_id}'"
        crd._initData()
        return crd.data

    def expect_entries(self, expected, project_id=None):
        if project_id is None:
            project_id = self.PROJECT_ID

        result = [
            (x["subject_id"], x["subject_type"], x["cdb_project_id"])
            for x in self.getData(project_id)
        ]
        self.assertEqual(result, expected)

    def test_initData_only_admin(self):
        self.expect_entries(
            [
                ("caddok", "Person", self.PROJECT_ID),
                ("Projektleiter", "PCS Role", self.PROJECT_ID),
                ("Projektmitglied", "PCS Role", self.PROJECT_ID),
            ]
        )

    def test_initData_multiple_users(self):
        u0 = common.generate_user("test_user_0")
        common.assign_person_to_project(
            "Projektmitglied", self.project, u0.personalnummer
        )
        u1 = common.generate_user("test_user_1")
        common.assign_person_to_project(
            "Projektmitglied", self.project, u1.personalnummer
        )

        self.expect_entries(
            [
                ("caddok", "Person", self.PROJECT_ID),
                (u0.personalnummer, "Person", self.PROJECT_ID),
                (u1.personalnummer, "Person", self.PROJECT_ID),
                ("Projektleiter", "PCS Role", self.PROJECT_ID),
                ("Projektmitglied", "PCS Role", self.PROJECT_ID),
            ]
        )

    def test_initData_common_role(self):
        r = common.generate_common_role("test_role_0")
        u0 = common.generate_user("test_user_0")
        u1 = common.generate_user("test_user_1")
        common.assign_user_common_role(u0, r.role_id)
        common.assign_user_common_role(u1, r.role_id)
        common.assign_common_role_to_project(
            "Projektmitglied", r.role_id, self.PROJECT_ID
        )

        self.expect_entries(
            [
                ("caddok", "Person", self.PROJECT_ID),
                (u0.personalnummer, "Person", self.PROJECT_ID),
                (u1.personalnummer, "Person", self.PROJECT_ID),
                ("Projektleiter", "PCS Role", self.PROJECT_ID),
                ("Projektmitglied", "PCS Role", self.PROJECT_ID),
                (r.role_id, "Common Role", self.PROJECT_ID),
            ]
        )

    def test_initData_project_role_0(self):
        r = common.generate_project_role(self.project, "test_role_0")
        common.generate_project_role_def(r.role_id)
        u0 = common.generate_user("test_user_0")
        u1 = common.generate_user("test_user_1")
        common.assign_user_project_role(u0, self.project, r.role_id)
        common.assign_user_project_role(u1, self.project, r.role_id)

        self.expect_entries(
            [
                ("caddok", "Person", self.PROJECT_ID),
                (u0.personalnummer, "Person", self.PROJECT_ID),
                (u1.personalnummer, "Person", self.PROJECT_ID),
                ("Projektleiter", "PCS Role", self.PROJECT_ID),
                ("Projektmitglied", "PCS Role", self.PROJECT_ID),
                (r.role_id, "PCS Role", self.PROJECT_ID),
            ]
        )

    # E067623 NUN TEST DER DEN ANDEREN FALL ABDECKT
    # Project Rolle X anlegen
    # X unter zB Projektmitglied zuordnen
    # Allgemeine Rolle Y mit gleichem Namen wie X anlegen
    # Jeder Rolle >= 1 User zu weisen
    # Katalog soll nur den User aus X anzeigen!
    def test_initData_project_role(self):
        r = common.generate_project_role(self.project, "test_role_0")
        common.generate_project_role_def(r.role_id)
        common.assign_project_role_to_project_role(
            role_id="Projektmitglied",
            cdb_project_id=self.PROJECT_ID,
            subject_id=r.role_id,
            subject_id2=self.PROJECT_ID,
        )
        common.generate_common_role(r.role_id)
        u0 = common.generate_user("test_user_0")
        u1 = common.generate_user("test_user_1")
        common.assign_user_project_role(u0, self.project, r.role_id)
        common.assign_user_common_role(u1, r.role_id)

        self.expect_entries(
            [
                ("caddok", "Person", self.PROJECT_ID),
                (u0.personalnummer, "Person", self.PROJECT_ID),
                ("Projektleiter", "PCS Role", self.PROJECT_ID),
                ("Projektmitglied", "PCS Role", self.PROJECT_ID),
                (r.role_id, "PCS Role", self.PROJECT_ID),
            ]
        )

    def test_initData_no_project_id(self):
        "search without pid: include pcs role defs and common roles used in projects"
        r = common.generate_common_role("test_role_0")
        common.assign_common_role_to_project(
            "Projektmitglied", r.role_id, self.PROJECT_ID
        )

        self.expect_entries(
            [
                ("caddok", "Person", ""),
                ("Project Cost Management", "PCS Role", ""),
                ("Projektassistent", "PCS Role", ""),
                ("Projektleiter", "PCS Role", ""),
                ("Projektmitglied", "PCS Role", ""),
                ("test_role_0", "Common Role", ""),
            ],
            "",
        )


if __name__ == "__main__":
    unittest.main()
