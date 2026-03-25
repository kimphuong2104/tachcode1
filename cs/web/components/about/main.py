# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import
import os

from cdb import auth, i18n, CADDOK
from cdb.sqlapi import RecordSet2
from cdb.wsgi import util as wsgi_util, messages
from cdbwrapc import (
    getApplicationName,
    getBrandedLongServerVersion,
    getVersionDescription,
    get_label_with_fallback
)

from cs.platform.web import PlatformApp
from cs.platform.web.root import Root

MOUNTEDPATH = "/about"
LAYOUT = os.path.join(os.path.join(os.path.dirname(__file__), "resources"), "about.html")


class AboutModel(object):
    pass


class AboutApp(PlatformApp):
    pass


@Root.mount(app=AboutApp, path=MOUNTEDPATH)
def _mount_app():
    return AboutApp()


@AboutApp.path(model=AboutModel, path='/')
def get_infos():
    return AboutModel()


@AboutApp.html(model=AboutModel)
def _about_view(self, request):
    from cdb.comparch import pkgtools
    from chameleon import PageTemplateFile
    from collections import OrderedDict

    infos = OrderedDict()
    infos["product"] = getApplicationName()
    infos["product_version"] = getBrandedLongServerVersion()

    infos["server_version"] = getVersionDescription()
    infos["server_node_id"] = CADDOK.get("UNIQUE_NODE_ID", "")
    edge_server_info = wsgi_util.get_edge_server_info(request.environ)
    if edge_server_info is None:
        infos["server"] = wsgi_util.get_host(request.environ)
    elif len(edge_server_info) > 0:
        infos["edge"] = edge_server_info[0]
        if len(edge_server_info) > 1:
            infos["edge_version"] = edge_server_info[1]

    infos["client_host"] = wsgi_util.get_client_address(request.environ)
    infos["user"] = "{0} ({1})".format(auth.get_name(), auth.get_login())

    labels = {row.ausgabe_label.partition('web.about.')[2]:
              get_label_with_fallback(row.ausgabe_label, i18n.default())
              for row
              in RecordSet2(table="ausgaben",
                            condition="ausgabe_label LIKE 'web.about.%'",
                            columns=["ausgabe_label"])}

    platform_templates = os.path.join(os.environ['CADDOK_HOME'], 'chrome')
    tmpl = PageTemplateFile(LAYOUT, search_path=[platform_templates])

    return tmpl(encoding="utf-8",
                title='Info',
                show_logout=False,
                component_namespace='cs-web-components-theme-static',
                labels=labels,
                infos=infos,
                message=messages.message,
                packages=pkgtools.get_package_version_desc("||").split("||"))
