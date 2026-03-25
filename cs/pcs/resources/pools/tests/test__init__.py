#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import mock
import pytest

from cdb import ue
from cs.pcs.resources.pools import ResourcePool


@pytest.mark.unit
class TestResourcePool(unittest.TestCase):
    def test_validate_parent_pool_sameParent(self):
        # parent pool is not changed
        pool = mock.MagicMock(spec=ResourcePool, parent_oid="a")
        ctx = mock.MagicMock()
        ctx.dialog = {"parent_oid": "a"}

        self.assertEqual(ResourcePool.validate_parent_pool(pool, ctx), None)

    def test_validate_parent_pool_changedParent_no_recursion(self):
        # parent pool is changed, but new parent pool is not in subpool structure of pool
        pool = mock.MagicMock(spec=ResourcePool, parent_oid="a", AllResourcePools=[])
        ctx = mock.MagicMock()
        ctx.dialog = {"parent_oid": "b"}

        self.assertEqual(ResourcePool.validate_parent_pool(pool, ctx), None)

    @mock.patch("cdb.util.CDBMsg", autospec=True)
    def test_validate_parent_pool_changedParent_recursion(self, CDBMsg):
        # parent pool is changed, but new parent pool is in subpool structure of pool
        pool = mock.MagicMock(
            spec=ResourcePool,
            parent_oid="a",
            AllResourcePools=[mock.MagicMock(spec=ResourcePool, cdb_object_id="b")],
        )
        ctx = mock.MagicMock()
        ctx.dialog = {"parent_oid": "b"}

        with self.assertRaises(ue.Exception):
            self.assertEqual(ResourcePool.validate_parent_pool(pool, ctx), None)
        CDBMsg.assert_called_once_with(CDBMsg.kFatal, "cdbpcs_resource_pool_recursive")


if __name__ == "__main__":
    unittest.main()
