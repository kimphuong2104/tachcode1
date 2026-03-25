#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#


"""
Register portfolio navigator plugin.
"""


from cdb import sig
from cdb import elink

__all__ = []


@elink.using_template_engine("chameleon")
class PortfolioNavigatorPlugin(elink.Application):
    __folder_content_class__ = "cdbvp_product"


# lazy initialization
app = None


@sig.connect("cs.portfolio.navigator.getplugins")
def get_plugin():
    global app
    if app is None:
        app = PortfolioNavigatorPlugin()
    return (1, app)
