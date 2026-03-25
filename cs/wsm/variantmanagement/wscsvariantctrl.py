# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module wsmcsvariantctrl

Remote Control for cs.variant cad hide command

This modul only runs under PY3 / 15.8
"""

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

from cdb import sqlapi
from xml.etree import ElementTree
from cs.wsm.variantmanagement.wsmremotecontrol import WsmRemoteControl

# Exported objects
__all__ = []


class WsRemoteControlCsVariants(WsmRemoteControl):
    """
    generates xml file for reduce150percent call for given cadsystem
    """

    def __init__(self, erzeug_system, walk_generator):
        """
        :param erzeug_system: str with doc.erzeug_system
        :param walk_generator: cs.variants.api.
                               occurrence_walk_generator.
                               OccurrenceWalkGenerator
        """
        super(WsRemoteControlCsVariants, self).__init__(None, erzeug_system)
        self.walk_generator = walk_generator

    def get_xml(self):
        """
        :returns utf-8 encoded binary string
        """
        ctrl_lines = [b'<?xml version="1.0" encoding="utf-8"?>']
        root_el = ElementTree.Element("cdbwsinfo")
        command_el = ElementTree.Element("command")
        command_el.text = "reduce150percent"
        root_el.append(command_el)
        parameters_el = ElementTree.Element("parameters")
        root_el.append(parameters_el)
        self._add_model_parameters(self.walk_generator.maxbom, parameters_el)

        from cs.vp.bom.enhancement.plugin import AbstractPlugin

        class CADSourceBomFilterPlugin(AbstractPlugin):
            def __init__(self, cad_source):
                self.cad_source = cad_source

            def get_bom_item_where_stmt_extension(self):
                return "{0}.cadsource = '{1}'".format(
                    self.BOM_ITEM_TABLE_ALIAS, sqlapi.quote(self.cad_source)
                )

        bom_filter_plugin = CADSourceBomFilterPlugin(self.cad_source)
        self.walk_generator.add_bom_filter_plugin(bom_filter_plugin)

        for node in self.walk_generator.walk():
            occurence_id_path = list(node.path)
            if occurence_id_path:
                self._add_hide_information(
                    occurence_id_path, node.active, parameters_el
                )
        ctrl_lines.append(ElementTree.tostring(root_el))
        return b"\n".join(ctrl_lines)
