#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2029 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import

"""
This module extends the `cs.vp.items.Item` class to interact with
Product Costing module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


from cdb import sig, ue
from cs.vp.items import Item


def _on_delete_part_pre(item, ctx):
    from cs.costing.calculations import Component, Product
    if len(Component.KeywordQuery(teilenummer=item.teilenummer,
                                  t_index=item.t_index)) or \
        len(Product.KeywordQuery(teilenummer=item.teilenummer,
                                 t_index=item.t_index)):
        raise ue.Exception("cdbpco_part_referenced")


def _on_delete_part_post(item, ctx):
    from cs.costing.components import PartCost
    PartCost.KeywordQuery(teilenummer=item.teilenummer,
                          t_index=item.t_index).Delete()


# Binds the methods to slots to avoid deleting the part if it assigned to
# calculation component
sig.connect(Item, "delete", "pre")(_on_delete_part_pre)


# Binds the methods to slots to delete the part costs while deleting part
# object
sig.connect(Item, "delete", "post")(_on_delete_part_post)
