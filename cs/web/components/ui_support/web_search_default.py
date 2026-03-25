# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import
import json
from webob.exc import HTTPForbidden

from cdb import i18n
from cdb import constants
from cdb.platform.mom.entities import CDBClassDef
from cdb.platform.mom.operations import OperationInfo
from cdb.util import PersonalSettings
from cdb.objects.core import DataDictionary
from cs.platform.core.settings import DefaultSetting
from . import App, get_uisupport_app


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class SearchDefaultsModel(object):

    def __init__(self, class_name):
        self.key = 'web.search.default'
        self.class_def = CDBClassDef(class_name)

    @classmethod
    def template_link(cls, request):
        return request.class_link(SearchDefaultsModel,
                                  {"class_name": "${class_name}"},
                                  app=get_uisupport_app(request))

    def get_setting(self, class_name):
        return PersonalSettings().getValueOrDefault(self.key, class_name, None)

    def set_value(self, class_name, search_defaults):
        if not OperationInfo('cdb_setting', constants.kOperationNew):
            raise HTTPForbidden(detail="Storing the search defaults is not allowed")
        else:
            setting = DefaultSetting.ByKeys(setting_id=self.key,
                                            setting_id2=class_name,
                                            role_id='public')
            if setting is None:
                return DefaultSetting.Create(setting_id=self.key,
                                             setting_id2=class_name,
                                             default_val=search_defaults,
                                             role_id='public',
                                             readonly=True,
                                             store_usr_val=False,
                                             cdb_module_id=DataDictionary().getClassRecord(class_name)['cdb_module_id'])
            else:
                return setting.Update(default_val=search_defaults)

    def get_attributes(self, class_name):
        search_defaults = self.get_setting(class_name)
        if search_defaults is not None:
            if search_defaults == "ALL":
                attr_names = self.get_non_language_attr_names()
            else:
                attr_names = json.loads(search_defaults)
            attr_ids = [self.get_attribute_identifier(attr_name) for attr_name in attr_names]
            return [attr_id for attr_id in attr_ids if attr_id]
        else:
            return search_defaults

    def get_non_language_attr_names(self):
        lang_attr_ids = set(a.getIdentifier()
                            for ml in self.class_def.getMultiLangAttributeDefs()
                            for a in ml.getLanguageAttributeDefs())
        return [attr.getName()
                for attr in self.class_def.getAttributeDefs()
                if attr.getIdentifier() not in lang_attr_ids]

    def get_attribute_identifier(self, attr):
        ml_attrs = self.class_def.getMultiLangAttributeDefs()
        ml_attr_names = [ml.getName() for ml in ml_attrs]
        if attr in ml_attr_names:
            lang = i18n.default()
            ml_attr = ml_attrs[ml_attr_names.index(attr)]
            result = {la.getIsoLang(): la.getName() for la in ml_attr.getLanguageAttributeDefs()}
            attr = result[lang]
        result = self.class_def.getAttrIdentifier(attr)
        if result:
            return result
        elif attr == constants.kArgumentTextIndex and not self.class_def.is_indexed():
            return None
        else:
            # only works for attributes with the prefix "cdb::argument."
            return attr


@App.path(path='/web_search_default/{class_name}', model=SearchDefaultsModel)
def _web_search_defaults(class_name):
    return SearchDefaultsModel(class_name)


@App.json(model=SearchDefaultsModel, request_method='GET')
def _get_web_search_defaults(self, _request):
    for class_def in (self.class_def,) + self.class_def.getBaseClasses():
        setting = self.get_attributes(class_def.getClassname())
        if setting is not None:
            return setting
    return []


@App.json(model=SearchDefaultsModel, request_method='POST')
def _set_web_search_defaults(self, request):
    try:
        self.set_value(self.class_def.getClassname(), json.dumps(request.json))
    except RuntimeError:
        raise HTTPForbidden()
    return request.view(self)
