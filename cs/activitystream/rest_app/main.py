# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from __future__ import absolute_import

from cs.platform.web import JsonAPI
from cs.platform.web.root import Internal, get_internal

__APP_NAME__ = "activitystream"


class ActivityStreamApp(JsonAPI):
    def __init__(self):
        self.rest_name = "activitystream"


@Internal.mount(app=ActivityStreamApp, path=__APP_NAME__)
def _mount_app():
    return ActivityStreamApp()


def get_activitystream(request):
    """Try to look up /internal/activitystream"""
    return get_internal(request).child(__APP_NAME__)
