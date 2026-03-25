# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cs.platform.web.base import byname_app
from cs.web.components.configurable_ui import ConfigurableUIApp, SinglePageModel

# #######################################################################################################
# Formula App:
# #######################################################################################################


class FormulaEditorModel(SinglePageModel):
    page_name = "classification-editor-formulas"


class FormulaEditorApp(ConfigurableUIApp):

    def __init__(self):
        super(FormulaEditorApp, self).__init__()


@byname_app.BynameApp.mount(app=FormulaEditorApp, path="classification_editor_formulas")
def _mount_formula_editor_app():
    return FormulaEditorApp()


@FormulaEditorApp.path(path="{class_property_oid}", model=FormulaEditorModel, absorb=True)
def _get_formula_model(absorb, class_property_oid):
    return FormulaEditorModel()


@FormulaEditorApp.view(model=FormulaEditorModel, name="base_path", internal=True)
def _get_formula_base_path(model, request):
    return request.path
