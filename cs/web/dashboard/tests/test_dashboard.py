#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest
from webtest import TestApp as Client
from cdb import testcase, sqlapi
from cs.platform.web.root import Root
from cs.web.dashboard import (Dashboard, DashboardItem)


def create_dashboard(dashboard, items):
    dashboard = Dashboard.Create(**dashboard)
    for item in items:
        DashboardItem.Create(
            dashboard_id=dashboard.cdb_object_id,
            **item
        )
    return dashboard


class TestDashboardAPI(testcase.RollbackTestCase):
    """
    Tests for the dashboard REST API.
    """

    @classmethod
    def setUpClass(cls):
        """
        Set up the test case
        """
        super(TestDashboardAPI, cls).setUpClass()

        cls.dashboard_1 = create_dashboard(
            {
                'name_de': 'Dashboard 1',
                'subject_type': 'Person',
                'subject_id': 'caddok',
                'is_template': 0,
                'position_index': 10
            },
            [{
                'widget_id': 'onboarding',
                'xpos': 1,
                'ypos': 1,
                'subject_type': 'Person',
                'subject_id': 'caddok',
            }]
        )

        cls.dashboard_2 = create_dashboard(
            {
                'name_de': 'Dashboard 2',
                'subject_type': 'Person',
                'subject_id': 'caddok',
                'is_template': 0,
                'position_index': 20
            },
            [{
                'widget_id': 'onboarding',
                'xpos': 1,
                'ypos': 1,
                'subject_type': 'Person',
                'subject_id': 'caddok',
            }]
        )

    @classmethod
    def tearDownClass(cls):
        super(TestDashboardAPI, cls).tearDownClass()
        dashboard_ids = [cls.dashboard_1.cdb_object_id, cls.dashboard_2.cdb_object_id]
        for dashboard_id in dashboard_ids:
            sqlapi.SQLdelete("FROM csweb_dashboard WHERE cdb_object_id = '%s'" % dashboard_id)
            sqlapi.SQLdelete("FROM csweb_dashboard_item WHERE dashboard_id = '%s'" % dashboard_id)

    def test_update_dashboards(self):
        """
        Update two Dashboards
        """
        c = Client(Root())
        id_1 = self.dashboard_1.cdb_object_id
        id_2 = self.dashboard_2.cdb_object_id
        data = {
            'dashboards': {
                id_1: {
                    'cdb_module_id': '',
                    'cdb_object_id': id_1,
                    'is_role_dashboard': True,
                    'is_template': 0,
                    'name': "Role Dashboard",
                    'name_multi_lang': {
                        'de': {'attribute': "name_de", 'value': "Role Dashboard"},
                        'en': {'attribute': "name_en", 'value': "Role Dashboard"}
                    },
                    'position_index': 10,
                    'subject_id': "public",
                },
                id_2: {
                    'cdb_module_id': '',
                    'cdb_object_id': id_2,
                    'is_role_dashboard': False,
                    'is_template': 0,
                    'name': "Mein Dashboard",
                    'name_multi_lang': {
                        'de': {'attribute': "name_de", 'value': "Mein Dashboard"},
                        'en': {'attribute': "name_en", 'value': "My Dashboard"}
                    },
                    'position_index': 10,
                }
            },
            'removedDashboards': {},
        }
        c.post_json('/internal/cs.web.dashboard/dashboard_collection/update', data)
        updated_dashboards = Dashboard.KeywordQuery(cdb_object_id=[id_1, id_2])
        updated_dashboard_items = DashboardItem.KeywordQuery(dashboard_id=[id_1, id_2])
        for dashboard in updated_dashboards:
            if dashboard.cdb_object_id == id_1:
                self.assertEquals(dashboard.name_de, 'Role Dashboard')
                self.assertEquals(dashboard.name_en, 'Role Dashboard')
                self.assertEquals(dashboard.subject_type, 'Common Role')
                self.assertEquals(dashboard.subject_id, 'public')
                self.assertEquals(dashboard.position_index, 10)
                self.assertEquals(dashboard.is_template, 0)
            elif dashboard.cdb_object_id == id_2:
                self.assertEquals(dashboard.name_de, 'Mein Dashboard')
                self.assertEquals(dashboard.name_en, 'My Dashboard')
                self.assertEquals(dashboard.subject_type, 'Person')
                self.assertEquals(dashboard.subject_id, 'caddok')
                self.assertEquals(dashboard.position_index, 10)
                self.assertEquals(dashboard.is_template, 0)

        for dashboard_item in updated_dashboard_items:
            if dashboard_item.dashboard_id == id_1:
                self.assertEquals(dashboard_item.subject_type, 'Common Role')
                self.assertEquals(dashboard_item.subject_id, 'public')
            elif dashboard_item.dashboard_id == id_2:
                self.assertEquals(dashboard_item.subject_type, 'Person')
                self.assertEquals(dashboard_item.subject_id, 'caddok')

    def test_update_template(self):
        """
        Create template from dashboard
        """
        c = Client(Root())
        id_1 = self.dashboard_1.cdb_object_id
        data = {
            'dashboards': {
                id_1: {
                    'cdb_module_id': 'test_module',
                    'cdb_object_id': id_1,
                    'is_role_dashboard': True,
                    'is_template': 1,
                    'name': "Template",
                    'name_multi_lang': {
                        'de': {'attribute': "name_de", 'value': "Template"},
                        'en': {'attribute': "name_en", 'value': "Template"}
                    },
                    'position_index': 10,
                    'subject_id': "public",
                }
            },
            'removedDashboards': {},
        }
        c.post_json('/internal/cs.web.dashboard/dashboard_collection/update', data)
        dashboard = Dashboard.ByKeys(cdb_object_id=id_1)
        dashboard_items = DashboardItem.KeywordQuery(dashboard_id=[id_1])
        self.assertEquals(dashboard.subject_type, 'Common Role')
        self.assertEquals(dashboard.subject_id, 'public')
        self.assertEquals(dashboard.is_template, 1)

        for dashboard_item in dashboard_items:
            if dashboard_item.dashboard_id == id_1:
                self.assertEquals(dashboard_item.subject_type, 'Common Role')
                self.assertEquals(dashboard_item.subject_id, 'public')

    def test_remove_dashboard(self):
        """
        Remove existing dashboard
        """
        c = Client(Root())
        id_1 = self.dashboard_1.cdb_object_id
        data = {
            'dashboards': {},
            'removedDashboards': {
                id_1: {
                    'cdb_object_id': id_1
                }
            },
        }
        c.post_json('/internal/cs.web.dashboard/dashboard_collection/update', data)
        dashboard = Dashboard.ByKeys(cdb_object_id=id_1)
        dashboard_items = DashboardItem.KeywordQuery(dashboard_id=[id_1])
        self.assertEquals(dashboard, None)
        for dashboard_item in dashboard_items:
            if dashboard_item.dashboard_id == id_1:
                self.assertEquals(dashboard_item, None)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
