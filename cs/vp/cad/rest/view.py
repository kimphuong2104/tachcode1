#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from cs.vp.cad.rest.main import VpCadInternalApp, CadSearchInternalApp
from cs.vp.cad.rest.model import AvailableViewers, CadSearchModel


@VpCadInternalApp.json(model=AvailableViewers)
def _get_result(result, request):
    return result.get_available_viewers(request)


@CadSearchInternalApp.json(model=CadSearchModel, request_method='POST')
def _get_matching_cad_variants(cadSearch, request):
    payload = request.json

    baseModel = payload["baseModel"]              # <dict>
    searchValues = payload["searchValues"]        # <dict>

    return cadSearch.get_cad_variants_to_show(baseModel, searchValues, request)
