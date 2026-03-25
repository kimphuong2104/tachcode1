#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import unittest
from collections import defaultdict

import cdbwrapc
import pytest
from cdb import ElementsError, testcase, util
from cdb.constants import kOperationSearch
from cdb.platform.gui import Mask
from cdb.platform.mom.operations import OperationConfig
from cdb.util import update_role_table
from cdb.validationkit import generateUser
from cdb.validationkit.SwitchRoles import run_with_project_roles, run_with_roles

from cs.pcs import projects
from cs.pcs.projects.tests import common


def assert_mask_fields(objects_cls, operation, required_fields):
    """
    :param objects_cls: Class to check operation masks for
    :type objects_cls: cdb.objects.Object

    :param operation: Operation name to check masks for
    :type operation: str

    :param required_fields: List or set of attribute names that are required
        in masks by code to work as intended.
    :type required_fields: iterable

    .. error ::

        If no mask is configured for the given values, the function will currently not raise an error.

    .. warning ::

        This function simplifies assertions regarding mask compositions with
        mask registers for multiple overlapping roles. The following is an
        example which would not work as expected:

        mask composition for "public"
            mask register for "public"
                mask for "public"
                mask for Common Role "Administrator" <- this mask is ignored
            mask register for "public"
                mask for "public"

    :raises ValueError: if any ``required_fields`` are missing in any masks
        for given ``objects_cls`` and ``operation``.

    :raises ValueError: if any mask with unknown ``cdb_classname`` value is
        found.
    """
    required_fields = set(required_fields)
    missing = defaultdict(set)  # attribut: set([(mask_name, role_id), ...])
    op = OperationConfig.ByKeys(name=operation, classname=objects_cls._getClassname())

    def check_mask(mask):
        for attr in required_fields - mask.Attributes.attribut:
            missing[attr].add((mask.name, mask.role_id))

    def check_composition(comp):
        included_fields = set()

        for reg in comp.Registers:
            # attribute must be included in any _one_ register
            # WARNING: This does not handle masks for other roles
            for reg_mask in reg.Masks.KeywordQuery(role_id=reg.mask_role_id):
                included_fields.update(reg_mask.Attributes.attribut)
                if not required_fields - included_fields:
                    return

        for attr in required_fields - included_fields:
            missing[attr].add((comp.name, comp.role_id))

    def check_mask_or_comp(mask_or_comp):
        # vanilla mask
        if mask.cdb_classname == "cdb_maskenzuordnung":
            check_mask(mask)

        # mask composition -> n registers -> m masks
        elif mask.cdb_classname == "cdb_mask_comp":
            check_composition(mask)

        # corrupted data, unknown cdb_classname
        else:
            raise ValueError("neither mask nor mask composition")

    # directly assigned masks
    for mask in op.Masks:
        check_mask_or_comp(mask)

    # override for Web UI
    if op.mask_name_webui:
        for owner in op.Owners:
            for mask in Mask.KeywordQuery(
                name=op.mask_name_webui, role_id=owner.role_id
            ):
                check_mask_or_comp(mask)

    if missing:
        missing_strs = [
            f"'{attr}' is missing in {masks}" for attr, masks in missing.items()
        ]
        raise ValueError(
            "some masks are missing attributes:\n\t{}".format("\n\t".join(missing_strs))
        )


@pytest.mark.integration
class ProjectIntegrationTestCase(testcase.RollbackTestCase):
    @pytest.mark.dependency(depends=["cs.pcs.issues"])
    def test_set_frozen_in_event_map(self):
        "Project event map contains 'set_frozen'"
        self.assertIn(
            "set_frozen", projects.Project.GetEventMap()[(("create", "copy"), "pre")]
        )

    @pytest.mark.dependency(depends=["cs.pcs.issues"])
    def test_derived_from_WithFrozen(self):
        "Project is derived from WithFrozen"
        self.assertIn(projects.WithFrozen, projects.Project.mro())

    @pytest.mark.dependency(depends=["configuration"])
    def test_on_modify_post_mask(self):
        assert_mask_fields(projects.Project, "CDB_Modify", set(["parent_project"]))


