#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import datetime

import pytest
from cdb import auth, testcase
from cdb.cdbuuid import create_uuid
from cdb.validationkit.SwitchRoles import run_with_project_roles, run_with_roles
from cs.taskboard.objects import Board

from cs.pcs.projects.tests import common


def create_board_for_object(obj):
    board_templates = Board.KeywordQuery(
        board_type="sprint_board", is_template=True, available=True
    )
    assert len(board_templates) == 1, "Team board template cannot be determined."

    tb_uuid = create_uuid()
    values = {
        "cdb_object_id": tb_uuid,
        "title": tb_uuid,
        "context_object_id": obj.cdb_object_id,
        "start_date": datetime.date(2020, 1, 1),
        "is_template": False,
    }
    values.update(Board.MakeChangeControlAttributes())
    # The test user should not be the owner of the board.
    values.update({"cdb_cpersno": "vendorsupport", "cdb_mpersno": "vendorsupport"})

    sprint_board = board_templates[0].copyBoard(**values)
    assert isinstance(sprint_board, Board), "Project board has not been created:"
    sprint_board.setupBoard()
    return sprint_board


@pytest.mark.integration
class SprintBoardAccessTestCase(testcase.RollbackTestCase):
    def setUp(self):
        super().setUp()
        self.project = common.generate_project()
        self.task = common.generate_project_task(self.project)
        self.project_board = create_board_for_object(self.project)
        self.task_board = create_board_for_object(self.task)

    @run_with_roles([])
    def test_access_as_nobody(self):
        self.assertFalse(self.project_board.CheckAccess("read", auth.persno))
        self.assertFalse(self.task_board.CheckAccess("read", auth.persno))

    @run_with_roles(["public"])
    def test_access_as_public(self):
        self.assertTrue(self.project_board.CheckAccess("read", auth.persno))
        self.assertTrue(self.task_board.CheckAccess("read", auth.persno))

    @run_with_roles(["public", "Team Board Manager"])
    def test_access_as_team_board_manager(self):
        self.assertTrue(self.project_board.CheckAccess("read", auth.persno))
        self.assertTrue(self.task_board.CheckAccess("read", auth.persno))

    @run_with_roles(["public", "Task Board Administrator"])
    def test_access_as_team_board_administrator(self):
        self.assertTrue(self.project_board.CheckAccess("read", auth.persno))
        self.assertTrue(self.task_board.CheckAccess("read", auth.persno))

    def test_access_as_projektmitglied(self):
        @run_with_roles(["public"])
        @run_with_project_roles(self.project, ["Projektmitglied"])
        def check_access():
            self.assertTrue(self.project_board.CheckAccess("read", auth.persno))
            self.assertTrue(self.task_board.CheckAccess("read", auth.persno))

        check_access()

    def test_access_as_projektleiter(self):
        @run_with_roles(["public"])
        @run_with_project_roles(self.project, ["Projektleiter"])
        def check_access():
            self.assertTrue(self.project_board.CheckAccess("read", auth.persno))
            self.assertTrue(self.task_board.CheckAccess("read", auth.persno))

        check_access()
