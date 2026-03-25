#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

__docformat__ = "restructuredtext en"


from cs.platform.web import PlatformApp
from cs.platform.web.root import Internal, get_internal

__APP_NAME__ = "share_objects"


class ShareObjectsApp(PlatformApp):
    pass


@Internal.mount(app=ShareObjectsApp, path=__APP_NAME__)
def _mount_app():
    return ShareObjectsApp()


def get_sharings(request):
    """Try to look up /internal/share_objects"""
    return get_internal(request).child(__APP_NAME__)
