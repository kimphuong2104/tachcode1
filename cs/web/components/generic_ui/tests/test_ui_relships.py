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
from webtest import TestApp as Client
from cdb import testcase
from cs.platform.web.root import Root


class TestUIRelships(testcase.RollbackTestCase):

    maxDiff = None

    def setUp(self):
        from cdb.objects import org
        self.child = org.Person.ByKeys("caddok")
        if self.child:
            self.parent = self.child.Organization
        if not self.child or not self.parent:
            raise unittest.SkipTest("Test needs caddok assigned to a valid organization")
        super(TestUIRelships, self).setUp()
        self.c = Client(Root())

    def _parent_ui_url(self):
        with testcase.error_logging_disabled():
            response = self.c.get(u'http://localhost/api/v1/collection/organization/%s' % self.parent.org_id)
            return response.json['system:ui_link']

    def _child_ui_url(self):
        with testcase.error_logging_disabled():
            response = self.c.get(u'http://localhost/api/v1/collection/person/%s' % self.child.personalnummer)
            return response.json['system:ui_link']

    def test_get_ui_parent(self):
        with testcase.error_logging_disabled():
            response = self.c.get(u'%s/relship/Organization' % self._child_ui_url())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, self._parent_ui_url())

    def test_relship_not_found(self):
        with testcase.error_logging_disabled():
            response = self.c.get(u'%s/relship/NotThere' % self._parent_ui_url(), status='4*')
        self.assertEqual(response.status_code, 404)

    def test_nary_relship(self):
        with testcase.error_logging_disabled():
            response = self.c.get(u'%s/relship/Cdb_organization_to_cdb_person' % self._parent_ui_url(), status='4*')
        self.assertEqual(response.status_code, 400)
