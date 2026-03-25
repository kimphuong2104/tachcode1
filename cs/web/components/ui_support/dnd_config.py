#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import json

from . import App
from cdb import ElementsError
from cs.platform.web.dnd_target import DropConfiguration
from cdb.platform.mom.entities import CDBClassDef

import logging

LOGGER = logging.getLogger(__name__)

__revision__ = "$Id$"


class DropConfigurationModel(object):

    def __init__(self, target_id):
        self.drop_configurations = DropConfiguration.KeywordQuery(drop_target_id=target_id)

    def get_properties(self, config):
        return json.loads(config.json_properties) if config.json_properties else {}

    def _add_subclass_configs(self, source_type, config, dnd_config):
        try:
            clsdef = CDBClassDef(source_type)
            subclasses = clsdef.getSubClassNames(False)
            if subclasses:
                for subclass in subclasses:
                    if subclass not in dnd_config:
                        dnd_config[subclass] = config
                        self._add_subclass_configs(subclass, config, dnd_config)
        except ElementsError as e:
            LOGGER.error(e)
        return dnd_config

    def get_configurations(self):
        if self.drop_configurations is not None:
            dnd_config = {
                config.source_type: {
                    "allow_link": config.allow_link,
                    "fn_link": config.fn_link,
                    "allow_copy": config.allow_copy,
                    "fn_copy": config.fn_copy,
                    "allow_move": config.allow_move,
                    "fn_move": config.fn_move,
                    "json_properties": self.get_properties(config),
                } for config in self.drop_configurations
            }
            result = dict(dnd_config)
            for source_type, config in dnd_config.items():
                self._add_subclass_configs(source_type, config, result)
            return result
        else:
            return {}


@App.path(path='/drop_target/{target_id}', model=DropConfigurationModel)
def _web_drop_configurations(target_id):
    return DropConfigurationModel(target_id)


@App.json(model=DropConfigurationModel, request_method='GET')
def _get_drop_configurations(self, request):
    return {
        "configs": self.get_configurations()
    }
