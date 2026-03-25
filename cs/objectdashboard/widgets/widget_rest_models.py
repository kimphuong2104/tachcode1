# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
cs.objectdashboard.widgets.widget_rest_models
=============================================

Model classes for the widget REST application of ``cs.objectdashboard``.

"""

from cs.platform.web import JsonAPI
from cs.platform.web.root import Internal, get_internal


class InternalWidgetApp(JsonAPI):
    PATH = "cs-objdashboard-widgets"

    @classmethod
    def get_app(cls, request):
        return get_internal(request).child(cls.PATH)


@Internal.mount(app=InternalWidgetApp, path=InternalWidgetApp.PATH)
def _():
    return InternalWidgetApp()
