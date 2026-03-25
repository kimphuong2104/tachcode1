#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from cs.vp.cad.rest.main import VpCadInternalApp, CadSearchInternalApp
from cs.vp.cad.rest.model import AvailableViewers, CadSearchModel


@VpCadInternalApp.path(path="available_viewers/{object_id}", model=AvailableViewers)
def _get_available_viewers(object_id):
    return AvailableViewers(object_id)


@CadSearchInternalApp.path(path="loadMatchingCADVariants", model=CadSearchModel)
def _get_available_viewers():
    return CadSearchModel()
