#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

from __future__ import absolute_import

__revision__ = "$Id$"

from cdb import auth, sqlapi, util
from cdb.objects import Object, Reference_N, Forward, Reference_1, ReferenceMethods_N
from cs.web.components.library_config import Libraries
from cdb import i18n

import json

Dashboard = Forward(__name__ + ".Dashboard")
DashboardItem = Forward(__name__ + ".DashboardItem")

DASHBOARD_LAYOUTS = [
    {'name': 'm', 'columns': ['medium']},
    {'name': 'mm', 'columns': ['medium', 'medium']},
    {'name': 'ms', 'columns': ['medium', 'small']},
    {'name': 'sm', 'columns': ['small', 'medium']},
    {'name': 'mmm', 'columns': ['medium', 'medium', 'medium']},
    {'name': 'mss', 'columns': ['medium', 'small', 'small']},
    {'name': 'sms', 'columns': ['small', 'medium', 'small']},
    {'name': 'ssm', 'columns': ['small', 'small', 'medium']},
    {'name': 'mmmm', 'columns': ['medium', 'medium', 'medium', 'medium']}
]
NEW_DASHBOARD_LAYOUT_NAME = DASHBOARD_LAYOUTS[6]['name']

fDashboardWidgetLibs = Forward(__name__ + ".DashboardWidgetLibs")
fDashboardWidget = Forward(__name__ + ".DashboardWidget")


class DashboardWidgetLibs(Object):
    __maps_to__ = "csweb_dashboard_widget_libs"
    __classname__ = "csweb_dashboard_widget_libs"

    Library = Reference_1(Libraries, fDashboardWidgetLibs.library_name)


class DashboardWidget(Object):
    __maps_to__ = "csweb_dashboard_widget"

    LibraryReferences = Reference_N(DashboardWidgetLibs,
                                    DashboardWidgetLibs.id == fDashboardWidget.id,
                                    order_by=DashboardWidgetLibs.pos_nr)

    def _get_libraries(self):
        qry = ("SELECT l.*"
               " FROM csweb_libraries l INNER JOIN csweb_dashboard_widget_libs cl"
               " ON l.library_name = cl.library_name"
               " WHERE cl.id = '%s'"
               " ORDER BY cl.pos_nr") % sqlapi.quote(self.id)
        return Libraries.SQL(qry)

    Libraries = ReferenceMethods_N(Libraries, _get_libraries)

    def app_setup(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'component': self.component
        }


class Dashboard(Object):
    __maps_to__ = "csweb_dashboard"

    Items = Reference_N(DashboardItem,
                        DashboardItem.dashboard_id == Dashboard.cdb_object_id)

    @classmethod
    def get_dashboard_collection(cls, manage_view=False):
        personal_dashboards = cls.KeywordQuery(subject_type="Person",
                                               subject_id=auth.persno,
                                               is_template=0
                                               ).Execute()
        args = {'subject_type': "Common Role"}
        if not manage_view:
            my_roles = util.get_roles('GlobalContext', '', auth.persno)
            args['subject_id'] = my_roles
        role_dashboards = cls.KeywordQuery(**args).Execute()

        result = role_dashboards + personal_dashboards

        if len(result) > 0:
            return result

        return [cls.create_dashboard()]

    @classmethod
    def get_dashboard_collection_within(cls, start_pos, end_pos):
        ownedRealDashboards = "subject_id = '%s' AND subject_type='Person' AND is_template = 0" % \
                              sqlapi.quote(auth.persno)
        withinRange = "position_index >= %d AND position_index < %d" % (start_pos, end_pos)
        cond = "%s AND %s" % (ownedRealDashboards, withinRange)
        return cls.Query(condition=cond, order_by="position_index").Execute()

    @classmethod
    def get_next_position(cls):
        stmt = "max(position_index) as max_position FROM csweb_dashboard WHERE subject_id='%s' " \
               "AND subject_type='Person'" % sqlapi.quote(auth.persno)
        value = sqlapi.SQLselect(stmt)
        return value.get_integer("max_position", 0) + 1

    @classmethod
    def get_min_position(cls):
        stmt = "min(position_index) as min_position FROM csweb_dashboard WHERE subject_id='%s' " \
               "AND subject_type='Person'" % sqlapi.quote(auth.persno)
        value = sqlapi.SQLselect(stmt)
        return value.get_integer("min_position", 0)

    @classmethod
    def create_dashboard(cls, name=""):
        descriptor = cls.GetFieldByName('name')

        lang_fields = descriptor.getLanguageFields()
        lang_values = {}

        for active_langs in i18n.getActiveGUILanguages():
            field_name = lang_fields[active_langs].name
            lang_values[field_name] = (name or util.get_label_with_fallback(
                'web.cs_web_dashboard.default_name',
                active_langs))

        dabo = cls.Create(subject_type='Person',
                          subject_id=auth.persno,
                          layout=NEW_DASHBOARD_LAYOUT_NAME,
                          is_template=0,
                          position_index=cls.get_next_position(),
                          **lang_values)

        cls.place_onboarding_widget(dabo.cdb_object_id)
        return dabo

    @classmethod
    def by_id(cls, object_id):
        result = cls.ByKeys(object_id)
        if result is None or not result.CheckAccess('read'):
            return None
        else:
            return result

    @classmethod
    def place_onboarding_widget(cls, object_id):
        data = {
            'dashboard_id': object_id,
            'widget_id': 'onboarding',
            'xpos': 1,
            'ypos': 1,
            'collapsed': 0,
            'settings': json.dumps({}),
            'subject_type': 'Person',
            'subject_id': auth.persno
        }

        DashboardItem.Create(**data)


class DashboardItem(Object):
    __maps_to__ = "csweb_dashboard_item"

    @classmethod
    def by_id(cls, dashboard_id, item_id):
        item = cls.ByKeys(item_id)
        if item is None or item.dashboard_id != dashboard_id or not item.CheckAccess('read'):
            return None
        else:
            return item
