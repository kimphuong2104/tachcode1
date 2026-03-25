#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Contains reusable mixin classes, that provide common functionality to Web UI
configuration classes.
"""

from __future__ import absolute_import
__revision__ = "$Id$"

import json
import os

import cdbwrapc
from cdb import ue


class WithComponentOrConfiguration(object):
    """ Mixin class to factor out the logic to use either a component name or a
        configuration file. A `cdb.objects.Object` subclass that inharits from
        this class is expected to have attributes `config_location` (holding the
        path of e configuration file) and `config_component` (holding the name
        of a React component).
    """

    def _set_component_configuration(self, result_dict):
        """ Determine which configuration option is used, and put the corresponding
            value in the result_dict.
        """
        if self.config_location:
            location = cdbwrapc.build_tag_string(self.config_location, None,
                                                 self.cdb_module_id)
            result_dict["configuration"] = os.path.normpath(location)
        elif self.config_component:
            result_dict["component"] = self.config_component

    def _calculate_config_location_path(self, ctx):
        """
        Calls `build_tag_string` for the attribute ``config_location`` of
        ctx.dialog and writes the result to ``cdb::argument.resolved_location``.
        `self` has to provide the attribute ``cdb_module_id``. The function is
        used to display the real path to the user. It is assumed that this is
        the location of a file. If the file is not there the functions adds
        ```Not found`` to the calculated path.
        """
        configured_path = getattr(ctx.dialog, "config_location")
        module_id = getattr(ctx.dialog, "cdb_module_id", self.cdb_module_id)
        calculated_path = cdbwrapc.build_tag_string(configured_path, None, module_id)
        if calculated_path:
            calculated_path = os.path.normpath(calculated_path)
        if calculated_path and not os.path.exists(calculated_path):
            calculated_path += " (Not found)"
        ctx.set("cdb::argument.resolved_location", calculated_path)

    def _check_config_location_or_component(self, ctx):
        """
        Check if either `config_location` or `config_component` is set.
        Checks also that only one of this attributes contain a value.
        """
        config_location = getattr(ctx.dialog, "config_location", self.config_location)
        config_component = getattr(ctx.dialog, "config_component", self.config_component)
        if not config_location and not config_component:
            raise ue.Exception("csweb_page_config_missing")
        elif config_location and config_component:
            raise ue.Exception("csweb_page_config_duplicated")

    event_map = {
        (("copy", "modify", "info"), "pre_mask"): "_calculate_config_location_path",
        (("create", "copy", "modify"), "dialogitem_change"): "_calculate_config_location_path",
        (("create", "copy", "modify"), "pre"): "_check_config_location_or_component"
    }


class WithJsonProperties(object):
    """ Mixin class to handle `cdb.object.Object` subclasses having a `json_properties`
        attribute, that has to be a valid JSON object.
    """

    def get_properties(self):
        return json.loads(self.json_properties) if self.json_properties else {}

    def _check_json_is_valid(self, _ctx):
        """ If JSON properties are entered, make sure it is valid JSON and is a
            dictionary.
        """
        if self.json_properties:
            try:
                props = self.get_properties()
                if not isinstance(props, dict):
                    raise ue.Exception('csweb_outlet_json_no_dict')
            except ValueError:
                raise ue.Exception('csweb_outlet_invalid_json')

    event_map = {
        (("create", "copy", "modify"), "pre"): "_check_json_is_valid"
    }
