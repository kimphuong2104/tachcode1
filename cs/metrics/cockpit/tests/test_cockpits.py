#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

"""
Module test_options

This is the documentation for the test_options module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import testcase
import unittest
import datetime

from cs.metrics.cockpit import QCCockpitTools
from cs.metrics.cockpit.qc_cockpits import gethistorydata


def setup():
    testcase.run_level_setup()


class TestObject(testcase.RollbackTestCase):

    def setUp(self):
        def fixture_installed():
            try:
                import cs.metricstests  # @UnusedImport
                return True
            except ImportError:
                return False

        if not fixture_installed():
            raise unittest.SkipTest("Fixture package cs.metrictests not installed")
        from cs.metricstests.qctestclasses import QCTest001
        self.qc_test_001_obj = QCTest001.ByKeys(code="test001")
        super(TestObject, self).setUp()

    def test_process_cockpit_render_data(self):
        with testcase.max_sql(16):
            tools = QCCockpitTools.get_qc_tools()
            render_result = tools['qccockpittools'].get_render_data('qc_process')
            assert isinstance(render_result, dict) and render_result.get('qc_process_data'), "process kpi cockpit render data not valid"

    def test_object_cockpit_render_data(self):
        with testcase.max_sql(65):
            tools = QCCockpitTools.get_qc_tools()
            render_result = tools['qccockpittools'].get_render_data('qc_object', self.qc_test_001_obj.cdb_object_id)
            assert isinstance(render_result, dict) and render_result.get('qc_object_data'), "object kpi cockpit render data not valid"
            assert [qc for qc in render_result.get('qc_object_data') if qc.get('obj') and qc.get('obj').cdbf_object_id == self.qc_test_001_obj.cdb_object_id], "object kpi cockpit render data not valid"

    def test_gethistorydata_with_invalid_qc_id(self):
        qc_ids = ['invalid']
        res = gethistorydata(qc_ids, 'qc_object')
        self.assertNotIn(qc_ids[0], res)
        self.assertEqual(len(list(res)), 0)

    def test_gethistorydata_with_time_window_set_in_kpi_definition(self):
        qc_ids = ['20a059de-b687-11e8-bbae-da141654416b']
        res = gethistorydata(qc_ids, 'qc_object')
        self.assertIn(qc_ids[0], res)
        self.assertIn('gdata', res.get(qc_ids[0]))
        history_data = res.get(qc_ids[0]).get('gdata')
        self.assertEqual(len(history_data), 1)
        for h in history_data:
            self.assertEqual(h[1], 42.0)

    def test_gethistorydata_with_time_window_overriden_by_date(self):
        qc_ids = ['20a059de-b687-11e8-bbae-da141654416b']
        res = gethistorydata(qc_ids, 'qc_object', datetime.datetime(year=2018, month=1, day=1))
        self.assertIn(qc_ids[0], res)
        self.assertIn('gdata', res.get(qc_ids[0]))
        history_data = res.get(qc_ids[0]).get('gdata')
        self.assertEqual(len(history_data), 2)
        for h in history_data:
            self.assertEqual(h[1], 42.0)

    def test_gethistorydata_with_time_window_overriden_by_date_in_future(self):
        qc_ids = ['20a059de-b687-11e8-bbae-da141654416b']
        res = gethistorydata(qc_ids, 'qc_object', datetime.datetime(year=2038, month=1, day=1))
        self.assertIn(qc_ids[0], res)
        self.assertIn('gdata', res.get(qc_ids[0]))
        self.assertEqual(len(res.get(qc_ids[0]).get('gdata')), 0)

    def test_gethistorydata_with_time_window_overriden_by_isostring(self):
        qc_ids = ['20a059de-b687-11e8-bbae-da141654416b']
        res = gethistorydata(qc_ids, 'qc_object', datetime.datetime(year=2018, month=1, day=1).isoformat())
        self.assertIn(qc_ids[0], res)
        self.assertIn('gdata', res.get(qc_ids[0]))
        history_data = res.get(qc_ids[0]).get('gdata')
        self.assertEqual(len(history_data), 2)
        for h in history_data:
            self.assertEqual(h[1], 42.0)

if __name__ == "__main__":
    unittest.main()