class ProjectRoleIntegrationTestCase(testcase.RollbackTestCase):

    PERSON = "test_user_1"
    ROLE_ID = "Projektmitglied"

    def prepare_project(self, project_status=0):
        p = common.generate_project(status=project_status)
        common.generate_user(self.PERSON)
        common.assign_person_to_project(self.ROLE_ID, p, self.PERSON)
        util.reload_cache(util.kCGRoleCaches, util.kLocalReload)
        return p

    def change_project(self, project_status, **rights):
        p = self.prepare_project(project_status)
        for name, right in rights.items():
            check = p.CheckAccess(name, persno=self.PERSON)
            self.assertEqual(
                right,
                check,
                f"Access right '{name}': {check} (should be {right})",
            )

    def change_project_role(self, **rights):
        p = self.prepare_project()
        r = common.generate_project_role(p, "Testrole")
        for name, right in rights.items():
            check = r.CheckAccess(name, persno=self.PERSON)
            self.assertEqual(
                right,
                check,
                f"Access right '{name}': {check} (should be {right})",
            )

    def allocate_role(self, fails, assign_user=True):
        p = self.prepare_project(0)
        r = common.generate_project_role(p, "Testrole")
        common.generate_user("test_user_allocate")

        @run_with_roles(["public"])
        @run_with_project_roles(p, [self.ROLE_ID])
        def allocate_role_with_rights():
            if fails:
                with self.assertRaises(ElementsError):
                    common.assign_person_to_project("Testrole", p, "test_user_allocate")
            else:
                pr = common.assign_person_to_project(
                    "Testrole", p, "test_user_allocate"
                )
                self.assertIsNotNone(pr, "Role not assigned !")

        if assign_user:
            allocate_role_with_rights()
        return p, r

    def allocate_role_to_task(self, status, check_type, assign_user=True, fails=False):
        p, r = self.allocate_role(fails, assign_user)
        t = common.generate_project_task(p)

        @run_with_roles(["public"])
        @run_with_project_roles(p, [self.ROLE_ID])
        def allocate_role_with_rights():
            common.assign_role_to_task(t, "Testrole")

        @run_with_roles(["public"])
        @run_with_project_roles(p, [self.ROLE_ID])
        def changeState():
            p.ChangeState(status)

        allocate_role_with_rights()
        if status:
            changeState()
        r.Reload()
        team_assigned = r.team_assigned if r else 0
        team_needed = r.team_needed if r else 0
        if check_type == "green":
            assert team_assigned == 1 and team_needed in (
                1,
                2,
            ), "The project role is not green"
        elif check_type == "yellow":
            assert (
                team_assigned == 0 and team_needed == 1
            ), "The project role is not yellow"
        elif check_type == "red":
            assert (
                team_assigned == 0 and team_needed == 2
            ), "The project role is not red"
        else:
            assert team_needed == 0, "The project role is not empty"


@pytest.mark.integration
class ProjectManagerTestCase(ProjectRoleIntegrationTestCase):

    ROLE_ID = "Projektleiter"

    def test_change_project_01(self):
        "Project access rights: " "project manager changes new project"
        self.change_project(0, read=True, delete=True, save=True)

    def test_change_project_02(self):
        "Project access rights: " "project manager changes execution project"
        self.change_project(50, read=True, delete=False, save=True)

    def test_change_project_03(self):
        "Project access rights: " "project manager changes frozen project"
        self.change_project(60, read=True, delete=False, save=True)

    def test_change_project_04(self):
        "Project access rights: " "project manager changes discarded project"
        self.change_project(180, read=True, delete=False, save=True)

    def test_change_project_05(self):
        "Project access rights: " "project manager changes closed project"
        self.change_project(200, read=True, delete=False, save=False)

    def test_change_project_role(self):
        self.change_project_role(create=True, delete=True)

    def test_allocate_project_role(self):
        self.allocate_role(False)

    def test_allocate_role_to_task_green(self):
        self.allocate_role_to_task(50, "green")

    def test_allocate_role_to_task_yellow(self):
        self.allocate_role_to_task(0, "yellow", assign_user=False)

    def test_allocate_role_to_task_red(self):
        self.allocate_role_to_task(50, "red", assign_user=False)


@pytest.mark.integration
class ProjectMemberTestCase(ProjectRoleIntegrationTestCase):

    ROLE_ID = "Projektmitglied"

    def test_change_project_01(self):
        "Project access rights: " "project member changes new project"
        self.change_project(0, read=True, delete=False, save=False)

    def test_change_project_02(self):
        "Project access rights: " "project member changes execution project"
        self.change_project(50, read=True, delete=False, save=False)

    def test_change_project_03(self):
        "Project access rights: " "project member changes frozen project"
        self.change_project(60, read=True, delete=False, save=False)

    def test_change_project_04(self):
        "Project access rights: " "project member changes discarded project"
        self.change_project(180, read=True, delete=False, save=False)

    def test_change_project_05(self):
        "Project access rights: " "project member changes closed project"
        self.change_project(200, read=True, delete=False, save=False)

    def test_change_project_role(self):
        self.change_project_role(create=False, delete=False)


