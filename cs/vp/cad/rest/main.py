#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from cs.platform.web.root import Internal
from cs.platform.web import JsonAPI

__revision__ = "$Id$"

__APP_NAME__ = "cad_document"


class VpCadInternalApp(JsonAPI):
    pass


@Internal.mount(app=VpCadInternalApp, path=__APP_NAME__)
def _mount_internal():
    return VpCadInternalApp()


class CadSearchInternalApp(JsonAPI):
    pass


@Internal.mount(app=CadSearchInternalApp, path="cad_search")
def _mount_internal():
    return CadSearchInternalApp()
