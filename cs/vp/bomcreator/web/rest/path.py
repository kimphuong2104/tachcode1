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


@App.path(path='bom-tree/{root}', model=BOMTreeModel)
def get_bom_tree_model(app, root, cadsource=None):
    return BOMTreeModel(root, cadsource)


@App.path(path='bom/{instance_id}', model=BOMModel)
def get_bom_tree_model(app, instance_id):
    return BOMModel(instance_id)


@App.path(path='save-boms', model=SaveBOMsModel)
def get_save_boms_model(app):
    return SaveBOMsModel()
