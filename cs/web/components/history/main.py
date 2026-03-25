#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Morepath app for Web UI history
"""

from __future__ import absolute_import
__revision__ = "$Id$"

from cs.platform.web import PlatformApp
from cs.platform.web.root import Internal, get_internal


class HistoryApp(PlatformApp):
    pass


@Internal.mount(app=HistoryApp, path='history')
def mount_history_app():
    return HistoryApp()


def get_history_app(request):
    return get_internal(request).child('history')
