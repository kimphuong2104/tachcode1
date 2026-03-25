#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
from __future__ import unicode_literals, print_function

"""
Module test_object_quality_characteristic

This is a test module for ObjectQualityCharacteristic
"""

import logging
from cdb import ElementsError
from cs.metrics.qcclasses import QCDefinition
from cs.metrics.tests.utils import MetricsTestCase


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


LOG = logging.getLogger(__name__)


class TestObjectQualityCharacteristic(MetricsTestCase):

    def test_kpi_activation_with_orphaned_kpi_objects(self):
        from cs.metricstests.qctestclasses import QCTest001
        top_level_obj = QCTest001.ByKeys(cdb_object_id='52f94380-273b-11e6-941a-082e5f0d0c14')
        top_level_obj.Delete()
        kpi = QCDefinition.ByKeys(identifier='qc_test_001_obj1')
        self.assertNotEqual(kpi, None)
        self.assertEqual(kpi.status, 0)
        with self.assertRaises(ElementsError) as cm:
            kpi.ChangeState(100)
        the_exception = cm.exception
        self.assertIn('52f94380-273b-11e6-941a-082e5f0d0c14', str(the_exception))