@pytest.mark.dependency(name="integration", depends=["configuration"])
class SearchForProjectRoles(testcase.RollbackTestCase):
    ROLE_ID = "Test Project Role"
    PERSNO = "Test Person"

    def setUp(self):
        super().setUp()

        def create_project(pid, bid):
            return projects.Project.Create(
                cdb_project_id=pid,
                ce_baseline_id=bid,
                project_manager="caddok",
            )

        # create test project without role
        self.without_role = create_project("TEST_WITHOUT_ROLE", "")

        # create test project with role, but no person assigned to it
        self.with_role = create_project("TEST_WITH_ROLE", "")
        projects.Role.Create(
            cdb_project_id=self.with_role.cdb_project_id,
            role_id=self.ROLE_ID,
        )
        projects.CommonRoleAssignment.Create(
            cdb_project_id=self.with_role.cdb_project_id,
            role_id=self.ROLE_ID,
            subject_type="Common Role",
            subject_id="Administrator",
            subject_id2="",
        )

        # create test project with role and person assigned to it
        self.with_role_and_owner = create_project("TEST_WITH_OWNER", "")
        projects.Role.Create(
            cdb_project_id=self.with_role_and_owner.cdb_project_id,
            role_id=self.ROLE_ID,
        )
        generateUser(self.PERSNO, is_system_account=0)
        projects.PersonAssignment.Create(
            cdb_project_id=self.with_role_and_owner.cdb_project_id,
            role_id=self.ROLE_ID,
            subject_type="Person",
            subject_id=self.PERSNO,
            subject_id2="",
        )

        # reloading role caches so test user and role ownership are "known"
        update_role_table(self.PERSNO)

    def _run_search_op(self, role=None, owner=None):
        query_args = [cdbwrapc.SimpleArgument("cdb_project_id", "TEST_*")]

        if role:
            query_args.append(cdbwrapc.SimpleArgument("projectcontext_role", role))

        if owner:
            query_args.append(cdbwrapc.SimpleArgument("projectcontext_persno", owner))

        op = cdbwrapc.Operation(
            kOperationSearch,
            "cdbpcs_project",
            query_args,
        )
        op.run()
        result = op.getQueryResult().as_table()

        return [result.getRowData(i) for i in range(result.getNumberOfRows())]

    def _assert_search_result(self, result, expected):
        self.assertEqual(
            len(result),
            expected,
            f"found {len(result)} projects, expected {expected}: {result}",
        )

    def test_search_for_role(self):
        "search for role only -> projects using that role"
        result = self._run_search_op(role=self.ROLE_ID)
        self._assert_search_result(result, 2)

    def test_search_for_owner(self):
        "search for owner only -> projects where owner has any role"
        result = self._run_search_op(owner=self.PERSNO)
        self._assert_search_result(result, 1)

    def test_search_for_role_and_owner(self):
        "search for role + owner -> projects where owner has that role"
        result = self._run_search_op(role=self.ROLE_ID, owner=self.PERSNO)
        self._assert_search_result(result, 1)


@pytest.mark.integration
class ProjectTeamIntegrationTestCase(testcase.RollbackTestCase):

    PERSON = "test_person"

    def check_project(self, role_id, **rights):
        p = common.generate_project(status=0)
        common.generate_user(self.PERSON)
        common.assign_person_to_project(role_id, p, self.PERSON)
        util.reload_cache(util.kCGRoleCaches, util.kLocalReload)
        for name, right in rights.items():
            check = p.CheckAccess(name, persno=self.PERSON)
            self.assertEqual(
                right,
                check,
                f"Access right '{name}': {check} (should be {right})",
            )

    def test_change_team_member_01(self):
        "Project team Member access rights: on team member objects"
        self.check_project("Projektmitglied", read=True, delete=False, save=False)

    def test_change_team_member_02(self):
        "Project team manager access rights: on team member objects"
        self.check_project("Projektleiter", read=True, delete=True, save=True)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
