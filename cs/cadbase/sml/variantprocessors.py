# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module variantprocessors

This is the documentation for the variantprocessors module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import cad


class SmlAttr(object):
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.dinAttrs = dict()

    def addDinAttr(self, name, value):
        self.dinAttrs[name] = value


def retrieveSmlAttributes(item, currentcad):
    oldcad = cad.get_cad_system()
    try:
        cad.set_cad_system(currentcad)
        smldata = cad.get_sml_data("", "", item.teilenummer, item.t_index, ".",
                                   currentcad)
    finally:
        cad.set_cad_system(oldcad)

    smlAttrList = cad.getCADConfValue("SML Attributelist", currentcad)
    smlValues = dict()
    smlDataList = smldata.split("@")[1:]

    i = 0
    dinMerkmal = cad.getCADConfValue("SML Attribut CAD parameter name",
                                     currentcad)
    while i < len(smlDataList) - 2:
        # beginnt immer mit einem Attributenamen
        # gefolgt vom Wert und evtl. DIN Attribut
        smlAttr = SmlAttr(smlDataList[i], smlDataList[i + 1])
        i += 2
        while i < len(smlDataList) - 2:
            name = smlDataList[i]
            isDinAttr = name.startswith("mm_") or name in smlAttrList
            value = smlDataList[i + 1]
            if isDinAttr:
                smlAttr.addDinAttr(name, value)
                i += 2
            else:
                break
        if dinMerkmal and smlAttr.dinAttrs.get(dinMerkmal):
            smlValues[smlAttr.dinAttrs.get(dinMerkmal)] = smlAttr
        else:
            smlValues[smlAttr.name] = smlAttr
    return smlValues
