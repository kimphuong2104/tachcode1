#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import sqlapi, testcase
from cs.taskmanager.updates import v15_6_0_8


@testcase.rollback
def test_ResponsibleCell():
    v15_6_0_8.ResponsibleCell().run()
    assert (
        sqlapi.RecordSet2("cs_tasks_column", "name = 'cs_tasks_col_responsible' ")[
            0
        ].plugin_component
        == "cs-tasks-cells-ResponsibleCell"
    )


@testcase.rollback
def test_ResponsibleCell_customized():
    sqlapi.SQLupdate(
        "cs_tasks_column SET plugin_component = 'foo' WHERE name = 'cs_tasks_col_responsible'"
    )
    v15_6_0_8.ResponsibleCell().run()
    assert (
        sqlapi.RecordSet2("cs_tasks_column", "name = 'cs_tasks_col_responsible'")[
            0
        ].plugin_component
        == "foo"
    )
