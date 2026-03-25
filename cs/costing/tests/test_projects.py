#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

from __future__ import absolute_import

import datetime

import mock

from cdb import testcase, constants

from cs.costing.projects import copy_project_calucations


class TestProjects(testcase.RollbackTestCase):
    @mock.patch("cs.costing.projects.operations.system_args")
    @mock.patch("cs.costing.projects.operations.operation")
    def test_copy_project_calucations(self, operation, system_args):
        calc = mock.MagicMock()
        calc.template = 1
        calc.ToObjectHandle.return_value = "bar"
        tmpl_project = mock.MagicMock()
        PCOCalculations = mock.MagicMock()
        PCOCalculations.KeywordQuery.return_value = [calc]
        tmpl_project.PCOCalculations = PCOCalculations
        tmpl_project.template = 1
        new_project = mock.MagicMock()
        new_project.cdb_project_id = "foo"
        new_project.template = 0
        system_args.return_value = "foobar"

        copy_project_calucations(tmpl_project, new_project)

        PCOCalculations.KeywordQuery.assert_called_once_with(status=0)
        system_args.assert_called_once_with(no_copy_cost_sheets=1)
        operation.assert_called_once_with(
            constants.kOperationCopy,
            "bar",
            "foobar",
            **{
                "cdb_project_id": "foo",
                "template": 0,
                "para_year": str(datetime.date.today().year)
            }
        )
