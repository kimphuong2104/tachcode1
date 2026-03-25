# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module ucupdatecmd

This is the documentation for the ucupdatecmd module.
"""

from __future__ import absolute_import


__docformat__ = "restructuredtext en"


# Exported objects
__all__ = []

import json

from lxml import etree as ElementTree
from cdb import ue
from cs.wsm.pkgs.pkgsutils import createErrorElement, createInfoElement

from cs.vp.items import Item
from cs.documents import Document

from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase
from cs.wsm.pkgs.classification import (
    merge_classication,
    class_for_generic,
    ucAvailable,
)


class UCGenericUpdateProcessor(CmdProcessorBase):
    """
    Retrieves the drawing from the generic group of the item of the document,
    which is found within the cad views of the generic group. For now, it can
    just be used for CatiaV5 documents, that consist of a variant as main file.
    """

    name = u"updateuc"

    def __init__(self, rootElement):
        """
        :param rootElement: lxml.etree
        # remove values because we changed values
        # <WSCOMMANDS cmd="updateuc">
        #  <UCUPDATE cls="<classname> generic="generic_object_id">
        #  <KEY name="name" val="val"/>
        #  <KEY name="name" val="val"/>
        #    classification jsondata
        #  </UCUPDATE>
        #  ...
        #  <UCUPDATE cls="<classname>">
        #  <KEY name="name" val="val"/>
        #  <KEY name="name" val="val"/>
        #    classification jsondata
        #  </UCUPDATE>
        # </WSCOMMANDS>
        # returns:

        """
        CmdProcessorBase.__init__(self, rootElement)

    def call(self, resultStream, request):
        """
        :param resultStream: CompressStream
        # <UCRESULT>
        #   <ERROR>
        #   <ERROR>
        #   <INFO>
        # </UCRESULT>
        :return: int
            A number to indicate the status of the processor call.
        """
        root = ElementTree.Element("UCRESULT")
        errors = root
        if ucAvailable():
            for child in self._rootElement.etreeElem:
                if child.tag == "UCUPDATE":
                    keys = {}
                    for keyElement in child:
                        keys[keyElement.attrib["name"]] = keyElement.attrib["val"]
                    clsname = child.attrib["cls"]
                    classificationData = json.loads(child.text)
                    generic_object_id = child.attrib["generic"]
                    updateError = self._updateClassification(
                        generic_object_id, clsname, keys, classificationData
                    )
                    if updateError is not None:
                        errors.append(updateError)
        else:
            # "Server does not support classification"
            errors.append(createErrorElement("wsm_uc_no_classfication"))
        xmlStr = ElementTree.tostring(root, encoding="utf-8")
        resultStream.write(xmlStr)

    def _updateClassification(
        self, generic_object_id, clsname, keys, classificationData
    ):
        """
        merges classification for given values
        """
        # we only support clsname part
        error = None
        if clsname == "part":
            item = Item.ByKeys(**keys)
            if item is not None:
                gen_doc = Document.ByKeys(cdb_object_id=generic_object_id)
                if gen_doc is not None:
                    classficationClass = class_for_generic(gen_doc)
                    if classficationClass is not None:
                        try:
                            merge_classication(
                                classficationClass.code, classificationData, item
                            )
                        except ue.Exception as e:
                            # "Classification data not modified Reason: %1"
                            error = createInfoElement(
                                "wsm_uc_modification_failed", ("%s" % e)
                            )
                    else:
                        # Classification update: Invalid generic. No classfication class found."
                        error = createErrorElement(
                            "wsm_uc_class_not_found",
                            (gen_doc.z_nummer, gen_doc.z_index, ""),
                        )
            else:
                # "Classification update: Part doesn't exists"
                error = createErrorElement("wsm_uc_not_existing_item", [clsname])
        else:
            # "Classification update not supported for class: %1"
            error = createErrorElement("wsm_uc_not_part", [clsname])
        return error
