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

    __plugin_macro_file__ = "widget_projectoverview.html"
    __dashboard_widget_links__ = {}
    __milestone_labels__ = {}

    def get_widget_links(self, name):
        if name not in self.__dashboard_widget_links__:
            widgets = sig.emit("cs.pcs.dashboard.widget", name)()
            if widgets:
                self.__dashboard_widget_links__[name] = getattr(
                    widgets[0][1], "dashboard_widget", None
                )
            else:
                self.__dashboard_widget_links__[name] = None
        return self.__dashboard_widget_links__[name]

    def get_milestone_label(self, mstone, field_name):
        if mstone:
            clsname = mstone.GetClassname()
            if clsname not in self.__milestone_labels__:
                self.__milestone_labels__[clsname] = {}
            if field_name not in self.__milestone_labels__[clsname]:
                self.__milestone_labels__[clsname][field_name] = mstone.Label(
                    field_name
                )
            return self.__milestone_labels__[clsname][field_name]
        return field_name


# lazy initialization
app = None


@sig.connect("cs.pcs.dashboard.widget", "projectoverview")
@sig.connect("cs.pcs.dashboard.getplugins")
def get_plugin():
    global app  # pylint: disable=global-statement
    if app is None:
        app = PluginImpl()
    return (1, app)
