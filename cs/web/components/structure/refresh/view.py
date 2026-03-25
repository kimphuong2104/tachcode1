# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import

import six

from cdb import ElementsError
from cs.web.components.structure import StructureApp
from .model import StructureRefreshModel
from webob.exc import HTTPForbidden

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


@StructureApp.json(model=StructureRefreshModel, request_method='POST')
def _structure_refresh_model_json(model, request):
    nodes = request.json['nodes']
    try:
        return model.get_refresh_information(nodes)
    except ElementsError as e:
        raise HTTPForbidden(six.text_type(e))
