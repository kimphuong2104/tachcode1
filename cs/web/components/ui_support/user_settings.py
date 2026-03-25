# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import
import json
from webob.exc import HTTPForbidden

from cdb.util import PersonalSettings
from . import App, get_uisupport_app

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class SettingsModel(object):

    def __init__(self, id1, id2):
        self.id1 = id1
        self.key1 = 'cs.webcomponents.{0}'.format(id1)
        self.id2 = id2

    @classmethod
    def template_link(cls, request):
        return request.class_link(SettingsModel,
                                  {"id1": "${id1}", "id2": "${id2}"},
                                  app=get_uisupport_app(request))

    def get_setting(self):
        return PersonalSettings().getValueOrDefault(self.key1, self.id2, '""')

    def set_value(self, value):
        PersonalSettings()[self.key1, self.id2] = value

    def delete(self):
        del PersonalSettings()[self.key1, self.id2]


@App.path(path='/user_settings/{id1}/{id2}', model=SettingsModel)
def _user_setting(id1, id2):
    return SettingsModel(id1, id2)


@App.json(model=SettingsModel, request_method='GET')
def _get_user_setting(self, _request):
    return json.loads(self.get_setting())


@App.json(model=SettingsModel, request_method='POST')
def _set_user_setting(self, request):
    try:
        self.set_value(json.dumps(request.json))
    except RuntimeError:
        raise HTTPForbidden()
    return request.view(self)


@App.view(model=SettingsModel, request_method='DELETE')
def _del_user_setting(self, _request):
    try:
        self.delete()
    except RuntimeError:
        raise HTTPForbidden()
