#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


import morepath
import os
from cdb import rte
from cdb import sig
from cdb import CADDOK
from cs.web.components.base.main import BaseApp, BaseModel, get_page
from cs.platform.web import static
from cs.platform.web.root import Root


MOUNTEDPATH = "/storybook"
STORYBOOK = "cs-web-components-storybook"
MANAGER = "%s-manager" % STORYBOOK
LOADER = "%s-loader" % STORYBOOK

STORIES = []

# Hook to add story specific setups
STORYBOOK_APP_SETUP_HOOK = sig.signal()
STORYBOOK_APP_SETUP_PATH = ["storybook", "stories"]


def add_csp_header(response):
    response.headers.add(
        "Content-Security-Policy",
        "default-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data: blob:; "
        "media-src 'self' data: blob:")


def add_stories(lib, stories):
    global STORIES
    STORIES.append((lib, stories))


def use_lib(name, version):
    return static.Registry().get(name, version).render()


class StorybookApp(BaseApp):
    RENDERER = None

    def update_app_setup(self, app_setup, model, request):
        super(StorybookApp, self).update_app_setup(app_setup, model, request)
        app_setup.update({
            STORYBOOK: {
                "previewLink": request.link(BaseModel(), app=request.app.child('iframe.html'))
            }
        })


def _mount_app():
    return StorybookApp()


# Only serve storybook if this developing flag set to True
if CADDOK.get("WEBUI_STORYBOOK", "").lower() == 'true':
    Root.mount(app=StorybookApp, path=MOUNTEDPATH)(_mount_app)


class StorybookModel(BaseModel):
    pass


@StorybookApp.path(path="main", model=StorybookModel)
def get_storybook_model():
    return StorybookModel()


@StorybookApp.view(model=BaseModel)
def get_storybook_redirect(self, request):
    return morepath.redirect('%s/main' % MOUNTEDPATH)


@StorybookApp.html(model=StorybookModel)
def get_storybook_page(self, request):
    return get_page(self, request)


@StorybookApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    # TODO: label
    return "cs.web storybook"


@StorybookApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return MOUNTEDPATH


@StorybookApp.view(model=BaseModel, name="_body", internal=True)
def get_special_body(model, request):
    request.after(add_csp_header)
    tags = ["<div id='root' />"]
    tags.append(use_lib(STORYBOOK, "15.1.0"))
    tags.append(use_lib(MANAGER, "15.1.0"))
    return "\n".join(tags)


class PreviewApp(BaseApp):
    RENDERER = None

    def update_app_setup(self, app_setup, model, request):
        super(PreviewApp, self).update_app_setup(app_setup, model, request)
        app_setup.merge_in(STORYBOOK_APP_SETUP_PATH, {})
        sig.emit(STORYBOOK_APP_SETUP_HOOK)(app_setup, model, request)


@StorybookApp.mount(app=PreviewApp, path="iframe.html")
def _mount_preview_app():
    return PreviewApp()


@PreviewApp.view(model=BaseModel, name="document_title", internal=True)
def preview_document_title(self, request):
    # TODO: label
    return "cs.web storybook"


@PreviewApp.view(model=BaseModel, name="app_component", internal=True)
def preview_setup(self, request):
    for story in STORIES:
        request.app.include(*story[0])

    def add_csp_header(response):
        response.headers.add(
            "Content-Security-Policy",
            "default-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data: blob:; "
            "media-src 'self' data: blob:; "
            "connect-src 'self' data: blob:"
        )

    request.after(add_csp_header)
    return ""


@PreviewApp.view(model=BaseModel, name="base_path", internal=True)
def preview_base_path(self, request):
    return MOUNTEDPATH + "/preview"


@PreviewApp.view(model=BaseModel, name="_body", internal=True)
def get_preview_body(model, request):
    tags = ["<div id='root' />"]
    tags.append(use_lib(STORYBOOK, "15.1.0"))
    for story in STORIES:
        tags.append(use_lib(*story[1]))
    tags.append(use_lib(LOADER, "15.1.0"))
    return "\n".join(tags)


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library(STORYBOOK,
                         "15.1.0",
                         os.path.join(os.path.dirname(__file__), "js", "build"))
    lib.add_file("%s-utils.js" % STORYBOOK)
    lib.add_file("%s-utils.js.map" % STORYBOOK)
    lib.add_file("%s.js" % STORYBOOK)
    lib.add_file("%s.js.map" % STORYBOOK)
    static.Registry().add(lib)

    lib = static.Library(MANAGER,
                         "15.1.0",
                         os.path.join(os.path.dirname(__file__), "js", "build"))
    lib.add_file("%s.js" % MANAGER)
    lib.add_file("%s.js.map" % MANAGER)
    static.Registry().add(lib)

    lib = static.Library(LOADER,
                         "15.1.0",
                         os.path.join(os.path.dirname(__file__), "js", "build"))
    lib.add_file("%s.js" % LOADER)
    lib.add_file("%s.js.map" % LOADER)
    static.Registry().add(lib)
