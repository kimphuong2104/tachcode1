# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cs.platform.web.base import byname_app
from cs.web.components.configurable_ui import ConfigurableUIApp, SinglePageModel

# #######################################################################################################
# Constraint App:
# #######################################################################################################


class ConstraintEditorModel(SinglePageModel):
    page_name = "classification-editor-constraints"


class ConstraintEditorApp(ConfigurableUIApp):

    def __init__(self):
        super(ConstraintEditorApp, self).__init__()


@byname_app.BynameApp.mount(app=ConstraintEditorApp, path="classification_editor_constraints")
def _mount_constraint_editor_app():
    return ConstraintEditorApp()


@ConstraintEditorApp.path(path="{class_oid}", model=ConstraintEditorModel, absorb=True)
def _get_constraint_model(absorb, class_oid):
    return ConstraintEditorModel()


@ConstraintEditorApp.view(model=ConstraintEditorModel, name="base_path", internal=True)
def _get_constraint_base_path(model, request):
    return request.path
