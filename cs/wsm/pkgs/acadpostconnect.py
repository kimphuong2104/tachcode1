# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module acadpostconnect

This is the documentation for the acadpostconnect module.
"""

from __future__ import absolute_import

import json
import logging
from cdb import sqlapi
from cdb import cad
from lxml.etree import Element
from lxml import etree as ElementTree

from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes

import six


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"
# Exported objects
__all__ = []


class AcadPostConnect(CmdProcessorBase):
    """
    Can navigate relships
    """

    name = u"acad_post_connect"

    _names = [
        "cadname",
        "cdbname",
        "callue",
        "idattr",
        "cdbrelship",
        "cadismaster",
        "autocheckin",
        "tilecoord",
    ]

    def call(self, resultStream, request):
        """
        navigates the given relation in CDB

        :Returns: integer indicating command success
        """

        cmdResultElement = Element("WSCOMMANDRESULT")
        rootEl = self.getRoot().etreeElem
        cadSystem = rootEl.attrib.get("cad_system")
        self.fill_post_connect(cadSystem, cmdResultElement)
        xmlStr = ElementTree.tostring(cmdResultElement, encoding="utf-8")
        resultStream.write(xmlStr)
        return WsmCmdErrCodes.messageOk

    def fill_post_connect(self, cadSystem, cmdResultElement):
        """
        <WSMCOMMANDS cmd="acad_post_connect" cad_system=>

        </WSMCOMMANDS>
        Result:
        <WSMCOMMANDRESULT>
          <ERROR>text</ERROR>, wenn es einen Fehler gab, gibt es error Eintraege, sonst ist die Liste leer
          <POSTCONNECT>
             {"entity_mapping": mapping,
              "tiles_enabled": tile_handling,
              "zoom_factor": zoom_f}
          <POSTCONNECT>
        </WSMCOMMANDRESULT>
        """
        tile_handling = cad.isTrue(cad.getCADConfValue("ZVS tile handling", cadSystem))
        zoom_str = cad.getCADConfValue("ZVS cadentity zoom factor", cadSystem)
        zoom_f = 0.0
        error = None
        if zoom_str:
            try:
                zoom_f = float(zoom_str)
            except ValueError:
                pass
        mapping = cad.isTrue(cad.getCADConfValue("ZVS entity mapping", cadSystem))
        json_data = {
            "entity_mapping": mapping,
            "tiles_enabled": tile_handling,
            "zoom_factor": zoom_f,
        }
        if mapping:
            config_entries = None
            try:
                objMap = sqlapi.RecordSet2("cadent_objmap")
                config_entries = []
                for rec in objMap:
                    reduced_dict = dict()
                    for n in self._names:
                        reduced_dict[n] = rec[n]
                    config_entries.append(reduced_dict)
                if config_entries:
                    json_data["entities_block_names"] = config_entries
            except Exception as e:
                error = "Mapping Error: %s" % e
                logging.error("AcadPostConnect: Entities are not available %s", error)
        if error:
            errorEl = Element("ERROR")
            errorEl.text = six.text_type(e)
            cmdResultElement.append(errorEl)
        postEl = Element("POSTCONNECT")
        postEl.text = json.dumps(json_data)
        logging.debug("AcadPostConnect: Result: %s", json_data)
        cmdResultElement.append(postEl)
