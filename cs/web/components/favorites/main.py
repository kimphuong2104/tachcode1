#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Morepath app for Web UI object favorites
"""

from __future__ import absolute_import
__revision__ = "$Id$"

from cs.platform.web import PlatformApp
from cs.platform.web.root import Internal, get_internal


class FavoritesApp(PlatformApp):
    pass


@Internal.mount(app=FavoritesApp, path='favorites')
def mount_favorites_app():
    return FavoritesApp()


def get_favorites_app(request):
    return get_internal(request).child('favorites')
