# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Backend functions to access the license feature export file
"""

import json
import morepath

from cs.platform.web import PlatformApp
from cdb.comparch.modules import Module

from cs.platform.web.root import Internal


class LicfeatureFileApp(PlatformApp):
    pass


@Internal.mount(app=LicfeatureFileApp,
                path="/cs-admin/lic_feature_file")
def mount_pkg_dependencies_app():
    return LicfeatureFileApp()


class LicfeatureFileModel(object):
    def __init__(self, module_id):
        self.module_id = module_id


@LicfeatureFileApp.path(model=LicfeatureFileModel, path="")
def _path(module_id):
    return LicfeatureFileModel(module_id)


@LicfeatureFileApp.view(model=LicfeatureFileModel)
def _retrieve_file(model, request):
    content = None
    if model.module_id:
        m = Module.ByKeys(model.module_id)
        if m:
            feature_data = m._get_feature_data()
            content = json.dumps(feature_data, indent=4, sort_keys=True)

    response = morepath.Response(content_type="application/json",
                                 charset="utf-8",
                                 body=content)
    response.cache_control.private = True
    response.cache_control.no_cache = True
    response.cache_control.max_age = 0
    return response
