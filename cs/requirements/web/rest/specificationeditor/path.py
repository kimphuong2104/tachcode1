# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from .main import SpecificationEditorAPI
from .model import SpecificationEditorAPIModel


@SpecificationEditorAPI.path(path='{cdb_object_id}', model=SpecificationEditorAPIModel)
def get_context_by_id(cdb_object_id, app):
    return SpecificationEditorAPIModel(cdb_object_id)
