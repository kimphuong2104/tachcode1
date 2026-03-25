#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Access to implicitly stored UI settings per user. The idea is that the settings
will be loaded all at once, and are cached in the FE, so there is no need to GET
single settings.
"""

from __future__ import absolute_import

import json
from collections import defaultdict

import six
from webob.exc import HTTPNoContent

from cdb import auth
from cdb import sqlapi
from cdb import util
from cdb.objects import Object
from cdb.transactions import Transaction

from . import App, get_uisupport_app

__revision__ = "$Id$"


class UISettings(Object):
    """ UISettings are used to store component properties that can be modified by
        the user through direct manipulation of the UI. Therefore, a relatively
        high write rate is to be expected, in comparison to explicitely set values.

        The form of the settings is defined by the frontend, and hence unknown here.
        It is stored in the form of JSON strings. These strings may get very long,
        so there is a json_value attribute directly in the main DB relation, as
        well as a long text attribute that will be used when the value is too long.
    """
    __maps_to__ = 'csweb_ui_settings'
    __classname__ = 'csweb_ui_settings'

    TextFieldName = 'csweb_ui_settings_txt'
    _InlineTextLength = None

    @classmethod
    def inline_text_length(cls):
        if cls._InlineTextLength is None:
            tbl = util.tables[cls.__maps_to__]
            cls._InlineTextLength = tbl.column("json_value").length()
        return cls._InlineTextLength

    @classmethod
    def get_short_and_long_text(cls, value):
        s = json.dumps(value)
        if len(s) >= cls.inline_text_length():
            return ('', s)
        else:
            return (s, None)

    def get_value(self):
        s = self.json_value if self.json_value else self.GetText(self.TextFieldName)
        return json.loads(s)

    @classmethod
    def _write_long_text(cls, persno, component, propname, text):
        util.text_write(cls.TextFieldName,
                        ['persno', 'component', 'property'],
                        [persno, component, propname],
                        text)

    @classmethod
    def _delete_long_text(cls, persno, component, propname):
        cls._write_long_text(persno, component, propname, '')

    @classmethod
    def set_ui_settings(cls, request_data):
        """ Stores the given settings for the current user. Expects a JSON encoded
            dict of dicts (component / property -> value) with the data to store.
        """
        # The implementation here assumes that normally only one or very few values
        # will be set, and that furthermore the keys will for the most part already
        # exist, so that an INSERT is needed less frequently than an UPDATE.
        # Using sqlapi directly avoids a SELECT that would be needed for the objects
        # framework.
        persno = sqlapi.quote(auth.persno)
        with Transaction():
            for component, props in six.iteritems(request_data):
                for propname, value in six.iteritems(props):
                    short_val, long_val = cls.get_short_and_long_text(value)
                    sql = ("%s SET json_value = '%s'"
                           " WHERE persno = '%s'"
                           "   AND component = '%s'"
                           "   AND property = '%s'") % (cls.__maps_to__,
                                                        sqlapi.quote(short_val),
                                                        persno,
                                                        sqlapi.quote(component),
                                                        sqlapi.quote(propname))
                    cnt = sqlapi.SQLupdate(sql)
                    if cnt == 0:
                        sql = ("INTO %s"
                               " (persno, component, property, json_value)"
                               " VALUES ('%s', '%s', '%s', '%s')") % (cls.__maps_to__,
                                                                      persno,
                                                                      sqlapi.quote(component),
                                                                      sqlapi.quote(propname),
                                                                      sqlapi.quote(short_val))
                        sqlapi.SQLinsert(sql)
                    if long_val is None:
                        cls._delete_long_text(persno, component, propname)
                    else:
                        cls._write_long_text(persno, component, propname, long_val)

    @classmethod
    def replace_component_settings(cls, component, request_data):
        """ Overwrite all settings for a single component with the request content.
            Expects a JSON body with a dict (property -> value).
        """
        persno = sqlapi.quote(auth.persno)
        component = sqlapi.quote(component)
        with Transaction():
            for tblname in (cls.__maps_to__, cls.TextFieldName):
                sqlapi.SQLdelete("FROM %s WHERE persno = '%s' AND component = '%s'"
                                 % (tblname, persno, component))
            for propname, value in six.iteritems(request_data):
                short_val, long_val = cls.get_short_and_long_text(value)
                sql = ("INTO %s"
                       " (persno, component, property, json_value)"
                       " VALUES ('%s', '%s', '%s', '%s')") % (cls.__maps_to__,
                                                              persno, component,
                                                              sqlapi.quote(propname),
                                                              sqlapi.quote(short_val))
                sqlapi.SQLinsert(sql)
                if long_val is not None:
                    cls._write_long_text(persno, component, propname, long_val)

    @classmethod
    def delete_component_settings(cls, component):
        """ Delete all settings for a component and all its subcomponents
        """
        persno = sqlapi.quote(auth.persno)
        component = sqlapi.quote(component)
        with Transaction():
            for tblname in (cls.__maps_to__, cls.TextFieldName):
                sqlapi.SQLdelete("FROM %s"
                                 " WHERE persno = '%s'"
                                 "   AND (component = '%s' OR component LIKE '%s/%%')"
                                 % (tblname, persno, component, component))


class UISettingsModel(object):
    """ Just here for morepath to use as model class
    """
    @classmethod
    def link(cls, request):
        return request.class_link(UISettingsModel, app=get_uisupport_app(request))


@App.path(path='/ui_settings', model=UISettingsModel)
def _ui_settings():
    return UISettingsModel()


@App.json(model=UISettingsModel, request_method='GET')
def _get_ui_settings(_model, _request):
    """ Returns all stored settings for the current user
    """
    result = defaultdict(dict)
    settings = UISettings.KeywordQuery(persno=auth.persno)
    for s in settings:
        result[s.component][s.property] = s.get_value()
    return result


@App.view(model=UISettingsModel, request_method='POST')
def _set_ui_settings(_model, request):
    UISettings.set_ui_settings(request.json)
    return HTTPNoContent()


class ComponentSettingsModel(object):
    def __init__(self, component):
        self.component = component


@App.path(path='/ui_settings/{component}', model=ComponentSettingsModel, absorb=True)
def _component_settings(component, absorb):
    compName = "%s/%s" % (component, absorb) if absorb else component
    return ComponentSettingsModel(compName)


@App.view(model=ComponentSettingsModel, request_method='POST')
def _replace_component_settings(model, request):
    UISettings.replace_component_settings(model.component, request.json)
    return HTTPNoContent()


@App.view(model=ComponentSettingsModel, request_method='DELETE')
def _delete_component_settings(model, _request):
    UISettings.delete_component_settings(model.component)
    return HTTPNoContent()
