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
from cdb import util
from cdb.objects.core import Object
from cs.platform.web.root.main import root
from cs.platform.web.uisupport import get_uisupport as get_uisupport_app
from cs.web.components.configurable_ui import ConfigurableUIApp
from cs.web.components.ui_support.search_favourites import SearchFavouriteCollection
from cs.web.components.base.main import BaseErrorModel
from cs.platform.web.rest import CollectionApp, get_collection_app

__revision__ = "$Id$"

LOG = logging.getLogger(__name__)

class EmbeddedOperationApp(ConfigurableUIApp):
    def update_app_setup(self, app_setup, model, request):
        super(EmbeddedOperationApp, self).update_app_setup(app_setup, model, request)
        if isinstance(model, BaseErrorModel):
            app_setup["appSettings"]["appComponent"] = "cs-web-components-base-EmbeddedErrorPage"

        app_setup["appSettings"]["embeddedOperationApp"] = True

        if hasattr(model, "op_info"):
            app_setup["appSettings"]["currentOperation"] = request.view(
                model.op_info,
                app=get_uisupport_app(request)
            )

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
        if hasattr(model, "search_model"):
            class_ops = {}
            class_ops['CDB_Search'] = []
            class_ops['CDB_Search'].append({'classname': model.classname, 'opname': 'CDB_Search'})

            app_setup.merge_in(["class_view"], {
                "classOpInfos": class_ops,
                "searchFavourites": SearchFavouriteCollection(model.classname).make_link(request)})
            app_setup.merge_in(["embedded_search"], {
                    "classname": model.classname
            })

        if hasattr(model, "keys") and hasattr(model, "rest_name"):
            collection_app = get_collection_app(request)
            if model.rest_name and model.keys:
                app_setup["appSettings"]["currentOperationObjectURL"] = six.moves.urllib.parse.unquote(request.class_link(Object,
                                                                                {'rest_name': model.rest_name,
	                                                                             'keys': model.keys},
	                                                                             app=collection_app))

@root.mount(app=EmbeddedOperationApp, path='embedded')
def _mount_app():
    return EmbeddedOperationApp()
