#!/usr/bin/env python
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Widget plugin for cs.pcs.dashboard.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import elink, sig

__all__ = []


@elink.using_template_engine("chameleon")
class PluginImpl(elink.Application):

    __plugin_macro_file__ = "widget_projectteam.html"


# lazy initialization
app = None


@sig.connect("cs.pcs.dashboard.getplugins")
def get_plugin():
    global app  # pylint: disable=global-statement
    if app is None:
        app = PluginImpl()
    return (7, app)
