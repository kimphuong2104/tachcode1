# !/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
from __future__ import absolute_import, unicode_literals

from cs.web.components.ui_support.operation_app.main import OperationApp
from cs.web.components.ui_support.operation_app.model import (ClassOperationModel,
                                                              CatalogOperationInfo)
from cs.web.components.ui_support.catalogs import CatalogGetDirectCreateOpModel
from cs.web.components.ui_support import App, operations

__revision__ = "$Id$"


@OperationApp.view(model=ClassOperationModel, name="document_title", internal=True)
def _document_title(model, _request):
    return "{} / {}".format(model.classdef.getTitle(), model.op_info.get_label())

@App.json(model=CatalogOperationInfo)
def _get_op_info(model, request):
    form_settings_model = CatalogGetDirectCreateOpModel(model.catalog, {"classname": model.op_info.get_classname()})
    return operations._op_info_data(model.op_info, request, form_settings_model=form_settings_model)
