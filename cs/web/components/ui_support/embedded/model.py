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

import os
from cdb.platform.mom import operations
from cdbwrapc import CDBClassDef
from cs.web.components.configurable_ui import ConfigurableUIModel, SinglePageModel
from cs.web.components.ui_support.utils import resolve_ui_name

__revision__ = "$Id$"

class EmbeddedClassOperationModel(ConfigurableUIModel):
    page_renderer = "cs-web-components-base-SinglePage"


    def __init__(self, clazz_rest_or_ui_name, operation_name, keys):
        super(EmbeddedClassOperationModel, self).__init__()
        (self.classname, self.rest_name, self.ui_name) = resolve_ui_name(clazz_rest_or_ui_name)
        self.operation_name = operation_name
        self.op_info = operations.OperationInfo(self.classname, self.operation_name)
        self.keys = keys
        self.set_page_frame('csweb_embedded_empty_page_frame')

    def is_valid(self):
        return self.rest_name is not None and self.classname is not None

    def offer_in_webui(self):
        if self.op_info:
            return self.op_info.offer_in_webui()
        else:
            return False

    @property
    def classdef(self):
        return CDBClassDef(self.classname)

    def config_filename(self):
        base_path = os.path.dirname(__file__)
        config_file_path = os.path.abspath(os.path.join(base_path, 'config', 'embeddedoperation.json'))
        return config_file_path

    def load_application_configuration(self):
        super(EmbeddedClassOperationModel, self).load_application_configuration()
        self.insert_component_configuration(
            "pageContent",
            {"configuration": self.config_filename()}
        )


class EmbeddedClassSearchModel(ConfigurableUIModel):
    page_renderer = "cs-web-components-base-SinglePage"

    def __init__(self, clazz_rest_or_ui_name):
        super(EmbeddedClassSearchModel, self).__init__()
        (self.classname, self.rest_name, self.ui_name) = resolve_ui_name(clazz_rest_or_ui_name)
        self.search_model = True
        self.set_page_frame('csweb_embedded_empty_page_frame')

    def config_filename(self):
        base_path = os.path.dirname(__file__)
        config_file_path = os.path.abspath(os.path.join(base_path, 'config', 'searchappWebview2.json'))
        return config_file_path

    def load_application_configuration(self):
        super(EmbeddedClassSearchModel, self).load_application_configuration()
        self.insert_component_configuration(
            "pageContent",
            {"configuration": self.config_filename()}
        )

    def is_valid(self):
        return self.rest_name is not None and self.classname is not None

    @property
    def classdef(self):
        return CDBClassDef(self.classname)
