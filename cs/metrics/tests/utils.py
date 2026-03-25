#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
import unittest
from cdb import testcase

"""
Module utils

Contain a Base TestCase class to be used in tests.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports


class MetricsTestCase(testcase.RollbackTestCase):

    def __init__(self, *args, **kwargs):
        self.need_uberserver = kwargs.pop('need_uberserver', False)
        super(MetricsTestCase, self).__init__(*args, **kwargs)

    def setUp(self):

        def fixture_installed():
            try:
                import cs.metricstests
                return True
            except ImportError:
                return False

        if not fixture_installed():
            raise unittest.SkipTest("Fixture package cs.metricstests not installed")
        if self.need_uberserver:
            testcase.require_uberserver()
        super(MetricsTestCase, self).setUp()

    def setDown(self):
        if self.need_uberserver:
            testcase.stop_uberserver()
