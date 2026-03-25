#!/usr/bin/env python
# -*- mode: python; coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Compute the differences between two product structures.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import collections

from cdb import util

from cs.vp.bom.enhancement import FlatBomEnhancement
from cs.vp.bom.productstructure import ProductStructure
from cs.vp.bom.productstructure import xBOMQuantityDiff
from cs.vp.items import Item

__all__ = [
    "get_differences", "diff_plugins"
]

FILTER_RULE = "mBOM Manager: Ignore differences"
DBERR_ORA_CYCLE_DETECTED = -32044
DBERR_MSSQL_RECURSION = 530


class RecursiveBomException(Exception):

    def __init__(self, nativeDBError, bom_desc):
        super(RecursiveBomException, self)
        self.bom_desc = bom_desc
        self.nativeDBError = nativeDBError

    def getBomDescription(self):
        return self.bom_desc

    def getNativeDBError(self):
        return self.nativeDBError


def get_differences(
        lbom: Item,
        lbom_enhancement: FlatBomEnhancement | None,
        rbom: Item,
        rbom_enhancement: FlatBomEnhancement | None,
        product_object_id: str | None = None,
        **kwargs
) -> list:
    """
    Computes the differences between two BOMs, e.g. an engineering BOM and a manufacturing BOM.

    .. important ::

        This method only works when the attribute ``mbom_mapping_tag`` of
        the bom positions is set correctly.

    :param lbom: the engineering BOM
    :type lbom: an instance of ``cs.vp.items.Item``

    :param lbom_enhancement: Used to enhance the query for the lBOM
    :type lbom_enhancement: cs.vp.bom.enhancement.FlatBomEnhancement

    :param rbom: the manufacturing BOM
    :type rbom: an instance of ``cs.vp.items.Item``

    :param rbom_enhancement: Used to enhance the query for the rBOM
    :type rbom_enhancement: cs.vp.bom.enhancement.FlatBomEnhancement

    :return: an iterable which provides dictionary-like objects with
        the following keys:

        * teilenummer
        * t_index
        * lbom_quantity
        * rbom_quantity
        * item_object_id
    """
    # filter out wanted differences
    result = collections.defaultdict(dict)

    for plugin in diff_plugins:
        plugin(lbom, lbom_enhancement, rbom, rbom_enhancement, product_object_id, result, **kwargs)

    return list(result.values())


def get_quantity_diffs(
        lbom: Item,
        lbom_enhancement: FlatBomEnhancement,
        rbom: Item,
        rbom_enhancement: FlatBomEnhancement,
        product_object_id: str,
        result: dict,
        **kwargs
) -> None:
    lps = ProductStructure(lbom, lbom_enhancement)
    rps = ProductStructure(rbom, rbom_enhancement)

    use_mapping = kwargs.get('use_mapping', True)

    differ = xBOMQuantityDiff(lps, rps)
    data = differ.get_differences_data(use_mapping)
    result.update(data)


# diff_plugins can be extended to add some other logic of computing differences
diff_plugins = [get_quantity_diffs]


# -- utils ----------------------------------------------------------------


class HintImpl(object):
    def __init__(self):
        self.prop = util.get_prop('flfo')

    def format_float(self, val):
        format_string = "%%%sg" % self.prop
        val = format_string % val
        return val

    def calculate(self, diffs: list[dict], litem: Item, ritem: Item) -> list[dict]:
        result = list(map(dict, diffs))
        for values in result:
            if 'lbom_quantity' in values and 'rbom_quantity' in values:
                diff_amount = values['lbom_quantity'] - values["rbom_quantity"]
                has_index = self._has_index(result, values)
                values["hint"] = "%s%s" % ("+" if diff_amount > 0 else "",
                                           self.format_float(diff_amount))
                if has_index:
                    values["hint"] += ", " + util.get_label("cdbvp_elink_diffutil_index_exchange")
        return result

    def _has_index(self, differences, source_diff):
        for difference in differences:
            if difference["teilenummer"] == source_diff["teilenummer"] and \
                difference["t_index"] != source_diff["t_index"]:
                return True
        return False


_hint_impl = HintImpl


def set_hint_impl(cls):
    global _hint_impl
    _hint_impl = cls


def calculate_hints(diffs: list[dict], litem: Item, ritem: Item) -> list[dict]:
    return _hint_impl().calculate(diffs, litem, ritem)
