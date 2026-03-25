#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Test Module test_pageframe

Tests the behaviour of the page_frame configuration
that resides in the class csweb_page_frame
"""

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest
from cdb.testcase import RollbackTestCase
from cdb import constants
from cdbwrapc import Operation
from cdb.platform.mom import entities, SimpleArguments
from cdb import ElementsError


class TestPageframe(RollbackTestCase):
    """Documentation for this test case"""
    def _run_create_op(self):
        """
        Returns a csweb_page_frame object handle with
        a valid config_location configuration.
        """
        op = Operation(constants.kOperationNew,
                       entities.CDBClassDef("csweb_page_frame"),
                       [])
        op.runAsTest([],
                     SimpleArguments(id="TESTPAGEFRAME",
                                     cdb_module_id="cs.web.components",
                                     config_location='"filename"'),
                     True)
        return op.getObjectResult()

    def test_create_page_frame_with_location(self):
        """
        Test create operation
        """
        self.assertTrue(self._run_create_op())

    def test_create_page_frame_with_component(self):
        """
        Test create operation
        """
        op = Operation(constants.kOperationNew,
                       entities.CDBClassDef("csweb_page_frame"),
                       [])
        op.runAsTest([],
                     SimpleArguments(id="TESTPAGEFRAME",
                                     cdb_module_id="cs.web.components",
                                     config_component='"component"'),
                     True)
        self.assertTrue(op.getObjectResult())

    def test_create_fails_without_config(self):
        """
        Test that the creation fails if neither a
        location nor a component is configured
        """
        with self.assertRaises(ElementsError):
            op = Operation(constants.kOperationNew,
                           entities.CDBClassDef("csweb_page_frame"),
                           [])
            op.runAsTest([],
                         SimpleArguments(id="TESTPAGEFRAME",
                                         cdb_module_id="cs.web.components"),
                         True)

    def test_create_fails_with_multiple_config(self):
        """
        Test that the creation fails if a
        location and a component is configured
        """
        with self.assertRaises(ElementsError):
            op = Operation(constants.kOperationNew,
                           entities.CDBClassDef("csweb_page_frame"),
                           [])
            op.runAsTest([],
                         SimpleArguments(id="TESTPAGEFRAME",
                                         cdb_module_id="cs.web.components",
                                         config_component='"component"',
                                         config_location='"filename"'),
                         True)

    def test_modify_page_frame(self):
        """
        Test modify operation
        """
        obj = self._run_create_op()
        op = Operation(constants.kOperationModify,
                       obj,
                       [])
        op.runAsTest([],
                     SimpleArguments(id="TESTPAGEFRAME",
                                     cdb_module_id="cs.web.components",
                                     config_component="",
                                     config_location='"filename"'),
                     True)
        self.assertTrue(op.getObjectResult())

    def test_modify_fails_without_config(self):
        """
        Test that the modification fails if neither a
        location nor a component is configured
        """
        obj = self._run_create_op()
        op = Operation(constants.kOperationModify,
                       obj,
                       [])
        with self.assertRaises(ElementsError):
            op.runAsTest([],
                         SimpleArguments(config_component="",
                                         config_location=""),
                         True)

    def test_modify_fails_without_multiple_config(self):
        """
        Test if a modification fails if
        location and a component is configured
        """
        obj = self._run_create_op()
        op = Operation(constants.kOperationModify,
                       obj,
                       [])
        with self.assertRaises(ElementsError):
            op.runAsTest([],
                         SimpleArguments(config_component='"component"',
                                         config_location='"filename"'),
                         True)

    def test_delete(self):
        """
        Test if deletion of a frame works
        """
        obj = self._run_create_op()
        op = Operation(constants.kOperationDelete,
                       obj,
                       [])
        op.runAsTest([], [], True)

    def test_delete_referenced_fails(self):
        """
        Test if the deletion of a referenced frame works
        """
        from cs.web.components.configurable_ui import Csweb_page_config_app
        obj = self._run_create_op()
        wp = Csweb_page_config_app.Create(page_id="TEST",
                                          pageframe_id=obj["id"])
        op = Operation(constants.kOperationDelete,
                       obj,
                       [])
        with self.assertRaises(ElementsError):
            op.runAsTest([], [], True)

# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
