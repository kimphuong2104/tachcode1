# !/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Morepath app for Web UI operations
"""

from __future__ import absolute_import, unicode_literals

import json
import logging

import six

from cdb import sig, util
from cs.platform.web.rest import get_collection_app, support
from cs.platform.web.root import root, get_root
from cs.platform.web.uisupport import get_uisupport as get_uisupport_app
from cs.web.components.generic_ui import get_ui_app
from cs.web.components.configurable_ui import ConfigurableUIApp
from cs.web.components.ui_support.operation_app.model import ClassCatalogOperationModel
from cs.web.components.base.main import GLOBAL_APPSETUP_HOOK

from morepath.error import LinkError

__revision__ = "$Id$"

LOG = logging.getLogger(__name__)

class OperationApp(ConfigurableUIApp):
    def update_app_setup(self, app_setup, model, request):
        super(OperationApp, self).update_app_setup(app_setup, model, request)
        if hasattr(model, "op_info"):
            app_setup["appSettings"]["currentOperation"] = request.view(
                model.op_info,
                app=get_uisupport_app(request)
            )
            if model.rest_name and len(model.object_navigation_ids):
                objs = support.get_objects_from_rest_name(
                    model.rest_name,
                    model.object_navigation_ids,
                    force_persistent=False)
                app_setup["appSettings"]["currentOperationObjects"] = \
                    [request.view(obj, app=get_collection_app(request)) for obj in objs]
                app_setup["appSettings"]["currentOperationDialog"] = model.dialog
            params = request.GET.get('p', '{}')
            try:
                params = json.loads(params)
            except (TypeError, ValueError) as e:
                LOG.exception(e)
                params = {}
                app_setup["appSettings"]["currentOperationParamError"] = {
                    "title": util.get_label('csweb_operation_parameter_error'),
                    "message": six.text_type(e)
                }
            app_setup["appSettings"]["currentOperationParams"] = params


@root.mount(app=OperationApp, path='operation')
def _mount_app():
    return OperationApp()


def get_operation_app(request, **kwargs):
    return get_root(request).child(OperationApp, **kwargs)

@sig.connect(GLOBAL_APPSETUP_HOOK)
def global_app_setup(app_setup, request):
    try:
        catalog_opapp_link = six.moves.urllib.parse.unquote(ClassCatalogOperationModel.template_link(request))
        app_setup.merge_in(['links', 'common'], {
            'catalog_opapp_link': catalog_opapp_link,
        })
    except LinkError:
        pass
