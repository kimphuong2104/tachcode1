# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module navigaterelshiprocessor

This is the documentation for the navigaterelshiprocessor module.
"""

from __future__ import absolute_import

import json
from lxml.etree import Element
from lxml import etree as ElementTree

from cdb.objects import ByID
from cdb import ElementsError

from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes

import six

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"
# Exported objects
__all__ = []


class NavigateRelshipProcessor(CmdProcessorBase):
    """
    Can navigate relships
    """

    name = u"navigate_relship"

    def call(self, resultStream, request):
        """
        navigates the given relation in CDB

        :Returns: integer indicating command success
        """

        cmdResultElement = Element("WSCOMMANDRESULT")
        self.navigate_relship(cmdResultElement)
        xmlStr = ElementTree.tostring(cmdResultElement, encoding="utf-8")
        resultStream.write(xmlStr)
        return WsmCmdErrCodes.messageOk

    def _navigate_relship_to_list(self, obj, relShip, conditions={}):
        """
        navigates relship by name with condifition
        :returns {"columndefs": [ (<attrname>, <columnname>))]
                  "data": [ {"dstobj": {<attrname>: <value>},
                             "tabledata": {<attrname>: <columnname>}}]
                  "dialogtitle": <Dialoglabel>}
        """
        objh = obj.ToObjectHandle()
        dstHandles = objh.navigate_Relship(relShip, conditions)
        dstVisibleRows = objh.navigate_relship_tableresult(relShip, "", conditions)
        dstObjs = []
        clsname = None
        columnDefs = dstVisibleRows.getTabDefinition().getColumns()
        colnames = []  # dict from attrname to columnname
        for colDef in columnDefs:
            # only strings, no icons
            if colDef.getColumnKind() == 1 and colDef.getDisplayType() == 0:
                colnames.append((colDef.getAttribute(), colDef.getName()))
        for i, dst in enumerate(dstHandles):
            dstAttributes = dict()
            dstClass = dst.getClassDef()
            if clsname is None:
                clsname = dstClass.getClassname()
            for a in dstClass.getAttributeDefs():
                k = a.getName()
                v = dst.getValue(k, False)
                dstAttributes[k] = v
            rowData = dstVisibleRows.getRowData(i)
            visibleAttrs = dict()
            for colindex, colDef in enumerate(columnDefs):
                attrName = colDef.getAttribute()
                # Standard Attr, no icons, Checkbox,...
                if colDef.getColumnKind() == 1 and colDef.getDisplayType() == 0:
                    visibleAttrs[attrName] = rowData[colindex]
            dstObjs.append({"dstobj": dstAttributes, "tabledata": visibleAttrs})
        return (
            {
                "data": dstObjs,
                "columnnames": colnames,
                "dialogtitle": dstVisibleRows.getLabel(),
            },
            clsname,
        )

    def navigate_relship(self, cmdResultElement):
        """
        Input:
        <WSMCOMMANDS cmd="naviagte_relship" src_obj_id="", rel_name="">
          <FILTER>
            json dict with key value pairs
          </FILTER>
        </WSMCOMMANDS>
        Result:
        <WSMCOMMANDRESULT>
          <ERROR>text</ERROR>, wenn es einen Fehler gab, gibt es error Eintraege, sonst ist die Liste leer
          <OBJECTS classname="<classname>" >
             json list of key/value dicts
          </OBJECTS>
        </WSMCOMMANDRESULT>
        """
        rootEl = self.getRoot().etreeElem
        srcId = rootEl.attrib.get("src_obj_id")
        srcObj = ByID(srcId)
        if srcObj is not None:
            relShipFilter = rootEl.find("FILTER")
            if relShipFilter and relShipFilter.text:
                filterDict = json.loads(relShipFilter.text)
            else:
                filterDict = None
            resultObjs = []
            try:
                resultObjs, clsname = self._navigate_relship_to_list(
                    srcObj, rootEl.attrib.get("rel_name"), filterDict
                )
                objects = Element("OBJECTS")
                objects.attrib["classname"] = clsname
                objects.text = json.dumps(resultObjs)
                cmdResultElement.append(objects)
            except ElementsError as e:
                errorEl = Element("ERROR")
                errorEl.text = six.text_type(e)
                cmdResultElement.append(errorEl)
