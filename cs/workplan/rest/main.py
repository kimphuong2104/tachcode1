# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# Version:  $Id$

"""
cs.workplan
"""

__revision__ = "$Id$"
__docformat__ = "restructuredtext en"


import morepath

from cs.platform.web.root import root


class App(morepath.App):
    pass


@root.mount(app=App, path="/cs-workplan-api")
def _mount_app():
    return App()
