# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module ucobjectinfos

This is the documentation for the ucobjectinfos module.
"""

from __future__ import absolute_import


__docformat__ = "restructuredtext en"


# Exported objects
__all__ = []

import json
from lxml import etree as ElementTree
from cs.wsm.pkgs.pkgsutils import createErrorElement

from cdb.objects import ByID


from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase
from cs.wsm.pkgs.classification import ucAvailable, get_classification


try:
    from cs.classification.rest.utils import ensure_json_serialiability
except ImportError:
    ensure_json_serialiability = None


class UCObjectInfos(CmdProcessorBase):
    """
    Retrives classification information and object attributes for given object id
    """

    name = u"getucobjectinfos"

    def __init__(self, rootElement):
        """
        :param rootElement: lxml.etree
        # remove values because we changed values
        # <WSCOMMANDS cmd="getucobjectinfos" cdb_object_id="<objid>" >
        """
        CmdProcessorBase.__init__(self, rootElement)

    def call(self, resultStream, request):
        """
        :param resultStream: CompressStream
        # <UCOBJECTINFOS>
        #   <ERRORS>
        #     <ERROR>
        #     <ERROR>
        #   </ERROS>
        #    json data {"classification": ,
        #               "objectattrs"}
        #   </PROPNAMES>
        # </UCOBJECTINFOS>
        :return: int
            A number to indicate the status of the processor call.
        """
        root = ElementTree.Element("UCOBJECTINFOS")
        errorsEl = ElementTree.Element("ERRORS")
        errors = []
        if ucAvailable():
            obj_id = self._rootElement.cdb_object_id
            obj = ByID(obj_id)
            if obj is not None:
                clinfo = get_classification(obj)
                jsonData = {"classfication": clinfo, "objectattrs": dict(obj)}
                root.text = json.dumps(ensure_json_serialiability(jsonData))
            else:
                errors.append(createErrorElement("wsm_uc_unknown_object"))
        else:
            errors.append(createErrorElement("wsm_uc_no_classfication"))
        if errors:
            for e in errors:
                errorsEl.append(e)
            root.append(errorsEl)
        xmlStr = ElementTree.tostring(root, encoding="utf-8")
        resultStream.write(xmlStr)
        return 0
