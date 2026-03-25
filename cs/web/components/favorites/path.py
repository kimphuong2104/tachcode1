#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Morepath path declaration for Web UI object favorites
"""

from __future__ import absolute_import
__revision__ = "$Id$"

from webob.exc import HTTPBadRequest

from cdb import auth
from .main import FavoritesApp
from .model import Favorite, FavoriteCollection


@FavoritesApp.path(model=FavoriteCollection, path='')
def get_favorite_collection(classname=None, as_table=None):
    if as_table is not None and not classname:
        return HTTPBadRequest(detail='as_table not allowed without classname')
    return FavoriteCollection(classname, as_table)


@FavoritesApp.path(model=Favorite, path='{cdb_object_id}')
def get_favorite(cdb_object_id):
    result = Favorite.ByKeys(cdb_object_id=cdb_object_id)
    # we cannot access other people's favorite
    if result is None or result.cdb_cpersno != auth.persno:
        return None
    return result
