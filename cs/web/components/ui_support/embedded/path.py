# !/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
from __future__ import absolute_import, unicode_literals
from cdb import constants
from cs.web.components.ui_support.embedded.main import EmbeddedOperationApp
from cs.web.components.ui_support.embedded.model import EmbeddedClassOperationModel
from cs.web.components.ui_support.embedded.model import EmbeddedClassSearchModel

__revision__ = "$Id$"

@EmbeddedOperationApp.path(model=EmbeddedClassOperationModel, path="operation/{opname}/{clazz}", absorb=True)
def get_class_operation_model(opname, clazz, absorb):
    mdl = EmbeddedClassOperationModel(clazz, opname, absorb if absorb else None)
    return mdl if mdl.is_valid() and mdl.offer_in_webui() else None

@EmbeddedOperationApp.path(model=EmbeddedClassSearchModel, path="search2/{clazz}")
def get_class_search_model(clazz):
    mdl = EmbeddedClassSearchModel(clazz)
    return mdl if mdl.is_valid() else None
