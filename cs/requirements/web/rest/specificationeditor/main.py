# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cs.platform.web import JsonAPI
from cs.platform.web import root


class SpecificationEditorAPI(JsonAPI):
    pass


@root.Internal.mount(app=SpecificationEditorAPI, path="specificationeditor")
def _mount_api():
    return SpecificationEditorAPI()
