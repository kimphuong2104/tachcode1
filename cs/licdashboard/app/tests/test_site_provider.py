#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Test Module test_site_provider

This is the documentation for the tests.
"""

from __future__ import absolute_import

import unittest

from cdb.objects.org import Person
from cdb.testcase import RollbackOnceTestCase

try:
    from cdb.fls import LicenseSite
except ImportError:
    LicenseSite = None
from cs.licdashboard.app.site_provider import (
    LicenseSiteProvider,
    OrganizationSiteProvider,
    PersonCitySiteProvider,
    SiteProviderBase,
)

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


# Tests
class site_provider_test_base(RollbackOnceTestCase):
    @classmethod
    def setUpClass(cls, provider=SiteProviderBase):
        super(site_provider_test_base, cls).setUpClass()
        cls.provider = provider(["caddok", "unknown_person"])
        cls.person = Person.ByKeys("caddok")

    def test_unknown_site(self):
        us = self.provider.get_unknown_site()
        self.assertTrue(isinstance(us, dict))
        self.assertTrue("site_id" in us)
        self.assertTrue("name" in us)
        self.assertTrue("region" in us)

    def test_is_available(self):
        self.assertTrue(self.provider.is_available())

    def test_get_site_by_unknown_person(self):
        s = self.provider.get_site_by_person("unknown_person")
        self.assertEqual(s, None)

    def test_get_site_by_unknown_person(self):
        s = self.provider.get_site_by_person("unknown_person")
        self.assertEqual(s, None)


class Test_LicenseSiteProvider(site_provider_test_base):
    @classmethod
    def setUpClass(cls, provider=LicenseSiteProvider):
        if not LicenseSite:
            raise unittest.SkipTest("Test requires fls.LicenseSite")
        super(Test_LicenseSiteProvider, cls).setUpClass(provider=provider)
        if not cls.person:
            raise unittest.SkipTest("Test requires caddok")
        if not cls.person.license_site_id:
            cls.site = LicenseSite.Create(
                name_de="Test", name_en="Test", region="Region"
            )
            cls.person.license_site_id = cls.site.cdb_object_id
        else:
            cls.site = LicenseSite.ByKeys(cls.person.license_site_id)

    def test_get_site_id_by_person(self):
        site_id = self.provider.get_site_id_by_person("caddok")
        self.assertEqual(site_id, self.person.license_site_id)

    def test_get_site_id_by_unknown_person(self):
        site_id = self.provider.get_site_id_by_person("unknown_person")
        self.assertEqual(site_id, self.provider.get_unknown_site_id())

    def test_get_site_id_by_person(self):
        s = self.provider.get_site_by_person("caddok")
        self.assertEqual(s["site_id"], self.person.license_site_id)
        self.assertEqual(s["name"], self.site.name)

    def test_get_sites(self):
        sites = self.provider.get_sites()
        self.assertEqual(len(sites), 1)
        self.assertEqual(sites[0]["site_id"], self.person.license_site_id)


class Test_OrganizationSiteProvider(site_provider_test_base):
    @classmethod
    def setUpClass(cls, provider=OrganizationSiteProvider):
        super(Test_OrganizationSiteProvider, cls).setUpClass(provider=provider)
        if not cls.person:
            raise unittest.SkipTest("Test requires caddok")

    def test_get_site_id_by_person(self):
        site_id = self.provider.get_site_id_by_person("caddok")
        self.assertEqual(site_id, self.person.org_id)

    def test_get_site_id_by_unknown_person(self):
        site_id = self.provider.get_site_id_by_person("unknown_person")
        self.assertEqual(site_id, self.provider.get_unknown_site_id())

    def test_get_site_id_by_person(self):
        s = self.provider.get_site_by_person("caddok")
        self.assertEqual(s["site_id"], self.person.org_id)
        self.assertEqual(s["name"], self.person.Organization.name)

    def test_get_sites(self):
        sites = self.provider.get_sites()
        self.assertEqual(len(sites), 1)
        self.assertEqual(sites[0]["site_id"], self.person.org_id)


class Test_CitySiteProvider(site_provider_test_base):
    @classmethod
    def setUpClass(cls, provider=PersonCitySiteProvider):
        super(Test_CitySiteProvider, cls).setUpClass(provider=provider)
        if not cls.person:
            raise unittest.SkipTest("Test requires caddok")

    def test_get_site_id_by_person(self):
        site_id = self.provider.get_site_id_by_person("caddok")
        self.assertEqual(site_id, self.person.city)

    def test_get_site_id_by_unknown_person(self):
        site_id = self.provider.get_site_id_by_person("unknown_person")
        self.assertEqual(site_id, self.provider.get_unknown_site_id())

    def test_get_site_id_by_person(self):
        s = self.provider.get_site_by_person("caddok")
        self.assertEqual(s["site_id"], self.person.city)
        self.assertEqual(s["name"], self.person.city)

    def test_get_sites(self):
        sites = self.provider.get_sites()
        self.assertEqual(len(sites), 1)
        self.assertEqual(sites[0]["site_id"], self.person.city)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
