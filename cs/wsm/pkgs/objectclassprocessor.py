# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2023 CONTACT Software GmbH.
# All rights reserved.
# https://www.contact-software.com/

"""
Module objectclassprocessor

TProvides method for getting the classname for given objectids
"""

from __future__ import absolute_import


__docformat__ = "restructuredtext en"


from lxml import etree as ElementTree
from cdb.objects import ByID
from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes


class ObjectToClass(CmdProcessorBase):
    """
    Retrievs the cdb_classnames fuer given object-ids
    """

    name = u"getclassforobjectids"

    def __init__(self, rootElement):
        """
        :param rootElement: lxml.etree
        <WSCOMMAND cmd="getclassforobjectids">
          <OBJECTIDLIST>
            <CDB_OBJECT_ID cdb_object_id="<id>" />
            ...
          </OBJECTIDLIST>
        </WSCOMMAND>
        Reply:
        <OBJECTIDLIST>
          <CDB_OBJECT_ID_CLASS cdb_object_id= classname=/>
        OBJECTIDLIST>
        """
        CmdProcessorBase.__init__(self, rootElement)

    def _getClassForId(self, objId):
        clname = None
        obj = ByID(objId)
        if obj:
            clname = obj.GetClassDef().getClassname()
        return clname

    def call(self, resultStream, request):
        """
        :param resultStream: CompressStream
        <OBJECTIDLIST>
          <CDB_OBJECT_ID_CLASS cdb_object_id= classname=/>
        OBJECTIDLIST>

        :return: int
            A number to indicate the status of the processor call.
        """
        result_id_list = ElementTree.Element("OBJECTIDLIST")
        obj_id_list_el = self._rootElement.etreeElem.find("OBJECTIDLIST")
        if obj_id_list_el:
            for obj_id_el in obj_id_list_el.getchildren():
                if obj_id_el.tag == "CDB_OBJECT_ID":
                    obj_id = obj_id_el.attrib.get("cdb_object_id")
                    if obj_id:
                        classname = self._getClassForId(obj_id)
                        if classname:
                            res_obj = ElementTree.Element("CDB_OBJECT_ID_CLASS")
                            res_obj.attrib["cdb_object_id"] = obj_id
                            res_obj.attrib["classname"] = classname
                            result_id_list.append(res_obj)
        xmlStr = ElementTree.tostring(result_id_list, encoding="utf-8")
        resultStream.write(xmlStr)
        return WsmCmdErrCodes.messageOk
