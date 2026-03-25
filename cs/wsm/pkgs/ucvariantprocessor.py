# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module ucvariantprocessor

This is the documentation for the ucvariantprocessor module.
"""

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import json

from lxml import etree as ElementTree

from cs.documents import Document
from cs.wsm.pkgs.classification import (
    create_empty_classification_from_generic,
    get_drawing_for_generic,
)
from cs.wsm.pkgs.classification import (
    get_classification_for_item,
    class_for_generic,
    ucAvailable,
)

from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase
from cs.wsm.pkgs.pkgsutils import createErrorElement

try:
    from cs.classification.rest.utils import ensure_json_serialiability
except ImportError:
    ensure_json_serialiability = None


# Exported objects
__all__ = []


class GetUCGenericProcessor(CmdProcessorBase):
    """
    Retrieves the model from the generic group of the item of the document,
    which is found within the cad views of the generic group. For now, it can
    just be used for CatiaV5 documents, that consist of a variant as main file.
    """

    name = u"getucgeneric"

    def __init__(self, rootElement):
        """
        :param rootElement: lxml.etree
            <WSCOMMANDS
                cmd="getucgeneric"
                z_nummer="<z_nummer of variant>"
                z_index="<z_index of variant>"
                model_object_id="<id of object"
                view_name="<restrict to view>"
                for_modify="0|1"
            </WSCOMMANDS>
        """
        CmdProcessorBase.__init__(self, rootElement)

    def call(self, resultStream, request):
        """
        :param resultStream: CompressStream
            <GENERICINFO cdb_object_id="<cdb_object_id of the generic> is_generic="0|1" classcode="<classification class>" >
                <ERRORS>
                    <ERROR>
                      error text
                    </ERROR>
                </ERRORS>
                {json classification data}
             </GENERICINFO>
        :return: int
            A number to indicate the status of the processor call.
        """
        root = ElementTree.Element("GENERICINFO")
        errors = ElementTree.Element("ERRORS")
        root.append(errors)
        genericObjectId = self._rootElement.model_object_id
        viewName = self._rootElement.view_name
        for_modify = self._rootElement.for_modify == "1"
        z_nummer = self._rootElement.z_nummer
        z_index = self._rootElement.z_index
        genericDoc = None
        isGeneric = False
        if ensure_json_serialiability is None:
            # "UC version not supported or not available"
            error = createErrorElement("wsm_uc_no_classfication")
            errors.append(error)
        else:
            if not genericObjectId:
                # if w got z_nummer and z_index we assume this is
                # the generic
                if bool(z_nummer) and z_index is not None and not for_modify:
                    genericDoc = Document.ByKeys(z_nummer=z_nummer, z_index=z_index)
            if not genericDoc:
                # get the document of the variant
                if genericObjectId:
                    genericDoc = Document.ByKeys(cdb_object_id=genericObjectId)
            if genericDoc:
                if not for_modify:
                    isGeneric = True
                    (
                        uc_class,
                        classificationData,
                    ) = create_empty_classification_from_generic(
                        genericDoc, viewName, None
                    )
                    if uc_class is not None:
                        root.attrib["classcode"] = uc_class.code
                        root.text = json.dumps(
                            ensure_json_serialiability(classificationData)
                        )
                    else:
                        # "No class found  for '%1-%2' for view: '%3'."
                        error = createErrorElement(
                            "wsm_uc_class_not_found",
                            (genericDoc.z_nummer, genericDoc.z_index, viewName),
                        )
                        isGeneric = False
                else:
                    # in for_modify mode z_nummer , z_index contains key for
                    # variant doc
                    v_doc = Document.ByKeys(z_nummer=z_nummer, z_index=z_index)
                    if v_doc:
                        v_item = v_doc.Item
                        if v_item:
                            uc_class = class_for_generic(genericDoc)
                            if uc_class is not None:
                                classificationData = get_classification_for_item(
                                    uc_class, v_item
                                )
                                root.attrib["classcode"] = uc_class.code
                                root.text = json.dumps(
                                    ensure_json_serialiability(classificationData)
                                )
                                isGeneric = True
                            else:
                                # "No class found  for '%1-%2'"
                                error = createErrorElement(
                                    "wsm_uc_class_not_found",
                                    (genericDoc.z_nummer, genericDoc.z_index, ""),
                                )
                                isGeneric = False
                                errors.append(error)
                        else:
                            # "Modify Variant: Got no Item for document '%1-%2'"
                            error = createErrorElement(
                                "wsm_uc_no_item", (z_nummer, z_index)
                            )
                            isGeneric = False
                            errors.append(error)
                    else:
                        # "Modify Variant: Document not found: '%1-%2'"
                        error = createErrorElement(
                            "wsm_uc_no_document", (z_nummer, z_index)
                        )
                        isGeneric = False
                        errors.append(error)
            else:
                # "The generic document '%1-%2' or '%3' was "
                # "not found."
                error = createErrorElement(
                    "wsm_uc_no_generic", (z_nummer, z_index, genericObjectId)
                )
                errors.append(error)
            root.attrib["is_generic"] = "1" if isGeneric else "0"
        xmlStr = ElementTree.tostring(root, encoding="utf-8")
        resultStream.write(xmlStr)
        return 0


class GetUCDrawingInformationProcessor(CmdProcessorBase):
    """
    Retrieves the drawing from the generic group of the item of the document,
    which is found within the cad views of the generic group. For now, it can
    just be used for CatiaV5 documents, that consist of a variant as main file.
    """

    name = u"getucdrawinginformation"

    def __init__(self, rootElement):
        """
        :param rootElement: lxml.etree
            <WSCOMMANDS
                cmd="getucdrawinginformation"
                gen_object_id="<object_id of generic>"
                view_name="<view_name to determine drawing for>">
            </WSCOMMANDS>
        """
        CmdProcessorBase.__init__(self, rootElement)

    def call(self, resultStream, request):
        """
        :param resultStream: CompressStream
            <DRAWINGINFORMATION cdb_object_id="<cdb_object_id of the drawing>">
                <ERRORS>
                    <ERROR>
                      error text
                    </ERROR>
                </ERRORS>
             </DRAWINGINFORMATION>
        :return: int
            A number to indicate the status of the processor call.
        """
        root = ElementTree.Element("DRAWINGINFORMATION")
        errors = ElementTree.Element("ERRORS")
        root.append(errors)
        if ucAvailable():
            genericObjectId = self._rootElement.gen_object_id
            view_name = self._rootElement.view_name
            genericDoc = Document.ByKeys(cdb_object_id=genericObjectId)
            if genericDoc is not None:
                uc_class = class_for_generic(genericDoc)
                if uc_class is not None:
                    drawing_model = get_drawing_for_generic(genericDoc, view_name)
                    if drawing_model is not None:
                        root.attrib["cdb_object_id"] = drawing_model.cdb_object_id
                    else:
                        error = createErrorElement(
                            "wsm_uc_no_drawing",
                            (uc_class.code, view_name, genericDoc.z_nummer),
                        )
                        errors.append(error)
                else:
                    error = createErrorElement(
                        "wsm_uc_class_not_found", ("", "", genericObjectId)
                    )
                    errors.append(error)
            else:
                error = createErrorElement(
                    "wsm_uc_no_generic", ("", "", genericObjectId)
                )
                errors.append(error)
        else:
            errors.append(createErrorElement("wsm_uc_no_classfication"))
        xmlStr = ElementTree.tostring(root, encoding="utf-8")
        resultStream.write(xmlStr)
        return 0
