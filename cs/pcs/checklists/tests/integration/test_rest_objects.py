#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import pytest
from cdb.validationkit.op import operation

from cs.pcs.checklists.checklist_status import (
    ChecklistItemStatusProtocol,
    ChecklistStatusProtocol,
)
from cs.pcs.checklists.tests.integration import util
from cs.pcs.tests.integration.rest_helpers import RESTSmokeTestBase

PROJECT_ID = "cl_rest_test"


@pytest.mark.dependency(name="integration", depends=["cs.pcs.checklists"])
class ChecklistRestObjects(RESTSmokeTestBase):
    def _create_project(self):
        project = util.create_project(PROJECT_ID, "")
        project.status = project.EXECUTION.status
        return project

    def _create_checklist(self, project):
        return util.create_checklist(project)

    def create_protocol_data(self):
        project = self._create_project()
        checklist = self._create_checklist(project)
        cl_item = util.create_checklist_item(
            util.get_user("caddok"), project, checklist, cl_item_id="0"
        )
        operation(
            "cdbpcs_clitem_rating",
            cl_item,
            preset={"rating_id": "gruen"},
        )
        return project, checklist, cl_item

    def create_ruleRef_data(self):
        project = self._create_project()
        checklist = self._create_checklist(project)
        rule_reference = util.create_rule_reference(
            project, checklist, "cdbpcs: TimeSheet: Active Checklists"
        )

        return project, checklist, rule_reference

    # only GET
    def test_checklisttype(self):
        self.rest_get_only("checklist_types", "Checklist", "cdbpcs_cl_types")

    # only GET
    def test_Weighting(self):
        self.rest_get_only("rating_weighting", "Grades@1", "cdbpcs_rat_wght")

    # only GET
    def test_RatingSchema(self):
        self.rest_get_only("rating_schema", "Grades", "cdbpcs_rat_def")

    # only GET
    def test_ChecklistStatusProtocol(self):
        self.create_protocol_data()
        self.rest_get_only(
            "checklist_protocol",
            self._build_rest_key(
                [ChecklistStatusProtocol.Query()[0]["cdbprot_sortable_id"]]
            ),
            "cdbpcs_cl_prot",
        )

    # only GET
    def test_ChecklistItem(self):
        self.rest_get_only(
            "checklist_item", "1@7035@ptest.cust.middle", "cdbpcs_cl_item"
        )

    # only GET
    def test_ChecklistItemStatusProtocol(self):
        self.create_protocol_data()
        self.rest_get_only(
            "checklistitem_protocol",
            self._build_rest_key(
                [ChecklistItemStatusProtocol.Query()[0]["cdbprot_sortable_id"]]
            ),
            "cdbpcs_cli_prot",
        )

    # only GET
    def test_RuleReference(self):
        _, _, rr = self.create_ruleRef_data()
        self.rest_get_only(
            "deliverable_rule",
            self._build_rest_key([rr.cdb_project_id, rr.checklist_id, rr.rule_id]),
            "cdbpcs_deliv2rule",
        )

    # All methods
    def test_checklist(self):
        self._create_project()
        self.complete_rest(
            "checklist",
            "cdbpcs_checklist",
            {"cdb_project_id": PROJECT_ID},
            ["cdb_project_id", "checklist_id"],
            {"category": "Foo"},
        )

    # only GET
    def test_ChecklistCategory(self):
        self.rest_get_only("checklist_category", "Fertigung", "cdbpcs_cl_cat")

    # only GET
    def test_RatingAssignment(self):
        self.rest_get_only("rating_assignment", "Checklist@Grades", "cdbpcs_rat_asgn")

    # only GET
    def test_RatingValue(self):
        self.rest_get_only("rating_value", "Grades@clear", "cdbpcs_rat_val")


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
