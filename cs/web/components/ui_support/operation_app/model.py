# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Morepath app for Web UI operations
"""

from __future__ import absolute_import

from cdb import ElementsError
from cdb.platform.mom import operations
from cdbwrapc import CDBClassDef
from cs.platform.web.rest import support
from cs.web.components.configurable_ui import SinglePageModel
from cs.web.components.ui_support.utils import resolve_ui_name
from cs.platform.web.uisupport import get_uisupport

__revision__ = "$Id$"

class ClassOperationModel(SinglePageModel):
    page_name = "cs-web-class-operation_page"

    def __init__(self, clazz_rest_or_ui_name, operation_name, object_navigation_ids, dialog):
        super(ClassOperationModel, self).__init__()
        (self.classname, self.rest_name, self.ui_name) = resolve_ui_name(clazz_rest_or_ui_name)
        self.operation_name = operation_name
        self.op_info = operations.OperationInfo(self.classname, self.operation_name)
        self.object_navigation_ids = object_navigation_ids
        self.dialog = dialog

    def is_valid(self):
        if self.rest_name is None or self.classname is None:
            return False

        try:
            activation_mode = self.op_info.get_activation_mode()
            no_objs = len(self.object_navigation_ids)
            if activation_mode == 2 and no_objs != 1:
                return False
            if activation_mode == 3 and no_objs < 1:
                return False
            if activation_mode in [0, 1] and no_objs != 0:
                return False
        except AttributeError:
            # op_info will raise an AttributeError on access
            # if it is not valid
            return False

        return all(hdl and hdl.is_valid()
                   for hdl in support.rest_objecthandles(self.classdef,
                   self.object_navigation_ids))

    def offer_in_webui(self):
        if self.op_info:
            return self.op_info.offer_in_webui()
        else:
            return False

    @property
    def classdef(self):
        return CDBClassDef(self.classname)


class CatalogOperationInfo(object):
    def __init__(self, catalog, op_info):
        self.op_info = op_info
        self.catalog = catalog


class ClassCatalogOperationModel(SinglePageModel):
    page_name = "cs-web-class-operation_page"

    @classmethod
    def template_link(cls, request):
        from cs.web.components.ui_support.operation_app.main import get_operation_app
        return request.class_link(ClassCatalogOperationModel,
                                  {"catalog": "${catalog}",
                                   "opname": "${opname}",
                                   "clazz": "${clazz}"},
                                  app=get_operation_app(request))

    def __init__(self, catalog, class_name, operation_name):
        super(ClassCatalogOperationModel, self).__init__()
        self.catalog = catalog
        self.classname = class_name
        self.operation_name = operation_name
        self.object_navigation_ids = []
        self.rest_name = None

        from cdbwrapc import RestCatalog
        from cdb.platform.mom import SimpleArguments
        c = RestCatalog(catalog, "", SimpleArguments())
        op_infos = c.get_create_opinfo()
        for oi in op_infos:
            if oi.get_opname() == self.operation_name and oi.get_classname() == self.classname:
                self.op_info = CatalogOperationInfo(catalog, oi)
                break

    @property
    def classdef(self):
        return CDBClassDef(self.classname)
