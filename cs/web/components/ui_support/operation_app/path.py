# !/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from __future__ import absolute_import, unicode_literals
import six
import json
from cdb import constants, ElementsError
from cs.web.components.ui_support.operation_app.main import OperationApp
from cs.web.components.ui_support.operation_app.model import (ClassOperationModel,
                                                              ClassCatalogOperationModel)

__revision__ = "$Id$"

# List of valid operations. For now only CDB_Create is supported.
valid_operations = [constants.kOperationNew]

@OperationApp.path(model=ClassOperationModel, path="{opname}/{clazz}")
def get_class_operation_model(opname, clazz, dialog, object_navigation_id, object_navigation_ids):
    try:
        oids = json.loads(object_navigation_ids) if object_navigation_ids else []
    except ValueError:
        raise ElementsError('\'object_navigation_ids\' is no valid json')
    if object_navigation_id:
        oids.append(object_navigation_id)
    mdl = ClassOperationModel(clazz, opname, oids, dialog)
    return mdl if mdl.is_valid() and mdl.offer_in_webui() else None


@OperationApp.path(model=ClassCatalogOperationModel, path="catalog/{catalog}/{opname}/{clazz}")
def get_class_operation_model(catalog, opname, clazz):
    if opname not in valid_operations:
        opname = None
    return ClassCatalogOperationModel(catalog, clazz, opname)
