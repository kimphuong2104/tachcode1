#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Internal morepath app for the dashboard. Provides the API for the dashboard page.
"""

from __future__ import absolute_import

__revision__ = "$Id$"

import json
import six
from morepath import Response
from webob.exc import HTTPCreated, HTTPNoContent, HTTPBadRequest, HTTPForbidden

from cdb import auth
from cdb import sqlapi
from cdb import transactions
from cdb import i18n
from cdb.platform.mom.entities import CDBClassDef
from cs.platform.web import PlatformApp
from cs.platform.web.root import Internal, get_internal
from . import Dashboard, DashboardItem


def _update_dashboard_item_collection(model, positions, request):
    # Most position changes will be shifts by one in y-direction. Collect these
    # separately, so that they can be processed with a single statement.
    y_plus_one_ids = []
    y_minus_one_ids = []
    moved_items = []
    for item in model.items:
        pos = positions.get(item.cdb_object_id)
        if pos is None:
            continue
        new_xpos = pos['xpos']
        new_ypos = pos['ypos']
        # Check for +/- 1 first
        if new_ypos == item.ypos + 1 and new_xpos == item.xpos:
            y_plus_one_ids.append(item.cdb_object_id)
        elif new_ypos == item.ypos - 1 and new_xpos == item.xpos:
            y_minus_one_ids.append(item.cdb_object_id)
        elif new_xpos != item.xpos or new_ypos != item.ypos:
            moved_items.append(item)

    with transactions.Transaction():
        if y_plus_one_ids:
            sqlapi.SQLupdate('%s SET ypos = ypos + 1 WHERE cdb_object_id IN (%s)'
                             % (DashboardItem.__maps_to__,
                                ','.join(["'%s'" % sqlapi.quote(id)
                                          for id in y_plus_one_ids])))
        if y_minus_one_ids:
            sqlapi.SQLupdate('%s SET ypos = ypos - 1 WHERE cdb_object_id IN (%s)'
                             % (DashboardItem.__maps_to__,
                                ','.join(["'%s'" % sqlapi.quote(id)
                                          for id in y_minus_one_ids])))
        for item in moved_items:
            item.Update(xpos=positions[item.cdb_object_id]['xpos'],
                        ypos=positions[item.cdb_object_id]['ypos'])
    # Return the full item collection, not only the positions
    return _get_dashboard_item_collection(model, request)


class InternalDashboardApp(PlatformApp):
    PATH = 'cs.web.dashboard'

    @classmethod
    def get_app(cls, request):
        return get_internal(request).child(cls.PATH)


@Internal.mount(app=InternalDashboardApp, path=InternalDashboardApp.PATH)
def _mount_app():
    return InternalDashboardApp()


@InternalDashboardApp.path(model=Dashboard, path='{dashboard_id}',
                           variables=lambda d: dict(dashboard_id=d.cdb_object_id))
def _dashboard_path(dashboard_id):
    return Dashboard.by_id(dashboard_id)


@InternalDashboardApp.json(model=Dashboard)
def _get_dashboard(model, request):
    return {
        '@id': request.link(model),
        'items_link': request.class_link(DashboardItemCollection,
                                         {'dashboard_id': model.cdb_object_id}),
        'layout': model.layout,
        'name': model.name,
        'name_multi_lang': {a.getIsoLang(): {'attribute': a.getName(), 'value': model[a.getName()]}
                            for ml in CDBClassDef('csweb_dashboard').getMultiLangAttributeDefs()
                            for a in ml.getLanguageAttributeDefs()
                            if a.getIsoLang() in i18n.getActiveGUILanguages()
                            if ml.getName() == 'name'},
        'cdb_object_id': model.cdb_object_id,
        'position_index': model.position_index,
        'is_role_dashboard': model.subject_type == 'Common Role',
        'is_template': model.is_template,
        'subject_id': model.subject_id,
        'cdb_module_id': model.cdb_module_id
    }


@InternalDashboardApp.json(model=Dashboard, request_method='PUT')
def _put_dashboard(model, request):
    layout = request.json.get('layout')
    name = request.json.get('name')
    new_default = request.json.get('default_id')
    positions = request.json.get('positions')
    position_index = request.json.get('position_index')
    old_position_index = request.json.get('old_position_index')
    dashboardDetails = {}
    if layout is not None:
        model.layout = layout
    if name is not None:
        model.name_de = name
        model.name_en = name
    if positions is not None:
        dashboardDetails = _update_dashboard_item_collection(
            DashboardItemCollection(model.cdb_object_id), positions, request)
    if (position_index is not None and
            position_index >= Dashboard.get_min_position() and
            position_index < Dashboard.get_next_position() and
            old_position_index is not None and
            old_position_index >= Dashboard.get_min_position() and
            old_position_index < Dashboard.get_next_position()):
        # find dashboards that are in the range between old and new position_index
        new_pos_is_smaller = old_position_index > position_index

        def adjustDashboardPositions(start_pos, end_pos, adjustment):
            dashboards = Dashboard.get_dashboard_collection_within(start_pos, end_pos)
            dashboards_og_positions = list(map(lambda db: db.position_index, dashboards))
            # adjust the position_index for each dashboard in the collection
            index = 0
            for dashboard in dashboards:
                i = index + adjustment
                if i >= len(dashboards) or i < 0:
                    dashboard.position_index = old_position_index
                else:
                    dashboard.position_index = dashboards_og_positions[i]
                index += 1

        if new_pos_is_smaller:
            adjustDashboardPositions(position_index, old_position_index, 1)
        else:
            adjustDashboardPositions(old_position_index + 1, position_index + 1, -1)
        # place the current dashboard in the new position
        model.position_index = position_index
    dashboardDetails.update(_get_dashboard(model, request))
    return dashboardDetails


@InternalDashboardApp.view(model=Dashboard, request_method='DELETE')
def _delete_dashboard(model, _request):
    items = DashboardItem.KeywordQuery(dashboard_id=model.cdb_object_id).Execute()
    for item in items:
        item.Delete()
    model.Delete()
    return HTTPNoContent()


class DashboardCollection(object):
    PATH = '/dashboard_collection'

    @classmethod
    def get_dashboards(cls, manage_view=False):
        return Dashboard.get_dashboard_collection(manage_view)


def get_dashboard_collection(model, request, manage_view=False):
    dashboards = {dashboard.cdb_object_id: _get_dashboard(dashboard, request)
                  for dashboard in model.get_dashboards(manage_view)
                  if dashboard.CheckAccess('read')}

    return {
        '@id': request.link(model),
        'dashboard_collection': dashboards
    }


@InternalDashboardApp.path(model=DashboardCollection, path=DashboardCollection.PATH)
def _dashboard_collection_path():
    return DashboardCollection()


@InternalDashboardApp.json(model=DashboardCollection)
def _get_dashboard_collection(model, request):
    return get_dashboard_collection(model, request)


@InternalDashboardApp.json(model=DashboardCollection, name='manage_view')
def _get_dashboard_collection(model, request):
    return get_dashboard_collection(model, request, True)


@InternalDashboardApp.json(model=DashboardCollection,
                           request_method='POST',
                           path=DashboardCollection.PATH,
                           name='create')
def _post_dashboard(_, request):
    request_data = request.json
    name = request_data.get('name')
    dashboard = Dashboard.create_dashboard(name)
    return _get_dashboard(dashboard, request)


@InternalDashboardApp.json(model=DashboardCollection,
                           request_method='POST',
                           path=DashboardCollection.PATH,
                           name='copy')
def _post_dashboard(_, request):
    request_data = request.json
    source_id = request_data.get('source_id', None)

    source_dashboard = Dashboard.KeywordQuery(cdb_object_id=source_id).Execute()
    dashboard = source_dashboard[0].Copy(position_index=Dashboard.get_next_position(),
                                         subject_id=auth.persno,
                                         subject_type='Person',
                                         is_template=False
                                         )
    items = DashboardItem.KeywordQuery(dashboard_id=source_id)
    for item in items:
        item.Copy(dashboard_id=dashboard.cdb_object_id)

    return _get_dashboard(dashboard, request)


def update_dashboard(dashboard, dashboard_items, values):
    if dashboard.CheckAccess('write'):
        if not values['is_role_dashboard']:
            values['subject_id'] = auth.persno
            values['subject_type'] = 'Person'
        else:
            values['subject_type'] = 'Common Role'
        multi_lang = {d['attribute']: d['value']
                      for _, d in list(six.iteritems(values['name_multi_lang']))}
        values.update(multi_lang)
        attributes = ['position_index', 'is_template', 'cdb_module_id', 'subject_id',
                      'subject_type'] + list(multi_lang.keys())
        args = {a: values[a] for a in attributes if values[a] != dashboard[a]}
        dashboard.Update(**args)
        for item in dashboard_items:
            if item.CheckAccess('write'):
                attributes = ['cdb_module_id', 'subject_id', 'subject_type']
                args = {a: values[a] for a in attributes if values[a] != item[a]}
                item.Update(**args)
            else:
                return HTTPForbidden("The dashboard item cannot be edited by the current user")
    else:
        return HTTPForbidden("The dashboard cannot be edited by the current user")


def remove_dashboard(dashboard, dashboard_items):
    if dashboard.CheckAccess('delete'):
        dashboard.Delete()
        for item in dashboard_items:
            if item.CheckAccess('delete'):
                item.Delete()
            else:
                return HTTPForbidden("The dashboard item cannot be deleted by the current user")
    else:
        return HTTPForbidden("The dashboard cannot be deleted by the current user")


@InternalDashboardApp.json(model=DashboardCollection,
                           request_method='POST',
                           path=DashboardCollection.PATH,
                           name='update')
def _update_dashboards(_, request):
    request_data = request.json
    updated_dashboards = request_data.get('dashboards', {})
    removed_dashboards = request_data.get('removedDashboards', {})
    dashboard_ids = list(updated_dashboards.keys()) + list(removed_dashboards.keys())
    dashboards = Dashboard.KeywordQuery(cdb_object_id=dashboard_ids)
    items = DashboardItem.KeywordQuery(dashboard_id=dashboard_ids)

    for dashboard in dashboards:
        dashboard_id = dashboard['cdb_object_id']
        if dashboard.cdb_object_id in removed_dashboards:
            remove_dashboard(
                dashboard,
                [item for item in items if item['dashboard_id'] == dashboard_id]
            )
        elif dashboard.cdb_object_id in updated_dashboards:
            update_dashboard(
                dashboard,
                [item for item in items if item['dashboard_id'] == dashboard_id],
                updated_dashboards[dashboard_id]
            )

    return HTTPNoContent()


class DashboardItemCollection(object):
    def __init__(self, dashboard_id):
        self.dashboard_id = dashboard_id

    @property
    def items(self):
        return Dashboard.by_id(self.dashboard_id).Items


@InternalDashboardApp.path(model=DashboardItemCollection, path='{dashboard_id}/items')
def _item_collection_path(dashboard_id):
    return DashboardItemCollection(dashboard_id)


@InternalDashboardApp.json(model=DashboardItemCollection)
def _get_dashboard_item_collection(model, request):
    items = {item.cdb_object_id: _get_dashboard_item(item, request)
             for item in model.items if item.CheckAccess('read')}
    return {
        '@id': request.link(model),
        'items': items
    }


@InternalDashboardApp.view(model=DashboardItemCollection, request_method='POST')
def _post_dashboard_item_collection(model, request):
    request_data = request.json
    dashboard = Dashboard.ByKeys(model.dashboard_id)
    data = {
        'dashboard_id': model.dashboard_id,
        'widget_id': request_data['widget_id'],
        'xpos': request_data['xpos'],
        'ypos': request_data['ypos'],
        'collapsed': request_data.get('collapsed', 0),
        'settings': json.dumps(request_data.get('settings', {})),
        'subject_type': dashboard.subject_type,
        'subject_id': dashboard.subject_id,
    }
    item = _get_dashboard_item(DashboardItem.Create(**data), request)
    resp = Response(json_body=item,
                    status=HTTPCreated.code)
    resp.location = item['@id']
    return resp


@InternalDashboardApp.json(model=DashboardItemCollection, request_method='PUT')
def _put_dashboard_item_collection(model, request):
    positions = request.json.get('positions')
    if positions is None:
        return HTTPBadRequest(detail='Expected key "positions"')
    return _update_dashboard_item_collection(model, positions, request)


@InternalDashboardApp.path(model=DashboardItem, path='{dashboard_id}/items/{cdb_object_id}')
def _item_path(dashboard_id, cdb_object_id):
    return DashboardItem.by_id(dashboard_id, cdb_object_id)


@InternalDashboardApp.json(model=DashboardItem)
def _get_dashboard_item(model, request):
    return {
        '@id': request.link(model),
        'cdb_object_id': model.cdb_object_id,
        'widget_id': model.widget_id,
        'dashboard_id': model.dashboard_id,
        'xpos': model.xpos,
        'ypos': model.ypos,
        'collapsed': model.collapsed,
        'settings': json.loads(model.settings) if model.settings else {}
    }


@InternalDashboardApp.json(model=DashboardItem, request_method='PUT')
def _put_dashboard_item(model, request):
    """ API to modify a dashboard item. The attributes that can be changed are
        restricted, only those that are explicitly listed here.
    """
    updates = {}
    settings = request.json.get('settings')
    if settings is not None:
        updates['settings'] = json.dumps(settings)
    collapsed = request.json.get('collapsed')
    if collapsed is not None:
        updates['collapsed'] = collapsed
    if updates:
        model.Update(**updates)
    return _get_dashboard_item(model, request)


@InternalDashboardApp.view(model=DashboardItem, request_method='DELETE')
def _delete_dashboard_item(model, _request):
    model.Delete()
    # TODO: renumber other items in column? Return results from here, or ask
    # later from FE?
    return HTTPNoContent()


@InternalDashboardApp.view(model=DashboardItem, request_method='POST')
def _copy_dashboard_item(model, _request):
    model.Copy()
    return HTTPNoContent()
