#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import os

import cdbwrapc
from cdb import rte, sig, util
from cdb.elink import isCDBPC
from cs.platform.web import static

from .main import ShareObjectsApp
from .model import ShareObjectsModel


def get_title():
    is_cdbpc = isCDBPC()
    if is_cdbpc:
        return util.get_label("cdb_share_objects")
    else:
        return cdbwrapc.getApplicationName()


@ShareObjectsApp.view(model=ShareObjectsModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include("cs-sharing", "15.2.0")
    return "cs-sharing-ShareObjectsApp"


@ShareObjectsApp.view(model=ShareObjectsModel, name="base_path", internal=True)
def get_base_path(self, request):
    return "/share_objects"


@ShareObjectsApp.view(model=ShareObjectsModel, name="application_title", internal=True)
def get_application_title(self, request):
    return get_title()


@ShareObjectsApp.view(model=ShareObjectsModel, name="document_title", internal=True)
def default_document_title(self, request):
    return util.get_label("cdb_share_objects")


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(
        "cs-sharing", "15.2.0", os.path.join(os.path.dirname(__file__), "gui", "build")
    )
    lib.add_file("cs-sharing.js")
    lib.add_file("cs-sharing.js.map")
    static.Registry().add(lib)
