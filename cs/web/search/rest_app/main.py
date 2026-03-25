#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Morepath applications for search. There is a "user visible" app that renders
the UI, and an internal app that provides the URLs for doing actual search, and
can return settings etc. that can't be retrieved from the generic REST API.
"""

from __future__ import absolute_import
__revision__ = "$Id$"


from cs.platform.web import PlatformApp
from cs.platform.web.root import Internal


class InternalSearchApp(PlatformApp):
    """ Internal app for search.
    """
    pass


@Internal.mount(app=InternalSearchApp, path="search")
def _mount_internal_app():
    return InternalSearchApp()
