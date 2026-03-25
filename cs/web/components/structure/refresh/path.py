# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import

from cs.web.components.structure import StructureApp
from .model import StructureRefreshModel
from webob.exc import HTTPForbidden

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


@StructureApp.path(model=StructureRefreshModel, path='/{structure_name}/refresh_node')
def _get_structure_refresh_model(structure_name, app):
    if not app.parent_object.CheckAccess('read'):
        # no read access to the source object means no access to the structure
        raise HTTPForbidden()
    return StructureRefreshModel(app.parent_object, structure_name)
