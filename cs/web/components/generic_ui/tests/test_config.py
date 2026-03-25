#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from __future__ import absolute_import
__revision__ = "$Id$"

import unittest

from cdb import testcase
from cdb.platform.mom.entities import CDBClassDef
from cdb.validationkit.SwitchRoles import run_with_roles
from cs.web.components.generic_ui import select_view, _select_view_intern
from cs.web.components.configurable_ui import Csweb_page_config_detail


class TestConfig(testcase.PlatformTestCase):

    # we want to see the complete JSON diff, not truncated
    maxDiff = None

    VIEW_CFG = [{"classname": "*",
                 "viewname": "default",
                 "roles": ["public"]},
                {"classname": "cdbdd_local_field",
                 "viewname": "extra",
                 "priority": 20,
                 "roles": ["public"]},
                {"classname": "cdbdd_local_field",
                 "viewname": "extra_admin",
                 "priority": 25,
                 "roles": ["Administrator"]},
                {"classname": "cdbdd_int_field",
                 "viewname": "for_int_field",
                 "priority": 30,
                 "roles": ["nobody"]},
                {"classname": "cdbdd_local_field",
                 "viewname": "special",
                 "priority": 10,
                 "roles": ["public"]}
                ]

    @run_with_roles(["public"])
    def test_select_view_fallback(self):
        self.assertEqual(select_view(self.VIEW_CFG, CDBClassDef('cdb_class')),
                         self.VIEW_CFG[0])

    @run_with_roles(["public"])
    def test_select_view_named(self):
        self.assertEqual(select_view(self.VIEW_CFG, CDBClassDef('cdbdd_int_field'), "special"),
                         self.VIEW_CFG[4])

    @run_with_roles(["public"])
    def test_select_view_public(self):
        self.assertEqual(select_view(self.VIEW_CFG, CDBClassDef('cdbdd_int_field')),
                         self.VIEW_CFG[1])

    @run_with_roles(["public", "Administrator"])
    def test_select_view_admin(self):
        self.assertEqual(select_view(self.VIEW_CFG, CDBClassDef('cdbdd_int_field')),
                         self.VIEW_CFG[2])


class TestInternalConfig(testcase.PlatformTestCase):

    # we want to see the complete JSON diff, not truncated
    maxDiff = None

    VIEW_CFG = [{"classname": "*",
                 "viewname": "default",
                 "roles": ["public"]},
                {"classname": "rel_nm_parent",
                 "viewname": "default",
                 "priority": 20,
                 "roles": ["public"]}
                ]

    @run_with_roles(["public"])
    def test_select_view_public(self):
        self.assertEqual(
            _select_view_intern(self.VIEW_CFG,
                                CDBClassDef('fixture_nm_parent'),
                                ["rel_nm_parent", "*"],
                                None),
            self.VIEW_CFG[1])


class TestLoadConfig(testcase.RollbackTestCase):

    maxDiff = None

    VIEW_CFG = {"page_id": "dummy_page",
                "classname": "*",
                "pageframe_id": "dummy_pageframe",
                "priority": 42,
                "viewname": "default",
                "config_component": "dummy_component"}

    def setUp(self):
        super(TestLoadConfig, self).setUp()
        self.detail_page_config = Csweb_page_config_detail.Create(**self.VIEW_CFG)

    def test_load(self):
        loaded = Csweb_page_config_detail.ByKeys(self.VIEW_CFG["page_id"]).convert2dict()
        expected = dict(self.VIEW_CFG)
        expected.pop("page_id")
        expected["component"] = expected.pop("config_component")
        expected["roles"] = []
        self.assertEqual(expected, loaded)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
