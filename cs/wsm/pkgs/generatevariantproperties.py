#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     generatevariantproperties.py
# Author:   dti
# Creation: 10.02.2016
# Purpose:

"""
Module generatevariantproperties.py

Processor for concluding actions
"""
from __future__ import absolute_import

__docformat__ = "restructuredtext en"


from cdb.sig import connect

from cs.documents import Document
from cs.vp.cad import CADVariant

from cs.wsm.pkgs.servertimingwrapper import timingWrapper, timingContext


@connect(Document, CADVariant, "wsm_get_variant_attrs")
@timingWrapper
@timingContext("GENERATEVARIANTPROPERTIES getVariantAttributes")
def getVariantAttributes(doc, variant, _ctx):
    """
    The user defined code has to return a tuple
    (
     variantId,
     list(
          {"id": name,       # name -> cad config name e.g.: PSI-Artikelnummer
           "value": value,   # value to be written to cad
           "type": "string"  # json conform type
          }
         )
    )
    example:
      ("v1", [{"type": "string", "id": "teilenummer", "value": "v1_t_num"},
              {"type": "string", "id": "t_index", "value": "a"},
              {"type": "string", "id": "benennung", "value": "Default_Var"}])
    """

    def _buildPropertyDict(name, cdbAttr):
        typeMap = {
            "<type 'int'>": "int",
            "<type 'float'>": "float",
            "<type 'datetime.datetime'>": "string",
        }
        t = type(cdbAttr)
        propDict = {"id": name, "value": cdbAttr, "type": typeMap.get(str(t), "string")}
        return propDict

    props = list()
    varId = None
    if isinstance(doc, Document) and isinstance(variant, CADVariant):
        # access to attributes of cad_variant relation
        varId = variant.variant_id
        tNum = variant.teilenummer
        if tNum not in [None, u""]:
            # if teilenummer is u"", then there is no assignment to an item
            props.append(_buildPropertyDict("teilenummer", tNum))
            tIdx = variant.t_index
            if tIdx is not None:
                props.append(_buildPropertyDict("t_index", tIdx))
        # access to attributes of teile_stamm relation
        # if an item was assigned to this variant
        variantItem = variant.Item
        if variantItem:
            # just some item attributes as example
            desc = variantItem.benennung
            if desc is not None:
                props.append(_buildPropertyDict("benennung", desc))
            state = variantItem.status
            if state is not None:
                props.append(_buildPropertyDict("status", state))
    return varId, props
