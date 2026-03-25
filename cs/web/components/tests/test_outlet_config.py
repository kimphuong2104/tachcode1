#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest
import os
from cdb import testcase
from cdb.version import getVersionDescription
from cdb.platform.mom import entities
from cs.web.components import outlet_config, library_config
from cs.web.components.ui_support import outlets
from cs.platform.web.static import File


class TestOutletConfig(testcase.PlatformTestCase):
    def setUp(self):
        """
        Set up the test case
        """
        try:
            import cs.webtest
        except RuntimeError:
            raise unittest.SkipTest("this test needs cs.webtest")
        super(TestOutletConfig, self).setUp()
        self.model = outlets.OutletConfig("outlet_test", "cswebtest_outlet_definition", "")
        self.outlet_config_path = os.path.join(os.path.dirname(cs.webtest.__file__), 'page_conf', 'outlet_config.json')


class test__replace_outlet(TestOutletConfig):
    """
    Test the function _replace_outlet
    """

    def test_valid_input(self):
        """
        We expect new_conf to be modified with the correct values for a valid input.
        """
        new_conf = {}
        outlet_config._replace_outlet(self.model, new_conf, "outlet_test")
        library_names = [l.get("library_name") for l in new_conf.get("libraries")]
        children = [l.get("name") for l in new_conf.get("children")]
        self.assertTrue("cs-webtest-library" in library_names)
        self.assertTrue("cs-webtest-library2" in library_names)
        self.assertTrue("cs-webtest-library3" in library_names)
        self.assertTrue("cs-webtest-library4" in library_names)
        self.assertTrue("cs-webtest-library5" in library_names)
        self.assertTrue("cs-webtest-HelloWorld" in children)
        self.assertEquals(len(library_names), 5)
        self.assertEquals(len(children), 1)

    def test_outlet_name_is_none(self):
        """
        We expect new_conf to be empty if the outlet_name is None.
        """
        new_conf = {}
        outlet_config._replace_outlet(self.model, new_conf)
        self.assertEquals(new_conf, {})


class test_get_script_urls(TestOutletConfig):
    """
    Test the function _get_script_urls
    """

    def test_valid_input(self):
        """
        We expect a result of length two with the correct urls for a valid input.
        """
        result = library_config._get_script_urls("cs-webtest-library", "15.1.0")
        library_urls = [r for r in result]
        self.assertTrue("/appstatic/cs-webtest-library/15.1.0/test_library.js" in library_urls)
        self.assertTrue("/appstatic/cs-webtest-library/15.1.0/test_library2.js" in library_urls)
        self.assertEquals(len(result), 2)

    def test_invalid_library_name(self):
        """
        We expect a ValueError for a library_name that does not exist
        """
        self.assertRaises(ValueError, library_config._get_script_urls,
                          "wrong_library_name", "15.1.0")

    def test_invalid_library_version(self):
        """
        We expect a ValueError for a library_version that does not exist
        """
        if getVersionDescription().startswith("16"):
            raise unittest.SkipTest("Makes no sense in CE 16")
        self.assertRaises(ValueError, library_config._get_script_urls,
                          "cs-webtest-library", "wrong_library_version")


class test_url(TestOutletConfig):
    """
    Test the function url
    """

    def test_valid_input(self):
        file = File(".js", "test_library.js")
        url = library_config.url(file, "appstatic/test")
        self.assertEquals(url, "appstatic/test/test_library.js")

    def test_invalid_file_extension(self):
        """
        We expect the result to be an empty string for an invalid file extension.
        """
        file = File(".css", "test_library.css")
        url = library_config.url(file, "appstatic/test")
        self.assertEquals(url, "")

    @testcase.without_error_logging
    def test_undefined_file_extension(self):
        """
        We expect a ValueError exception for an undefined file extension.
        """
        file = File(".invalidFileExtension", "test_library.invalidFileExtension")
        self.assertRaises(ValueError, library_config.url, file, "appstatic/test")


class test__make_component(TestOutletConfig):
    """
    Test the function _make_component
    """

    def test_without_config_file(self):
        """
        We expect the result to contain the specified TestComponent2.
        """
        conf = {'component': u'cs-web-test-TestComponent2'}
        key = "__outlet_0"
        result = outlet_config._make_component(self.model, conf, key)
        self.assertEquals(result.get("name"), "cs-web-test-TestComponent2")

    def test_with_config_file(self):
        """
        We expect the result to contain the configured ReactComponent.
        """
        conf = {
            'component': u'cs-web-test-TestComponent2',
            'configuration': self.outlet_config_path
        }
        key = "__outlet_0"
        result = outlet_config._make_component(self.model, conf, key)
        self.assertEquals(result.get("name"), "cs-web-test-TestComponent")


