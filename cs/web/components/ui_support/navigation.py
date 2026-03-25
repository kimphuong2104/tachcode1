#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import

import cdbwrapc

from webob.exc import HTTPNotFound
from cdb import auth, ue, util
from cdb.objects import Object, Forward, Reference_1, Reference_N
from cdb.objects.iconcache import IconCache
from cdb.platform.mom.entities import CDBClassDef
from cs.web.components.favorites.main import get_favorites_app
from cs.web.components.favorites.model import FavoriteCollection
from cs.web.components.ui_support.search_favourites import SearchFavouriteCollection
from cs.web.components.ui_support.utils import ui_name_for_class, get_classname_from_app_link

from . import App
from .navigation_tree import NavigationTreeContent, NavigationTreeSubmenuContent

PrimaryNavigation = Forward(__name__ + ".PrimaryNavigation")
PrimaryNavigationOwner = Forward(__name__ + ".PrimaryNavigationOwner")


class PrimaryNavigation(Object):
    __maps_to__ = 'csweb_primary_nav'
    __classname__ = 'csweb_primary_nav'

    Owners = Reference_N(PrimaryNavigationOwner,
                         PrimaryNavigationOwner.nav_object_id == PrimaryNavigation.cdb_object_id)

    def _check_config(self, ctx):
        if not ctx.dialog['app_link'] and not ctx.dialog['conf_link']:
            raise ue.Exception("csweb_nav_config_invalid")

    @classmethod
    def EntriesForCurrentUser(cls):
        roles = set(util.get_roles("GlobalContext", "", auth.persno))
        owners = set([(pno.nav_object_id)
                      for pno in PrimaryNavigationOwner.KeywordQuery(role_id=roles)])

        result = (
            [entry for entry in cls.Query().Execute() if entry.cdb_object_id in owners]
        )
        return sorted(result, key=lambda k: k['pos'])

    event_map = {
        (("modify", "create", "copy"), "pre"): "_check_config"
    }


class PrimaryNavigationOwner(Object):
    __maps_to__ = 'csweb_primary_nav_owner'
    __classname__ = 'csweb_primary_nav_owner'

    Position = Reference_1(PrimaryNavigation,
                           PrimaryNavigationOwner.nav_object_id == PrimaryNavigation.cdb_object_id)


class NavigationContent(object):

    def __init__(self, section_id="primary_master"):
        self.section_id = section_id

    def get_entries(self):
        if self.section_id == "primary_master":
            entries = PrimaryNavigation.EntriesForCurrentUser()
            result = []
            for entry in entries:
                result.append({
                    "is_direct_link": bool(entry.app_link and not entry.conf_link),
                    "section": entry.nav_section,
                    "title": cdbwrapc.get_label(entry.ausgabe_label),
                    "app_link": entry.app_link,
                    "conf_link": entry.conf_link,
                    "imageSrc": IconCache.getIcon(entry.cdb_icon_id),
                    "tooltip": cdbwrapc.get_label(entry.tooltip),
                    "className": get_classname_from_app_link(entry.app_link)
                })
            return result

        raise HTTPNotFound()


class NavigationFavorites(object):

    def __init__(self, classname):
        self.classname = classname

    def get_favorites(self, request):
        fc = FavoriteCollection(self.classname, None)
        global_favorites = request.view(fc, app=get_favorites_app(request))

        cdef = CDBClassDef(self.classname)
        sfc = request.view(SearchFavouriteCollection(self.classname))

        render_result = []

        for fav in global_favorites["favorites"]:
            render_result.append({
                "imageSrc": "/resources/icons/byname/%s/0" % cdef.getIconId(),
                "title": fav["title"],
                "link": fav["frontend_url"]
            })

        for sf in sfc["favourites"]:
            render_result.append({
                "imageSrc": "/resources/icons/byname/csweb_search/0",
                "title": sf["name"],
                "link": "/info/%s?favorite_id=%s" % (ui_name_for_class(cdef),
                                                     sf["cdb_object_id"])
            })

        return sorted(render_result, key=lambda k: k['title'])


@App.path(path="navigation/{section_id}", model=NavigationContent)
def _get_nav_entries_model(section_id):
    return NavigationContent(section_id)


@App.path(path="navigation/favorites/{classname}", model=NavigationFavorites)
def _get_nav_favorites_model(classname):
    return NavigationFavorites(classname)


@App.json(model=NavigationContent)
def _get_nav_entries(nav_content, request):
    return nav_content.get_entries()


@App.json(model=NavigationFavorites)
def _get_nav_favorites(nav_favorites, request):
    return nav_favorites.get_favorites(request)


@App.path(path="navigation/tree/{navigation_id}", model=NavigationTreeContent)
def _get_navigationtree_model(navigation_id, extra_parameters):
    return NavigationTreeContent(navigation_id, extra_parameters)


@App.json(model=NavigationTreeContent)
def _get_navigationtree_json(navtree, request):
    return navtree.get_entries(request)


@App.path(path="navigation/submenu/{navigation_id}", model=NavigationTreeSubmenuContent)
def _get_navigationtreesubmenu_model(navigation_id, extra_parameters):
    return NavigationTreeSubmenuContent(navigation_id, extra_parameters)


@App.json(model=NavigationTreeSubmenuContent)
def _get_navigationtreesubmenu_json(navtree, request):
    return navtree.get_entries(request)
