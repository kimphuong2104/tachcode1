# !/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cs.platform.web.base import byname_app
from cs.web.components.configurable_ui import ConfigurableUIApp, SinglePageModel

# #######################################################################################################
# Rule App:
# #######################################################################################################


class RuleEditorModel(SinglePageModel):
    page_name = "classification-editor-rules"


class RuleEditorApp(ConfigurableUIApp):

    def __init__(self):
        super(RuleEditorApp, self).__init__()


@byname_app.BynameApp.mount(app=RuleEditorApp, path="classification_editor_rules")
def _mount_rule_editor_app():
    return RuleEditorApp()


@RuleEditorApp.path(path="{class_property_oid}", model=RuleEditorModel, absorb=True)
def _get_rule_model(absorb, class_property_oid):
    return RuleEditorModel()


@RuleEditorApp.view(model=RuleEditorModel, name="base_path", internal=True)
def _get_rule_base_path(model, request):
    return request.path
