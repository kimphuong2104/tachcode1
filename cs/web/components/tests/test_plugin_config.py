#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Test Module test_plugin_config

This is the documentation for the tests.
"""

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest


import unittest
from cdb.testcase import RollbackTestCase
from cdb import constants
from cdbwrapc import Operation
from cdb.platform.mom import entities, SimpleArguments
from cdb import ElementsError
from cs.web.components import plugin_config


class TestPluginConfigCallback(RollbackTestCase):
    """
    Tests that uses the `cs.webtest.plugin_test.WebUIPluginCallbackTest`
    callback for the plugin ``csweb-plugin-test`` to ensure that the base
    functionality and the special functionality of the configuration works
    """
    def setUp(self):
        try:
            from cs.webtest import plugin_test
        except RuntimeError:
            raise unittest.SkipTest("this test needs cs.webtest.plugin_test")
        super(TestPluginConfigCallback, self).setUp()

    def test_check_value_call(self):
        """
        Test if the callback funktion "check_value" is called. The test
        plugin refuses a component with the value ``error``.
        """
        op = Operation(constants.kOperationNew,
                       entities.CDBClassDef("csweb_plugin_config"),
                       [])
        with self.assertRaises(ElementsError):
            op.runAsTest([],
                         SimpleArguments(plugin_id="csweb-plugin-test",
                                         discriminator="discriminator",
                                         component="error",
                                         cdb_module_id="cs.webtest"),
                         True)

    def test_plugin_config_values(self):
        """
        Test if the plugin configuration values are there
        """
        found = False
        pcs = plugin_config.Csweb_plugin.get_plugin_config("csweb-plugin-test")
        for pc in pcs:
            if pc["discriminator"] == "discriminator1":
                self.assertEqual(pc["component"], "react_component")
                self.assertEqual(pc["setup"], "setup_function")
                library_names = [lib[0] for lib in pc["libraries"]]
                self.assertTrue("cs-web-components-pdf" in library_names)
                self.assertTrue("cs-webtest-library" in library_names)
                self.assertTrue("cs-webtest-library3" in library_names)
                self.assertTrue("cs-webtest-library4" in library_names)
                self.assertTrue("cs-webtest-library5" in library_names)
                self.assertEquals(len(library_names), 5)
                found = True
                break
        self.assertTrue(found, "Configuration not found")

    def test_plugin_config_libraries(self):
        """
        Test if the plugin libraries are there
        """
        found = False
        pcs = plugin_config.Csweb_plugin.get_plugin_config("csweb-plugin-test")
        for pc in pcs:
            if pc["discriminator"] == "discriminator02":
                library_names = [lib[0] for lib in pc["libraries"]]
                self.assertTrue("cs-webtest-library" in library_names)
                self.assertTrue("cs-webtest-library2" in library_names)
                self.assertTrue("cs-webtest-library3" in library_names)
                self.assertTrue("cs-webtest-library4" in library_names)
                self.assertTrue("cs-webtest-library5" in library_names)
                self.assertEquals(len(library_names), 5)
                found = True
                break
        self.assertTrue(found, "Libraries not found")

    def test_plugin_config_order(self):
        """
        The plugins should be delivered according to their priority.
        """
        pcs = plugin_config.Csweb_plugin.get_plugin_config("csweb-plugin-test")
        self.assertEqual(pcs[0]["discriminator"], "discriminator02",
                         "Priority does not affect the plugin order")
        cfg = plugin_config.Csweb_plugin_config.ByKeys("csweb-plugin-test",
                                                       "discriminator02")
        # Change the priority to 0 - this should move the config to the end of
        # the list
        cfg.Update(priority=0)
        plugin_config.Csweb_plugin.clear_cache()
        pcs = plugin_config.Csweb_plugin.get_plugin_config("csweb-plugin-test")
        # -2 because the plugin appends a configuration for an other test
        self.assertEqual(pcs[-2]["discriminator"], "discriminator02",
                         "Priority does not affect the plugin order:%s")

    def test_adapt_config(self):
        """
        The test plugin adds a configuration at the end. Lets have
        a look if this works
        """
        pcs = plugin_config.Csweb_plugin.get_plugin_config("csweb-plugin-test")
        self.assertEqual(pcs[-1], {"discriminator": "added_by_plugin",
                                   "added_by_plugin": True})

    def test_generate_config(self):
        """
        The test plugin adds a hint to each configuration
        """
        pcs = plugin_config.Csweb_plugin.get_plugin_config("csweb-plugin-test")
        for pc in pcs:
            self.assertTrue("added_by_plugin" in pc)


class TestClasstilesmallPluginConfig(RollbackTestCase):
    """
    Test specific things for the class-tile-small plugin
    configuration
    """
    def _run_create_op(self):
        """
        Returns a csweb_plugin_config object handle.
        """
        op = Operation(constants.kOperationNew,
                       entities.CDBClassDef("csweb_plugin_config"),
                       [])
        op.runAsTest([],
                     SimpleArguments(plugin_id="class-tile-small",
                                     discriminator="cdbdd_field",
                                     component="classtilesmall",
                                     cdb_module_id="cs.web.components"),
                     True)
        return op.getObjectResult()

    def test_create_plugin_config(self):
        """
        Test create operation
        """
        self.assertTrue(self._run_create_op())

    def test_create_fails_with_invalid_classname(self):
        """
        Test that the creation fails if the discriminator does not
        reference a valid class.
        """
        with self.assertRaises(ElementsError):
            op = Operation(constants.kOperationNew,
                           entities.CDBClassDef("csweb_plugin_config"),
                           [])
            op.runAsTest([],
                         SimpleArguments(plugin_id="class-tile-small",
                                         discriminator="wrong_class",
                                         component="classtilesmall",
                                         cdb_module_id="cs.web.components"),
                         True)

    def test_modify_plugin_config(self):
        """
        Test modify operation
        """
        obj = self._run_create_op()
        op = Operation(constants.kOperationModify,
                       obj,
                       [])
        op.runAsTest([],
                     SimpleArguments(component="other component"),
                     True)
        self.assertTrue(op.getObjectResult())

    def test_delete(self):
        """
        Test if deletion of a plugin_config works
        """
        obj = self._run_create_op()
        op = Operation(constants.kOperationDelete,
                       obj,
                       [])
        op.runAsTest([], [], True)

    def test_config_inheritance(self):
        """
        We made a configuration for cdbdd_field. We have to ensure that this
        configuration is set for all subclasses.
        """
        obj = self._run_create_op()
        plugin_config.Csweb_plugin.clear_cache()
        pcs = plugin_config.Csweb_plugin.get_plugin_config("class-tile-small")
        cfg_dict = {cfg["discriminator"]: cfg for cfg in pcs}
        self.assertTrue("cdbdd_field" in cfg_dict)
        self.assertTrue("cdbdd_multilang_field_predefined" in cfg_dict)
        # The configs should only differ in the discriminator
        multilang_config = dict(cfg_dict["cdbdd_multilang_field_predefined"])
        multilang_config["discriminator"] = "cdbdd_field"
        self.assertEqual(cfg_dict["cdbdd_field"], multilang_config)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
