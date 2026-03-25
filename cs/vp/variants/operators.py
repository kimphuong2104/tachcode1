#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Module cs.vp.variants.operators

This is the documentation for the cs.vp.variants.operators module.

"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from collections import namedtuple
import operator

from cdb.platform.gui import CDBCatalog
from cdb.objects import Forward

fProperty = Forward("cs.vp.variants.properties.Property")

OperatorInfo = namedtuple('OperatorInfo', ('func', 'inverse', 'sap'))

_OpInfos = {
    '=': OperatorInfo(operator.eq, '!=', 'EQ'),
    '!=': OperatorInfo(operator.ne, '=', 'NE'),
    '<': OperatorInfo(operator.lt, '>=', 'LT'),
    '<=': OperatorInfo(operator.le, '>', 'LE'),
    '>': OperatorInfo(operator.gt, '<=', 'GT'),
    '>=': OperatorInfo(operator.ge, '<', 'GE'),
    '\N{BALLOT BOX WITH CHECK}': OperatorInfo(lambda val, _: val is not False, '\N{BALLOT BOX}', ''),
    '\N{BALLOT BOX}': OperatorInfo(lambda val, _: val is False, '\N{BALLOT BOX WITH CHECK}', '')
}


class OperatorCatalog(CDBCatalog):
    def __init__(self):
        CDBCatalog.__init__(self)

    def handlesSimpleCatalog(self):
        return True

    def getCatalogEntries(self):
        product_object_id = self.getInvokingDlgValue("product_object_id")
        property_id = self.getInvokingDlgValue("property_id")
        value = self.getInvokingDlgValue("enum_value")
        prop = fProperty.ByKeys(property_id, product_object_id)
        if prop:
            if not value:
                return ['\N{BALLOT BOX WITH CHECK}', '\N{BALLOT BOX}']
            if prop.data_type in ["alphanumeric", "boolean"]:
                return ["!=", "="]
            else:
                return sorted(_OpInfos.keys())[:-2]
        else:
            return []


def eval_term(left, right, op):
    return _OpInfos[op].func(left, right)


def inverse_operator(op):
    return _OpInfos[op].inverse


def sap_operator(op):
    return _OpInfos[op].sap
