#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


__revision__ = "$Id$"

import logging
import os
from urllib.parse import unquote

from cdb import rte, sig
from cdb.objects.org import CommonRole, Person
from cs.platform.web import static
from cs.web.components.generic_ui import get_ui_app
from cs.web.components.generic_ui.detail_view import ClassViewModel
from cs.web.components.storybook.main import STORYBOOK_APP_SETUP_HOOK

from cs.pcs.projects import Role

APP = "cs-pcs-common-web"
VERSION = "15.1.0"


@sig.connect(STORYBOOK_APP_SETUP_HOOK)
def use_common_lib(_, __, request):
    # make this lib available to all stories
    request.app.include(APP, VERSION)

    # sort this directly after cs.web libs so dependency order is OK
    # (uses undocumented internals of cs.web.components.base.main.BaseApp)
    web_index = max(
        index
        for index, lib in enumerate(request.app.includes)
        if lib.name.startswith("cs-web")
    )
    request.app.includes.insert(web_index + 1, request.app.includes.pop())


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def register_libraries():
    lib = static.Library(
        APP, VERSION, os.path.join(os.path.dirname(__file__), "js", "build")
    )
    lib.add_file(f"{APP}.js".format(APP))
    lib.add_file(f"{APP}.js.map")
    static.Registry().add(lib)


def get_url_patterns(request, app, models):
    """
    :param request: The request sent from the frontend
    :type request: morepath.Request

    :param app: Application to generate URL patterns for
    :type app: Mounted `morepath.App`

    :param models: Tuples with three entries each:
        label, model_class, list of variables
    :type models: list of tuples

    :returns: URL patterns (URLs with placeholders)
        indexed by names to be referenced by the frontend
        and application names.
    :rtype: dict

    :raises morepath.error.LinkError: if any model class cannot be linked to
    """

    def _get_url_pattern(model_class, params):
        try:
            return unquote(
                request.class_link(
                    model_class,
                    # pylint: disable-next=consider-using-f-string
                    {param: "${%s}" % param for param in params},
                    app=app,
                )
            )
        except Exception:
            logging.exception("failed to get URL pattern: %s, %s", model_class, params)
            raise

    return {
        label: _get_url_pattern(model_class, params)
        for label, model_class, params in models
    }


def get_app_url_patterns(request):
    app = get_ui_app(request)

    def _get_url(model_class, keys):
        rest_name = model_class().GetClassDef().getRESTName()
        base = request.link(
            ClassViewModel(rest_name, None),
            app=app,
        )
        # pylint: disable-next=consider-using-f-string
        masked_keys = ["${%s}" % key for key in keys]
        return f"{base}/{'@'.join(masked_keys)}"

    return {
        model_class.__subject_type__: _get_url(model_class, keys)
        for model_class, keys in [
            (Person, ["subject_id"]),
            (Role, ["subject_id", "cdb_project_id"]),
            (CommonRole, ["subject_id"]),
        ]
    }
