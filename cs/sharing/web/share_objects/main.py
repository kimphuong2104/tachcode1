#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

from cdb import CADDOK, auth, sig, util
from cdbwrapc import RestCatalog
from cs.platform.web.root import Root, get_root
from cs.platform.web.uisupport.main import get_uisupport
from cs.web.components.base.main import GLOBAL_APPSETUP_HOOK, BaseApp
from cs.web.components.ui_support import catalogs

from . import GROUP_SIZE_LIMIT, HELP_ID
from .model import ShareObjectsModel

__docformat__ = "restructuredtext en"

CATALOG_NAME = "angest_web_sharing"


class ShareObjectsApp(BaseApp):
    """Web application to show sharings for a single attachment object"""

    def __init__(self):
        super(ShareObjectsApp, self).__init__()
        self.includes = []

    def update_app_setup(self, app_setup, model, request):
        super(ShareObjectsApp, self).update_app_setup(app_setup, model, request)

        catalog_cfg = {}
        uisupport = get_uisupport(request)

        # TODO generate catalog urls for angestellter
        rc = RestCatalog(CATALOG_NAME, "", [])
        catalog_cfg["select_url"] = request.link(
            catalogs.CatalogSelectedValuesModel(CATALOG_NAME, {}), app=uisupport
        )
        catalog_cfg["form_url"] = request.link(
            catalogs.CatalogQueryFormModel(CATALOG_NAME, {}), app=uisupport
        )
        if rc.is_structure_browser():
            catalog_cfg["structure_root_url"] = request.link(
                catalogs.CatalogStructureModel(CATALOG_NAME, {}), app=uisupport
            )
        else:
            catalog_cfg["items_url"] = request.link(
                catalogs.CatalogItemsModel(CATALOG_NAME, {}), app=uisupport
            )
            catalog_cfg["type_ahead_url"] = request.link(
                catalogs.CatalogTypeAheadModel(CATALOG_NAME, {}), app=uisupport
            )
            catalog_cfg["tabdef_url"] = request.link(
                catalogs.CatalogTableDefWithValuesModel(CATALOG_NAME, {}), app=uisupport
            )

        if rc.is_value_check_catalog():
            catalog_cfg["value_check_url"] = request.link(
                catalogs.CatalogValueCheckModel(CATALOG_NAME, {}), app=uisupport
            )
        app_setup.merge_in(
            ["cs-sharing"],
            {
                "helpURL": "/help/id/%s" % HELP_ID,
                "GROUP_SIZE_LIMIT": GROUP_SIZE_LIMIT,
                "user_id": auth.persno,
                "user_catalog": catalog_cfg,
                "language": CADDOK.ISOLANG,
                "settings": {},
            },
        )


@Root.mount(app=ShareObjectsApp, path="share_objects")
def _mount_sharings_app():
    return ShareObjectsApp()


@ShareObjectsApp.path(model=ShareObjectsModel, path="")
def _get_web_model():
    return ShareObjectsModel()


@sig.connect(GLOBAL_APPSETUP_HOOK)
def update_app_setup(app_setup, request):
    attachments = ShareObjectsModel()
    app_setup.merge_in(
        ["cs-sharing-web-share_objects"],
        {
            "objectsSharing": {
                "URL": "%s?attachments="
                % request.link(
                    attachments, app=get_root(request).child("share_objects")
                ),
                "iconName": "elements_share",
                "label": util.get_label("elements_share"),
            }
        },
    )
