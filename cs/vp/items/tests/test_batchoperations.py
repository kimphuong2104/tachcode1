# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tests batch operations for parts
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
import cs.vp.items.tests as common

from cdb.testcase import RollbackTestCase
from cdb.objects import operations

# Exported objects
__all__ = []


class TestStateChange(RollbackTestCase):
    def setUp(self):
        super(TestStateChange, self).setUp()

        self.part1 = common.generateItem()
        self.part2 = common.generateItem()
        self.part3 = common.generateItem()

    def test_op_executed_properly(self):
        """If one status change does not succed, only one error will be recorded"""

        self.part2.ChangeState(100)
        self.part2.ChangeState(200)

        batch_op = common.generateStateChangeBatchOperation(
            [self.part1, self.part2, self.part3],
            param1="100",
            param2="Review"
        )

        operations.operation(
            "cdbbop_operation_exec",
            batch_op
        )
        batch_op.Reload()

        self.assertEqual(batch_op.failures, 1)
        self.assertEqual(batch_op.successes, 2)
