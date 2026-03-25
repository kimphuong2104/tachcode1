#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=broad-except

import unittest

import pytest

from cdb import testcase
from cdb.objects.operations import operation
from cs.pcs.resources.pools import ResourcePool

EXCEPTION_MSG = (
    "Der gewählte Resourcenpool ist ein bestehender Subpool"
    " und kann daher nicht als übergeordneter Resourcenpool gewählt werden."
)


@pytest.mark.integration
class TestResourcePoolsIntegration(testcase.RollbackTestCase):
    def _createEasyPool(self, pool_id, **kwargs):
        new_kwargs = {
            "cdb_object_id": f"oid{pool_id}",
            "name": f"pool{pool_id}",
            "parent_oid": "",
        }
        if kwargs:
            new_kwargs.update(**kwargs)
        return ResourcePool.Create(**new_kwargs)

    def _modifyPool(self, pool, **kwargs):
        operation("CDB_Modify", pool, **kwargs)

    def _copyPool(self, pool, **kwargs):
        return operation("CDB_Copy", pool, **kwargs)

    def _checkErrorMsg(self, e):
        error_msg = e.args[0] if e.args else None
        return error_msg == EXCEPTION_MSG

    def test_modifyParent_legal(self):
        pool1 = self._createEasyPool(1)
        pool2 = self._createEasyPool(2)

        self._modifyPool(pool1, parent_oid=pool2.cdb_object_id)
        self.assertEqual(pool1.parent_oid, "oid2")

    def test_copyyParent_legal(self):
        pool1 = self._createEasyPool(1)
        pool2 = self._createEasyPool(2)

        copied_pool = self._copyPool(pool1, parent_oid=pool2.cdb_object_id)
        self.assertEqual(copied_pool.parent_oid, "oid2")

    def test_modifyParent_nested_legal(self):
        pool1 = self._createEasyPool(1)
        pool2 = self._createEasyPool(2, parent_oid=pool1.cdb_object_id)
        pool3 = self._createEasyPool(3, parent_oid=pool2.cdb_object_id)
        pool4 = self._createEasyPool(4, parent_oid=pool3.cdb_object_id)
        pool5 = self._createEasyPool(5)

        self._modifyPool(pool5, parent_oid=pool4.cdb_object_id)
        self.assertEqual(pool5.parent_oid, "oid4")

    def test_copyyParent_nested_legal(self):
        pool1 = self._createEasyPool(1)
        pool2 = self._createEasyPool(2, parent_oid=pool1.cdb_object_id)
        pool3 = self._createEasyPool(3, parent_oid=pool2.cdb_object_id)
        pool4 = self._createEasyPool(4, parent_oid=pool3.cdb_object_id)
        pool5 = self._createEasyPool(5)

        copied_pool = self._copyPool(pool5, parent_oid=pool4.cdb_object_id)
        self.assertEqual(copied_pool.parent_oid, "oid4")

    def test_modifyParent_self(self):
        pool1 = self._createEasyPool(1)

        try:
            self._modifyPool(pool1, parent_oid=pool1.cdb_object_id)
        except Exception as e:
            self.assertTrue(self._checkErrorMsg(e))
        self.assertEqual(pool1.parent_oid, "")

    def test_copyParent_self(self):
        pool1 = self._createEasyPool(1)

        try:
            self._copyPool(pool1, parent_oid=pool1.cdb_object_id)
        except Exception as e:
            self.assertTrue(self._checkErrorMsg(e))

    def test_modifyParent_nested_illegal(self):
        pool1 = self._createEasyPool(1)
        pool2 = self._createEasyPool(2, parent_oid=pool1.cdb_object_id)
        pool3 = self._createEasyPool(3, parent_oid=pool2.cdb_object_id)
        pool4 = self._createEasyPool(4, parent_oid=pool3.cdb_object_id)

        try:
            self._modifyPool(pool1, parent_oid=pool4.cdb_object_id)
        except Exception as e:
            self.assertTrue(self._checkErrorMsg(e))

        self.assertEqual(pool1.parent_oid, "")
        self.assertEqual(pool4.parent_oid, pool3.cdb_object_id)

    def test_copyParent_nested_illegal(self):
        pool1 = self._createEasyPool(1)
        pool2 = self._createEasyPool(2, parent_oid=pool1.cdb_object_id)
        pool3 = self._createEasyPool(3, parent_oid=pool2.cdb_object_id)
        pool4 = self._createEasyPool(4, parent_oid=pool3.cdb_object_id)

        try:
            self._copyPool(pool1, parent_oid=pool4.cdb_object_id)
        except Exception as e:
            self.assertTrue(self._checkErrorMsg(e))


if __name__ == "__main__":
    unittest.main()
