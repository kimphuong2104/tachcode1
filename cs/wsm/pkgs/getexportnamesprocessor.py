#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from __future__ import absolute_import
from lxml import etree
import logging

from cs.documents import Document

from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes


class GetExportNamesProcessor(CmdProcessorBase):
    name = u"getexportnames"

    def call(self, resultStream, request):
        coids = self._parseInput()
        if coids is None:
            return WsmCmdErrCodes.invalidCommandRequest

        partner_id = self._rootElement.export_partner_id
        record_set = Document.get_export_names(coids, partner_id)
        self._writeReply(record_set, resultStream)
        return WsmCmdErrCodes.messageOk

    def _parseInput(self):
        res = None
        contexts = self._rootElement.getChildrenByName("WSCOMMANDS_CONTEXTOBJECT")
        if len(contexts) > 0:
            res = []
            for context in contexts:
                res.append(context.cdb_object_id)
        return res

    def _writeReply(self, record_set, resultStream):
        logging.info(u"GetExportNamesProcessor: building reply")
        result = etree.Element("WSCOMMANDRESULT")

        for record in record_set:
            partner_fn = etree.Element("PARTNERNAME")
            partner_fn.attrib["cdb_object_id"] = record.cdb_object_id
            partner_fn.attrib["cdbf_object_id"] = record.cdbf_object_id
            partner_fn.attrib["cdbf_name"] = record.cdbf_name
            partner_fn.attrib["partner_filename"] = record.partner_filename
            result.append(partner_fn)

        xmlStr = etree.tostring(result, encoding="utf-8")
        resultStream.write(xmlStr)
        return WsmCmdErrCodes.messageOk
