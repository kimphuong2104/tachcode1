# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

"""
Web app to start an access check and render the results
"""

from __future__ import absolute_import

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"

import os
import six

try:
    from functools import lru_cache
except ImportError:
    from backports.functools_lru_cache import lru_cache

from cdb import rte
from cdb import sig
from cdb import ue
from cdb import util

from cdbwrapc import get_help_url
from cdb.objects import Object
from cs.platform.web import static
from cs.platform.web.root import Internal
from cs.web.components.base.main import BaseApp, BaseModel
from cs.web.components.ui_support import forms, get_uisupport_app


class AccessCheckApp(BaseApp):

    def update_app_setup(self, app_setup, model, request):
        super(AccessCheckApp, self).update_app_setup(app_setup, model, request)
        fis = forms.FormInfoSimple("ce_showacconfig_userselection")
        form_info_link = request.link(fis, app=get_uisupport_app(request))
        hurl = get_help_url("accesscheck_app")
        app_setup.merge_in(["links", "cs-admin"], {
            "access_check_api": "/internal/cs-admin/access-check-api",
            "access_check_form": form_info_link,
            "access_check_help": hurl
        })


@Internal.mount(app=AccessCheckApp, path="/cs-admin/access-check")
def _mount_app():
    return AccessCheckApp()


@AccessCheckApp.view(model=BaseModel, name="document_title", internal=True)
def default_document_title(self, request):
    return util.get_label("web.config_check_app.label")


@AccessCheckApp.view(model=BaseModel, name="app_component", internal=True)
def _setup(self, request):
    request.app.include("cs-admin-access_check_app", "0.0.1")
    return "cs-admin-access_check_app-MainComponent"


@AccessCheckApp.view(model=BaseModel, name="base_path", internal=True)
def get_base_path(self, request):
    return request.path


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def _register_libraries():
    lib = static.Library("cs-admin-access_check_app", "0.0.1",
                         os.path.join(os.path.dirname(__file__),
                                      'js', 'build'))
    lib.add_file("cs-admin-access_check_app.js")
    lib.add_file("cs-admin-access_check_app.js.map")
    static.Registry().add(lib)


@sig.connect(Object, "CE_ShowACConfig", "now")
def _call_config_app(self, ctx):
    obj = self.ToObjectHandle()
    cdef = obj.getClassDef()
    relation = cdef.getPrimaryTable()
    acs = util.ACAccessSystem(relation, "")
    try:
        result = (acs.get_access_control_type() != 0)
    except AttributeError:
        # Function has been introduced with 15.5, SL 13
        result = cdef.isSystemOpAvailable("CDB_ShowACConfig")
    if not result:
        raise ue.Exception("err_accesscheckapp_no_access_config",
                           cdef.getClassname())

    url = "/internal/cs-admin/access-check?"
    oid = obj.get_object_id()
    url += six.moves.urllib.parse.urlencode({'ohandle_id': oid})
    ctx.url(url)
