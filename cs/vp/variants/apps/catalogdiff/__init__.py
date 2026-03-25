#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module catalogdiff

This is the documentation for the catalogdiff module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
from cdb import elink

from cs.vp.variants.properties import Property


class Page(elink.Template):
    __template__ = "catalogdiff.html"

    def render(self, context, product_object_id, prop_id):
        prop = Property.ByKeys(product_object_id=product_object_id,
                               id=prop_id)

        propdiff, values, new_values = prop.get_differences_from_catalogue()

        return {"propdiff": propdiff,
                "values": values,
                "new_values": new_values}


@elink.using_template_engine("chameleon")
class Main(elink.Application):
    def __init__(self):
        super(Main, self).__init__("")
        self.add("", Page())

app = elink.AppMaker(Main)
