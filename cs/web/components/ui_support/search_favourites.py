#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Objects classes and morepath views to manage search favourites.
"""

from __future__ import absolute_import
import six
__revision__ = "$Id: search_favourites.py 211365 2020-05-08 09:30:17Z gwe $"

import itertools
from webob.exc import HTTPNoContent, HTTPForbidden

from cdb import auth
from cdb import sig
from cdb import sqlapi
from cdb import transactions
from cdb import constants
from cdb import ElementsError
from cdb import i18n
from cdb.platform import gui
from cdb.platform.mom.entities import CDBClassDef, Entity
from cdb.platform.mom.operations import OperationInfo
from cdb.util import get_roles, PersonalSettings, get_label
from cdb.objects import Object, Reference_N, Forward
from cdb.platform.mom import fields
from cdb.comparch import modules
from cs.platform.web.uisupport import App as UI_SupportApp, get_uisupport
from cs.platform.web.rest.support import getRESTVisibleClasses
from cs.web.components.history.main import get_history_app
from cs.web.components.history.model import HistoryCollection
from cs.web.components.favorites.main import get_favorites_app
from cs.web.components.favorites.model import FavoriteCollection

SearchFavourite = Forward(__name__ + ".SearchFavourite")
SearchFavouriteParam = Forward(__name__ + ".SearchFavouriteParam")

_SETTINGS_KEY = 'cs.web.search_favourite'

# The stable object id that is used for the special search favourite "recently
# used"
_LAST_OBJECTS_FAVOURITE_ID = '018f6d70-b0a8-11e6-9207-005056c00008'

# The stable object id that is used for the special search favourite "my favorites"
_OBJECT_FAVORITES_FAVOURITE_ID = 'c865c307-6a24-4861-b9e1-fdddde507542'


class SearchFavourite(Object):
    __maps_to__ = "csweb_search_favourites"
    __classname__ = "csweb_search_favourites"

    Params = Reference_N(SearchFavouriteParam,
                         SearchFavouriteParam.favourite_id == SearchFavourite.cdb_object_id)

    @classmethod
    def LocalNameAttr(cls):
        return cls.name.getLanguageField().name

    @classmethod
    def MyFavourites(cls):
        persno = auth.persno
        pers_clause = "subject_type = 'Person' AND subject_id = '%s'" % sqlapi.quote(persno)
        my_roles = get_roles("GlobalContext", "", persno)
        role_clause = ("subject_type = 'Common Role' AND subject_id in (%s)"
                       % (", ".join(["'%s'" % sqlapi.quote(r) for r in my_roles])))
        qry = "((%s) OR (%s))" % (pers_clause, role_clause)
        return cls.Query(qry)

    def is_readonly(self):
        return self.subject_type != 'Person'

    def to_json(self, params, request):
        """ Return a structure suitable for conversion to JSON. Note that the
            actual position values of the parameters are not transmitted, but
            the order is preserved as the order in the list.
        """
        def _get_value(param):
            result = param.value
            if result == "$(persno)":
                result = auth.persno
            elif result == "$(name)":
                result = auth.name
            return result

        return {'@id': request.link(self),
                'cdb_object_id': self.cdb_object_id,
                'name': self.name,
                'name_multi_lang': {a.getIsoLang(): {'attribute': a.getName(), 'value': self[a.getName()]}
                                    for ml in CDBClassDef('csweb_search_favourites').getMultiLangAttributeDefs()
                                    for a in ml.getLanguageAttributeDefs()
                                    if a.getIsoLang() in i18n.getActiveGUILanguages()
                                    if ml.getName() == 'name'},
                'classname': self.classname,
                'readonly': self.is_readonly(),
                'params': [{'attribute': param.attribute,
                            'value': _get_value(param)}
                           for param in sorted(params, key=lambda p: p.position or -1)],
                'subject_id': self.subject_id,
                'pos': self.pos,
                'onlyVisibleForAdmin': self not in self.MyFavourites(),
                'cdb_module_id': self.cdb_module_id
                }

    def update_from_request(self, request):
        """ Update this favourite from an HTTP PUT request.
        """
        request_data = request.json
        attrs = {item['attribute']: item['value']
                 for _, item in six.iteritems(request_data['name_multi_lang'])}
        cdb_module_id = request_data['cdb_module_id']
        try:
            modules.get_module_dir(cdb_module_id)
        except ValueError:
            cdb_module_id = self.cdb_module_id if cdb_module_id else None
        attrs.update({"pos": request_data['pos'],
                      "subject_id": request_data['subject_id'] if request_data['readonly'] else auth.persno,
                      "subject_type": 'Common Role' if request_data['readonly'] else 'Person',
                      "cdb_module_id": cdb_module_id})
        # Only update if something has changed
        for attr, value in attrs.items():
            if self[attr] != value:
                self.Update(**attrs)
                break
        # Just drop the params and create new entries from the request. This is
        # not performance critical, so avoid complex logic to determine the
        # minimal set of updates,
        new_params = self.Params
        if request_data['update_params']:
            self.Params.Delete()
            new_params = SearchFavouriteParam.ParamsFromData(self.cdb_object_id,
                                                             request_data['params'])
        else:
            for param in new_params:
                if param.cdb_module_id != cdb_module_id:
                    param.cdb_module_id = cdb_module_id
        return self.to_json(new_params, request)


class SearchFavouriteParam(Object):
    __maps_to__ = "csweb_search_fav_params"
    __classname__ = "csweb_search_fav_params"

    @classmethod
    def ParamsFromData(cls, favourite_id, request_data):
        return [SearchFavouriteParam.Create(favourite_id=favourite_id,
                                            attribute=param['attribute'],
                                            value=param['value'],
                                            position=pos)
                for (param, pos) in six.moves.zip(request_data, itertools.count())]

    def _preset_position(self, ctx):
        if self.favourite_id:
            data = sqlapi.SQLselect("max(position) FROM "
                                    "csweb_search_fav_params "
                                    "WHERE favourite_id = '%s'" %
                                    (sqlapi.quote(self.favourite_id)))
            if data and sqlapi.SQLrows(data):
                new_pos = sqlapi.SQLinteger(data, 0, 0) + 10
                ctx.set("position", new_pos)


    event_map = {(("create", "copy"), "pre_mask"): "_preset_position"}


@sig.connect(fields.DDField, "query_catalog", "pre")
def _query_attribute_restrict_class(cls, ctx):
    if ctx.catalog_name != 'SearchFavouriteAttr' or ctx.catalog_requery:
        return

    fav_id = getattr(ctx.catalog_invoking_dialog, "favourite_id")
    if fav_id:
        fav = SearchFavourite.ByKeys(fav_id)
        if fav:
            if fav.classname:
                classnames = [fav.classname]
                try:
                    cdef = CDBClassDef(fav.classname)
                    for bc in cdef.getBaseClassNames():
                        classnames.append(bc)
                    ctx.set("classname", " or ".join(classnames))
                except ElementsError:
                    pass


class SearchFavouriteAttrCatalog(gui.CDBCatalog):
    """
    Catalog derived class to handle the selection that needs the attribute
    identifier instead of the field_name.
    """
    def handleSelection(self, selected_objects):
        if selected_objects:
            try:
                cdef = CDBClassDef(selected_objects[0].classname)
                attr_id = cdef.getAttrIdentifier(selected_objects[0].field_name)
                self.setValue("attribute", attr_id)
            except ElementsError:
                self.setValue("attribute", selected_objects[0].field_name)


class SearchFavouriteCollection(object):
    def __init__(self, classname):
        self.classname = classname

    def make_link(self, request):
        return request.link(self, app=get_uisupport(request))

    @classmethod
    def template_link(cls, request):
        return request.class_link(SearchFavouriteCollection,
                                  {"classname": "${classname}"},
                                  app=get_uisupport(request))

    @classmethod
    def add_special_favourites(cls, classname, result, request):
        """ Add entries that should appear as a search favourite in the UI, but
            is defined by special logic in the backend. The UI looks at the
            `resultLink` key to distinguish between the normal and the special
            entries, and to retrieve the objects that correspond to the search.
        """

        # A search favourite that returns objects from the history
        last_objects = {
            'cdb_object_id': _LAST_OBJECTS_FAVOURITE_ID,
            'name': get_label('web.favorites.history'),
            'iconName': 'csweb_history',
            'classname': classname,
            'readonly': True,
            'params': [],
            'resultLink': request.class_link(HistoryCollection,
                                             {'classname': classname,
                                              'as_table': ''},
                                             app=get_history_app(request))
        }
        result.append(last_objects)

        # A search favourite that returns objects that the user stored as favourites
        favorite_objects = {
            'cdb_object_id': _OBJECT_FAVORITES_FAVOURITE_ID,
            'name': get_label('web.favorites.favorites'),
            'iconName': 'csweb_favorite_added',
            'classname': classname,
            'readonly': True,
            'params': [],
            'resultLink': request.class_link(FavoriteCollection,
                                             {'classname': classname,
                                              'as_table': ''},
                                             app=get_favorites_app(request))
        }
        result.append(favorite_objects)
        return result

    def to_json(self, request):
        favorites = SearchFavourite.MyFavourites().KeywordQuery(
            classname=self.classname,
            order_by=["pos"]
        )
        fav_ids = [f.cdb_object_id for f in favorites]
        if fav_ids:
            params = SearchFavouriteParam.KeywordQuery(favourite_id=fav_ids)
            fav_list = [f.to_json([p for p in params
                                   if p.favourite_id == f.cdb_object_id],
                                  request)
                        for f in favorites]
        else:
            fav_list = []
        fav_list = self.add_special_favourites(self.classname, fav_list, request)
        return {
            'favourites': fav_list,
            'classname': self.classname,
            'classDesignation': CDBClassDef(self.classname).getDesignation(),
            'defaultFavouriteId':
                PersonalSettings().getValueOrDefault(_SETTINGS_KEY,
                                                     self.classname,
                                                     None)
        }

    def new_favourite(self, request):
        request_data = request.json
        data = {'classname': self.classname,
                'subject_type': 'Person',
                'subject_id': auth.persno}
        lang_attr = {a.getIsoLang(): a.getName()
                     for ml in CDBClassDef("csweb_search_favourites").getMultiLangAttributeDefs()
                     for a in ml.getLanguageAttributeDefs()
                     if a.getIsoLang() in i18n.getActiveGUILanguages()
                     if ml.getName() == 'name'}
        for lang, value in six.iteritems(request_data['name_multi_lang']):
            data[lang_attr[lang]] = value
        with transactions.Transaction():
            new_fav = SearchFavourite.Create(**data)
            new_params = SearchFavouriteParam.ParamsFromData(new_fav.cdb_object_id,
                                                             request_data['params'])
            return new_fav.to_json(new_params, request)


class AllSearchFavouriteCollection(object):

    def _to_json_by_classname(self, favourites, params, classname, request):
        class_favourites = [
            f.to_json([p for p in params if p.favourite_id == f.cdb_object_id], request)
            for f in favourites if f.classname == classname]
        class_favourites = SearchFavouriteCollection.add_special_favourites(classname,
                                                                            class_favourites,
                                                                            request)
        return {
            'favourites': class_favourites,
            'classname': classname,
            'classDesignation': CDBClassDef(classname).getDesignation(),
            'defaultFavouriteId':
                PersonalSettings().getValueOrDefault(_SETTINGS_KEY,
                                                     classname,
                                                     None)
        }

    # Cache for rest enabled classes, or classes with a configured UI name, that
    # have the search operation allowed
    _Searchable_REST_Activ_Class_Cache = None

    @classmethod
    def get_searchable_classnames(cls):
        if cls._Searchable_REST_Activ_Class_Cache is None:

            def filter_name(cls_name):
                search_config = OperationInfo(cls_name, constants.kOperationSearch)
                return search_config and search_config.offer_in_webui()

            candidates = set(getRESTVisibleClasses()).union(
                Entity.Query("ui_name != '' AND ui_name is NOT NULL").classname
            )
            cls._Searchable_REST_Activ_Class_Cache = [cls_name
                                                      for cls_name in candidates
                                                      if filter_name(cls_name)]
        return cls._Searchable_REST_Activ_Class_Cache

    def to_json(self, request):
        classnames = self.get_searchable_classnames()
        favorites = SearchFavourite.MyFavourites()
        fav_ids = [f.cdb_object_id for f in favorites]
        params = SearchFavouriteParam.KeywordQuery(favourite_id=fav_ids)
        return [self._to_json_by_classname(favorites, params, classname, request)
                for classname in classnames]

    def make_link(self, request):
        return request.link(self, app=get_uisupport(request))


class PredefinedSearchFavourites(object):
    def __init__(self, classname):
        self.classname = classname

    def make_link(self, request):
        return request.link(self, app=get_uisupport(request))

    @classmethod
    def template_link(cls, request):
        return request.class_link(PredefinedSearchFavourites,
                                  {"classname": "${classname}"},
                                  app=get_uisupport(request))

    def to_json(self, request):
        favourites = SearchFavourite.KeywordQuery(subject_type="Common Role", classname=self.classname)
        result = []
        for f in favourites:
            params = SearchFavouriteParam.KeywordQuery(favourite_id=f.cdb_object_id)
            result.append(f.to_json(params, request))
        return {
            'favourites': result
        }


@UI_SupportApp.path(path="search_favourites/",
                    model=AllSearchFavouriteCollection)
def _all_search_favourites_path():
    return AllSearchFavouriteCollection()


@UI_SupportApp.json(model=AllSearchFavouriteCollection)
def _get_all_search_favourites(model, request):
    return model.to_json(request)


@UI_SupportApp.path(path="search_favourites/by_class/{classname}",
                    model=SearchFavouriteCollection)
def _search_favourites_path(classname):
        return SearchFavouriteCollection(classname)


@UI_SupportApp.json(model=SearchFavouriteCollection)
def _get_search_favourites(model, request):
    return model.to_json(request)


@UI_SupportApp.json(model=SearchFavouriteCollection, request_method='POST')
def _new_search_favourite(model, request):
    return model.new_favourite(request)


@UI_SupportApp.json(model=SearchFavouriteCollection, request_method='PUT')
def _set_default_favourite(model, request):
    request_data = request.json
    defaultFavouriteId = request_data.pop('defaultFavouriteId', None)
    if defaultFavouriteId is None:
        del PersonalSettings()[_SETTINGS_KEY, model.classname]
    else:
        PersonalSettings()[_SETTINGS_KEY, model.classname] = defaultFavouriteId
    return {'defaultFavouriteId': defaultFavouriteId}


@UI_SupportApp.path(path="search_favourites/by_id/{cdb_object_id}",
                    model=SearchFavourite)
def _search_favourite_path(cdb_object_id):
    # make sure the caller can't see other users favorites
    if not OperationInfo('csweb_search_favourites', constants.kOperationNew):
        favourites = SearchFavourite.MyFavourites()
    else:
        favourites = SearchFavourite
    result = favourites.KeywordQuery(cdb_object_id=cdb_object_id).Execute()
    return result[0] if result else None


@UI_SupportApp.json(model=SearchFavourite)
def _get_search_favourite(model, request):
    return model.to_json(model.Params, request)


@UI_SupportApp.json(model=SearchFavourite, request_method='PUT')
def _change_search_favourite(model, request):
    if model.is_readonly() and not OperationInfo('csweb_search_favourites', constants.kOperationNew):
        # may only change own favourites without administrator rights
        return HTTPForbidden(detail="Only the callers own favourites may be changed")
    with transactions.Transaction():
        return model.update_from_request(request)


@UI_SupportApp.view(model=SearchFavourite, request_method='DELETE')
def _delete_search_favourite(model, _request):
    if model.is_readonly() and not OperationInfo('csweb_search_favourites', constants.kOperationNew):
        # may only delete own favorites without administrator rights
        return HTTPForbidden(detail="Only the callers own favourites may be deleted")
    with transactions.Transaction():
        model.Params.Delete()
        model.Delete()
    return HTTPNoContent()


@UI_SupportApp.path(path="all_predefined_search_favourites/{classname}",
                    model=PredefinedSearchFavourites)
def _search_favourite_path(classname):
    if not OperationInfo('csweb_search_favourites', constants.kOperationNew):
        raise HTTPForbidden(detail="Querying the predefined search favorites is not allowed")
    return PredefinedSearchFavourites(classname)


@UI_SupportApp.json(model=PredefinedSearchFavourites)
def _get_all_predefined_search_favourites(model, request):
    return model.to_json(request)