class test__get_libraries(TestOutletConfig):
    """
    Test the function _get_libraries
    """

    def test_without_config_file(self):
        """
        We expect the result to contain the two configured libraries.
        """
        conf = {'outlet_child_name': u'cs-web-test-TestComponent2'}
        result = outlet_config._get_libraries(self.model, conf)
        self.assertEquals(len(result), 5)
        library_names = [r.get("library_name") for r in result]
        script_urls = [r.get("script_urls") for r in result]
        self.assertEquals(len(script_urls), 5)
        self.assertTrue("cs-webtest-library" in library_names)
        self.assertTrue("cs-webtest-library2" in library_names)
        self.assertTrue("cs-webtest-library3" in library_names)
        self.assertTrue("cs-webtest-library4" in library_names)
        self.assertTrue("cs-webtest-library5" in library_names)

    def test_with_config_file(self):
        """
        We expect the result to contain the configured libraries.
        """
        conf = {
            'outlet_child_name': u'cs-web-test-TestComponent2',
            'configuration': self.outlet_config_path
        }
        result = outlet_config._get_libraries(self.model, conf)
        library_names = [r.get("library_name") for r in result]
        self.assertTrue("cs-webtest-library" in library_names)
        self.assertTrue("cs-webtest-library2" in library_names)
        self.assertTrue("cs-webtest-library3" in library_names)
        self.assertTrue("cs-webtest-library4" in library_names)
        self.assertTrue("cs-webtest-library5" in library_names)
        self.assertTrue("cs-web-components-pdf" in library_names)
        self.assertTrue("cs-webtest-library6" in library_names)
        self.assertTrue("cs-webtest-library7" in library_names)
        self.assertEquals(len(result), 8)


class test_outlet_description(TestOutletConfig):
    """
    Test the relations of the class OutletDescription
    """

    def test_outlet_description_relation(self):
        """
        We expect the outlet_name of the related Definitions to be "outlet_test".
        """
        cfg = outlet_config.OutletDescription.ByKeys("outlet_test")
        outlet_names = cfg.Definitions.outlet_name
        self.assertEquals(len(outlet_names), 1)
        self.assertTrue("outlet_test" in outlet_names)


class test_get_outlet_definition(TestOutletConfig):
    """
    Test the method get_outlet_definition
    """

    def test_with_position(self):
        model = outlets.OutletConfig("outlet_test6", "cswebtest_outlet_definition", "")
        outlet_definitions = outlet_config.OutletDefinition.get_outlet_definition("outlet_test6", model.classdef)
        self.assertEquals(len(outlet_definitions), 1)
        self.assertTrue("cs-web-test-TestComponent" in outlet_definitions[10][0].get("outlet_child_name"))

    def test_with_double_fallback(self):
        model = outlets.OutletConfig("outlet_test1", "cswebtest_outlet_definition", "")
        outlet_definitions = outlet_config.OutletDefinition.get_outlet_definition("outlet_test1", model.classdef)
        self.assertEquals(len(outlet_definitions), 2)
        self.assertTrue("cs-web-test-TestComponent" in outlet_definitions[10][0].get("outlet_child_name"))
        self.assertTrue("cs-web-test-TestComponent2" in outlet_definitions[20][0].get("outlet_child_name"))

    def test_with_missing_outlet_definition(self):
        model = outlets.OutletConfig("outlet_test4", "cswebtest_outlet_definition", "")
        outlet_definitions = outlet_config.OutletDefinition.get_outlet_definition("outlet_test4", model.classdef)
        self.assertEquals(len(outlet_definitions), 0)

    def test_with_asterisk(self):
        model = outlets.OutletConfig("outlet_test8", "cswebtest_outlet_definition", "")
        outlet_definitions = outlet_config.OutletDefinition.get_outlet_definition("outlet_test8", model.classdef)
        self.assertEquals(len(outlet_definitions), 2)
        self.assertTrue("cs-web-test-TestComponent" in outlet_definitions[10][0].get("outlet_child_name"))
        self.assertTrue("cs-web-test-TestComponent2" in outlet_definitions[20][0].get("outlet_child_name"))


class test_get_outlet_positions(TestOutletConfig):
    """
    Test the method get_outlet_positions
    """

    def test_outlet_child_name(self):
        cdef = entities.CDBClassDef("cswebtest_outlet_definition")
        result = outlet_config.OutletDefinition.get_outlet_positions("outlet_test", cdef)
        self.assertTrue(len(result), 1)
        self.assertEquals(result[0].get("outlet_child_name"), "cs-web-test-TestComponent2")


class test_outlet_child(TestOutletConfig):
    """
    Test the class OutletChild
    """

    def setUp(self):
        super(test_outlet_child, self).setUp()
        self.outlet_child = outlet_config.OutletChild.ByKeys("cs-web-test-TestComponent")

    def test_outlet_child_libraries(self):
        """
        We expect the result to contain the two configured libraries.
        """
        result = self.outlet_child.Libraries
        self.assertTrue(len(result), 2)
        self.assertEquals(result[0].library_name, "cs-webtest-library")
        self.assertEquals(result[0].library_version, "15.1.0")
        self.assertEquals(result[0].cdb_module_id, "cs.webtest")
        self.assertEquals(result[1].library_name, "cs-webtest-library2")
        self.assertEquals(result[1].library_version, "15.3.0")
        self.assertEquals(result[1].cdb_module_id, "cs.webtest")

    def test_get_title(self):
        """
        We expect the result to be equals to "WebTest".
        """
        self.assertEquals(self.outlet_child.get_title(), "WebTest")

    def test_to_dict(self):
        """
        We expect the result to contain a all specified attributes with the correct values.
        """
        result = self.outlet_child.to_dict()
        self.assertEquals(result.get("title"), "WebTest")
        self.assertEquals(result.get("icon_id"), "")
        self.assertEquals(result.get("outlet_child_name"), "cs-web-test-TestComponent")
        self.assertEquals(result.get("properties"), {})
        self.assertEquals(result.get("component"), "cs-webtest-HelloWorld")


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
