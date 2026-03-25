#!/usr/bin/env python
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#


"""
Register portfolio navigator plugin.
"""


from cdb import elink, sig
from cs.shared.elink_plugins import check_license

__all__ = []


@elink.using_template_engine("chameleon")
@check_license.check_license("PROJECTS_001")
class PortfolioNavigatorPlugin(elink.Application):
    __folder_content_class__ = "cdbpcs_project"

    __kosmodromtools__ = None

    def get_kosmodrom_tools(self):
        if self.__kosmodromtools__ is None:
            from cs.pcs.dashboard import KosmodromTools

            self.__kosmodromtools__ = KosmodromTools
        return self.__kosmodromtools__


# lazy initialization
app = None


@sig.connect("cs.portfolio.navigator.getplugins")
def get_plugin():
    global app  # pylint: disable=global-statement
    if app is None:
        app = PortfolioNavigatorPlugin()
    return (2, app)
