#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from __future__ import absolute_import
import six
__revision__ = "$Id$"
from six.moves.urllib.parse import urlparse, urlunparse

from webob.exc import HTTPNotFound

from cs.platform.web.rest import get_collection_app
from cs.platform.web.rest.support import rest_name_for_class_name
from cs.platform.web.uisupport import get_ui_link
from cs.web.components.ui_support.utils import (get_handles_from_restitems,
                                                get_handles_from_restitems_for_class)
from cdb import auth, transactions
from cdb.objects import Object
from cdb.objects.iconcache import IconCache
from cdb.platform.mom import getObjectHandlesFromRESTIDs

from .model import FavoriteCollection, Favorite
from .main import FavoritesApp


def render_favorite_item(request, item, item_handle, collection_app):
    title = item.title
    icon_url = item.icon_url
    frontend_url = item.frontend_url
    rest_url = ''
    classname = ''
    rootname = ''
    ref_object_id = ''

    if item_handle:
        if not title:
            title = item_handle.getDesignation()
        if not icon_url:
            icon_id = item_handle.getClassDef().getObjectIconId()
            icon_url = IconCache.getIcon(icon_id, accessor=item_handle)
        if not frontend_url:
            frontend_url = get_ui_link(request, item_handle) or ""
            # make url root relative
            frontend_url = urlunparse(('', '') + urlparse(frontend_url)[2:])
        ref_object_id = item.ref_object_id
        rest_url = request.class_link(Object,
                                      {'rest_name': item.rest_name,
                                       'keys': item.rest_id},
                                      app=collection_app)
        classdef = item_handle.getClassDef()
        classname = classdef.getClassname()
        rootname = classdef.getRootClass().getClassname()
    return {
        '@id': request.link(item),
        'title': title,
        'frontend_url': frontend_url,
        'rest_url': six.moves.urllib.parse.unquote(rest_url),
        'icon_url': icon_url,
        'rest_name': item.rest_name,
        'classname': classname,
        'rootclass': rootname,
        'ref_object_id': ref_object_id
    }


def _with_dead_handles_removed(items_with_handles):
    """Yields the provided iterable without dead handles filtered out,
    and corresponding entries removed from db."""

    for item, item_handle in items_with_handles:
        if not item_handle:
            # If we don't get a handle for an object we try to get it
            # again without access checks to avoid deleting items
            # which still exists in DB, but just (temporary) missing
            # the required rights (E049751)
            try:
                try:
                    if len(getObjectHandlesFromRESTIDs(item.rest_name, [item.rest_id], check_access=False)) == 0:
                        item.Delete()
                except ValueError:
                    # Fail safe if rest id of the class changed in the object is not
                    # constructable (maybe temporary, so don't delete it).
                    pass
            except TypeError:
                item.Delete()
        else:
            yield item, item_handle


@FavoritesApp.json(model=FavoriteCollection)
def favorite_collection_get(model, request):
    collection_app = get_collection_app(request)
    items = model.get_favorites()
    handles = (get_handles_from_restitems_for_class(items, model.classname)
               if model.classname
               else get_handles_from_restitems(items))
    if model.as_table is None:
        valid_items = _with_dead_handles_removed(six.moves.zip(items, handles))
        favorites = [render_favorite_item(request, item, item_handle, collection_app)
                     for (item, item_handle) in valid_items]
        # Ignore entries without frontent_url
        result = {'@id': request.link(model),
                  'favorites': [fav for fav in favorites if fav.get("frontend_url")]
                  }
    else:
        result = {'@id': request.link(model)}
        valid_handles = [hndl for hndl in handles if hndl is not None]
        result.update(model.getTableResult(valid_handles).get_rest_data(request))
    return result


@FavoritesApp.json(model=FavoriteCollection, request_method='POST')
def favorite_collection_post(self, request):
    json = request.json
    title = json.get('title', '')
    icon_url = json.get('icon_url', '')
    rest_name = rest_name_for_class_name(json.get('classname', ''))
    rest_id = json.get('rest_id', '')
    frontend_url = json.get('frontend_url', '')
    ref_object_id = json.get('ref_object_id', '')
    if rest_name and rest_id:
        frontend_url = ''

    # make url root relative
    frontend_url = urlunparse(('', '') + urlparse(frontend_url)[2:])
    icon_url = urlunparse(('', '') + urlparse(icon_url)[2:])

    args = {'title': title,
            'frontend_url': frontend_url,
            'icon_url': icon_url,
            'rest_name': rest_name,
            'rest_id': rest_id,
            'ref_object_id': ref_object_id}
    args.update(Favorite.MakeChangeControlAttributes())
    with transactions.Transaction():
        result = Favorite.Create(**args)
        # Try to determine if the just inserted entry is a duplicate (either the
        # same URL or the same REST id), and if so, roll back the transaction and
        # return an existing entry. Don't check beforehand, because that would
        # introduce a race condition.
        qry_args = {'cdb_cpersno': auth.persno}
        if frontend_url:
            qry_args.update(frontend_url=frontend_url)
        else:
            qry_args.update(rest_name=rest_name, rest_id=rest_id)
        favs = (Favorite.KeywordQuery(**qry_args)
                .Query("cdb_object_id != '%s'" % result.cdb_object_id)
                .Execute())
        if favs:
            result = favs[0]
            raise transactions.Rollback()
    return request.view(result)


@FavoritesApp.json(model=Favorite)
def favorite_get(self, request):
    handle = Favorite.get_handle(self)
    if not handle:
        self.Delete()
        return HTTPNotFound()

    collection_app = get_collection_app(request)
    return render_favorite_item(request, self, handle, collection_app)


@FavoritesApp.json(model=Favorite, request_method='PUT')
def favorite_put(self, request):
    title = request.json.get('title', '')
    args = {'title': title}
    ccas = Favorite.MakeChangeControlAttributes()
    del ccas['cdb_cdate']
    del ccas['cdb_cpersno']
    args.update(ccas)
    self.Update(**args)
    return request.view(self)


@FavoritesApp.json(model=Favorite, request_method='DELETE')
def favorite_delete(self, request):
    self.Delete()
    return {}
