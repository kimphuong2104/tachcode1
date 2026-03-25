#!/usr/bin/env python
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from cs.vp.bomcreator.web.rest.main import App
from cs.vp.bomcreator.web.rest.bomtreemodel import BOMTreeModel
from cs.vp.bomcreator.web.rest.bommodel import BOMModel
from cs.vp.bomcreator.web.rest.savebomsmodel import SaveBOMsModel


@App.json(model=BOMTreeModel, request_method="GET")
def bom_tree_view(model, request):
    return model.create_result(request)


@App.json(model=BOMModel, request_method="GET")
def bom_view(model, request):
    return model.create_result(request)


@App.json(model=SaveBOMsModel, request_method="POST")
def save_boms_view(model, request):
    boms = request.json
    return model.save(boms)


@App.json(model=SaveBOMsModel, request_method="POST", name="cancel")
def cancel_view(model, request):
    boms = request.json
    return model.cancel(boms)


@App.json(model=SaveBOMsModel, request_method="POST", name="save-single-bom")
def save_single_bom_view(model, request):
    bom = request.json
    return model.save_single_bom(bom, request)
