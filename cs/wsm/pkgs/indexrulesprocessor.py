#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2011 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     cdbfiletypes.py
# Author:   wme
# Creation: 05.10.11
# Purpose:

"""
Fetch the list of configured index update rules
"""

from __future__ import absolute_import

import six
from lxml.etree import Element
from lxml import etree as ElementTree

from cs.wsm.index_helper import IndexUpdateRule
from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes


class IndexRulesProcessor(CmdProcessorBase):
    """
    Handler class for indexrules command.
    """

    name = u"indexrules"

    def __init__(self, rootElement):
        CmdProcessorBase.__init__(self, rootElement)

    def call(self, resultStream, request):
        """
        Retrieve index rules.

        :Returns:
            errCode : integer indicating command success
        """
        elements = Element("CDBINDEXRULES")
        index_rules = IndexUpdateRule.Query(order_by=("sort_val", "name"), lazy=0)

        for rule in index_rules:
            elements.append(self._rule_to_element(rule))

        result = Element("WSCOMMANDRESULT")
        result.append(elements)

        xmlStr = ElementTree.tostring(result, encoding="utf-8")
        resultStream.write(xmlStr)
        return WsmCmdErrCodes.messageOk

    def _rule_to_element(self, rule):
        rule_element = Element("CDBINDEXRULE")
        rule_element.attrib["id"] = rule.cdb_object_id
        rule_element.attrib["name"] = rule.name
        defaultName, namesByLang = rule.get_names()
        rule_element.text = defaultName
        langsElement = Element("CDBINDEXRULEBYLANGS")
        for lang, name in six.iteritems(namesByLang):
            langElement = Element("CDBINDEXRULEBYLANG")
            langElement.attrib["lang"] = lang
            langElement.attrib["name"] = name
            langsElement.append(langElement)
        rule_element.append(langsElement)
        try:
            rule_element.attrib["rule_type"] = (
                six.text_type(rule.rule_type) if rule.rule_type is not None else ""
            )
        except AttributeError:
            pass  # pre 15.3
        return rule_element
