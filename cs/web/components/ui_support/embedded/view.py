# !/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
from __future__ import absolute_import, unicode_literals

from cdb import util
from cs.web.components.ui_support.embedded.main import EmbeddedOperationApp
from cs.web.components.ui_support.embedded.model import EmbeddedClassOperationModel
from cs.web.components.ui_support.embedded.model import EmbeddedClassSearchModel

__revision__ = "$Id$"


@EmbeddedOperationApp.view(model=EmbeddedClassOperationModel, name="document_title", internal=True)
def _document_title(model, _request):
    return "{} / {}".format(model.classdef.getTitle(), model.op_info.get_label())

@EmbeddedOperationApp.view(model=EmbeddedClassSearchModel, name="document_title", internal=True)
def _document_title(model, _request):
    return util.get_label("csweb_embedded_search_ex").format(model.classdef.getTitle())
