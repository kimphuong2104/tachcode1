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

from cdb.objects import Rule
from cdb.objects.org import Organization

from cs.documents import Document

from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes


class FindExportPartnerProcessor(CmdProcessorBase):
    """
    Find organizations to be used for customer export.
    """

    name = u"findexportpartner"

    def call(self, resultStream, request):
        coids = self._parseInput()
        if coids is None:
            return WsmCmdErrCodes.invalidCommandRequest

        for_generating_names = self._rootElement.for_generating_names == "1"
        if for_generating_names:
            partners = self._findExportPartnerForGeneratingNames(coids)
        else:
            partners = self._findExportPartners(coids)

        partners = self._filterNonAccessable(partners)
        self._writeReply(partners, resultStream)
        return WsmCmdErrCodes.messageOk

    def _parseInput(self):
        res = None
        contexts = self._rootElement.getChildrenByName("WSCOMMANDS_CONTEXTOBJECT")
        if len(contexts) > 0:
            res = []
            for context in contexts:
                res.append(context.cdb_object_id)
        return res

    def _findExportPartnerForGeneratingNames(self, coids):
        """
        :param coids: list of cdb_object_ids of documents
        :return: sequence of Organization
        """
        # try to find a unique partner from previously generated partner names
        partners = Document.find_export_partners(coids, only_generated=True)
        if len(partners) == 1:
            (org_id,) = partners
            return Organization.KeywordQuery(cdb_object_id=org_id)

        logging.info(
            u"FindExportPartnerProcessor: returning all matching organizations"
        )
        all_orgs = Organization.Query()
        return self._filterPartners(all_orgs)

    def _filterPartners(self, partners):
        """
        Filter by object rule, if configured.
        :param partners: iterable of Organization
        :return: filtered iterable of Organization
        """
        rule = Rule.ByKeys("WSM: partners for export")
        if rule:
            for p in partners:
                if rule.match(p):
                    yield p
        else:
            for p in partners:
                yield p

    def _findExportPartners(self, coids):
        partners = Document.find_export_partners(coids, only_generated=False)
        orgs = [
            Organization.KeywordQuery(cdb_object_id=org_id)[0] for org_id in partners
        ]
        return orgs

    def _filterNonAccessable(self, partners):
        # cdb_org is not access_controlled in the standard, but maybe it is for some customers
        # so only delivers orgs we are allowed to see
        return [p for p in partners if p.CheckAccess("read")]

    def _writeReply(self, partners, resultStream):
        """
        :param partners: sequence of Organization objects
        """
        logging.info(u"FindExportPartnerProcessor: building reply")
        result = etree.Element("WSCOMMANDRESULT")

        for partner in partners:
            partner_el = etree.Element("PARTNER")
            partner_el.attrib["id"] = partner.cdb_object_id
            partner_el.attrib["name"] = partner.name
            result.append(partner_el)

        xmlStr = etree.tostring(result, encoding="utf-8")
        resultStream.write(xmlStr)
        return WsmCmdErrCodes.messageOk
