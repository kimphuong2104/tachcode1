# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id: main.py 198563 2019-07-12 07:11:33Z tst $"

import os

from cdb import rte
from cdb import sig
from cdb.objects import ICON_CACHE
from cs.platform.web import static
from cs.platform.web.root import Root, get_root

from cs.web.components.base.main import BaseApp, GLOBAL_APPSETUP_HOOK
from cs.web.search.model import SearchModel


class SearchApp(BaseApp):
    """ The UI application, that is responsible for the visible part
    """

    def update_app_setup(self, app_setup, model, request):
        super(SearchApp, self).update_app_setup(app_setup, model, request)

        app_setup.merge_in(["links", "cs-web-search"], {
            "fulltext_search_api": "/internal/search/fulltext",
            "fulltext_highlight_api": "/internal/search/highlight",
            "fulltext_search_route": "fulltextsearch",
            "search_icon_link": ICON_CACHE.getIcon('ES_Search')
        })


@Root.mount(app=SearchApp, path="search")
def _mount_app():
    return SearchApp()


@SearchApp.path(model=SearchModel, path="/", absorb=True)
def get_app_model(absorb):
    return SearchModel(absorb)


@SearchApp.view(model=SearchModel, name="document_title", internal=True)
def default_document_title(self, request):
    return "Search"


@SearchApp.view(model=SearchModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include("cs-web-search", "0.0.1")
    return "cs-web-search-SearchApp"


@SearchApp.view(model=SearchModel, name="base_path", internal=True)
def get_base_path(self, request):
    if not self.absorb:
        return request.path
    else:
        return request.path[:-(len(self.absorb) + 1)]


@SearchApp.view(model=SearchModel, name="hide_title_bar_search_field", internal=True)
def get_hide_title_bar_search_field(model, request):
    return True


@sig.connect(GLOBAL_APPSETUP_HOOK)
def update_global_app_setup(app_setup, request):
    app_setup.merge_in(['links', 'common'], {
        "search": request.link(SearchModel(),
                               app=get_root(request).child('search'))
    })


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-web-search",
                         "0.0.1",
                         os.path.join(os.path.dirname(__file__),
                                      'js', 'build'))
    lib.add_file("cs-web-search.js")
    lib.add_file("cs-web-search.js.map")
    static.Registry().add(lib)
