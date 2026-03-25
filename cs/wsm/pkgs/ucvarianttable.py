# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module ucvarianbttable

This is the documentation for the ucvarianbttable module.
"""

from __future__ import absolute_import


__docformat__ = "restructuredtext en"


# Exported objects
__all__ = []

import json
from lxml import etree as ElementTree
from cs.wsm.pkgs.pkgsutils import createErrorElement

from cs.vp.items import Item
from cs.documents import Document

from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase
from cs.wsm.pkgs.classification import class_for_generic, ucAvailable
from cs.wsm.pkgs.classification import (
    add_additonal_property_infos,
    get_familytable_for_class,
)

try:
    from cs.classification.rest.utils import ensure_json_serialiability
except ImportError:
    ensure_json_serialiability = None


class UCGenericTableUpdateProcessor(CmdProcessorBase):
    """
    Retrieves the drawing from the generic group of the item of the document,
    which is found within the cad views of the generic group. For now, it can
    just be used for CatiaV5 documents, that consist of a variant as main file.
    """

    name = u"getcaducvarianttable"

    def __init__(self, rootElement):
        """
        :param rootElement: lxml.etree
        # remove values because we changed values
        # <WSCOMMANDS cmd="updateuc" z_nummer="<genericnumber>", z_index="<genericindex>" >
        """
        CmdProcessorBase.__init__(self, rootElement)

    def call(self, resultStream, request):
        """
        :param resultStream: CompressStream
        # <UCVARRESULT>
        #   <ERRORS>
        #     <ERROR>
        #     <ERROR>
        #     <INFO>
        #   <ERORRS>
        #   <VARIANTS classcode=<uc_class_code for generic>
        #     <VARIANT teilenummer="" t_index="">
        #       json_classification_info
        #     </VARIANT>
        #   <VARIANTS>
        #   <PROPNAMES>
        #     json da
        #   </PROPNAMES>
        # </UCVARRESULT>
        :return: int
            A number to indicate the status of the processor call.
        """
        root = ElementTree.Element("UCVARRESULT")
        errors = ElementTree.Element("ERRORS")
        variants = ElementTree.Element("VARIANTS")
        propnames = ElementTree.Element("PROPNAMES")
        root.append(errors)
        root.append(variants)
        root.append(propnames)
        if ucAvailable():
            gen_number = self._rootElement.z_nummer
            gen_index = self._rootElement.z_index
            gen_doc = Document.ByKeys(z_nummer=gen_number, z_index=gen_index)
            if gen_doc is not None:
                uc_class = class_for_generic(gen_doc)
                if uc_class is not None:
                    variants.attrib["classcode"] = uc_class.code
                    for (item, cl_data) in get_familytable_for_class(
                        uc_class.code, Item
                    ):
                        variant = ElementTree.Element("VARIANT")
                        variant.attrib["teilenummer"] = item.teilenummer
                        variant.attrib["t_index"] = item.t_index
                        variant.text = json.dumps(ensure_json_serialiability(cl_data))
                        variants.append(variant)
                    property_info_container = dict()
                    add_additonal_property_infos(uc_class, property_info_container)
                    property_names = property_info_container["_prop_names_"]
                    propnames.text = json.dumps(property_names)
            else:
                # "No class found  for '%1-%2'"
                error = createErrorElement(
                    "wsm_uc_class_not_found", (gen_number, gen_index, "")
                )
                errors.append(error)
        else:
            errors.append(createErrorElement("wsm_uc_no_classfication"))
        xmlStr = ElementTree.tostring(root, encoding="utf-8")
        resultStream.write(xmlStr)
        return 0
