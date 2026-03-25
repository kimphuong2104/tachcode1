#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging
from contextlib import contextmanager

import mock
import pytest
from cdb import testcase

from cs.pcs.projects import Project


def setup_module():
    testcase.run_level_setup()


@contextmanager
def logging_disabled():
    old_log_level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(old_log_level)


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class SchedulingStability(testcase.RollbackTestCase):
    @mock.patch("cs.pcs.projects.tasks_efforts.aggregate_changes")
    @mock.patch("cdb.sqlapi.SQLupdate")
    def test_scheduling_stability(self, SQLupdate, _):
        "scheduling is stable (a freshly-scheduled project doesn't change)"
        p = Project.ByKeys("ptest.cust.big")
        with logging_disabled():
            p.recalculate()
        # note: if this test fails, this may indicate a behavioral change in scheduling
        # we may have to recalculate all test fixture projects and generate perf projects again
        SQLupdate.assert_not_called()
