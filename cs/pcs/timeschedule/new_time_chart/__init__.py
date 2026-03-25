#!/usr/bin/env python
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__revision__ = "$Id$"

from cdb import elink


@elink.using_template_engine("chameleon")
class App(elink.Application):
    def setup(self):
        from cs.pcs.timeschedule.new_base_chart.dataprovider import DataProviderBase
        from cs.pcs.timeschedule.new_time_chart import pages

        self.add("index", pages.MyPage())
        self.add("time_api", DataProviderBase(pages.router))


# lazy instantiation
_APP = None


def _getapp():
    global _APP
    if _APP is None:
        _APP = App("App")
    return _APP


def handle_request(req):
    """Shortcut to the app"""
    req.add_extra_header(
        "CONTENT-SECURITY-POLICY",
        "default-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        + "img-src 'self' data: blob:; font-src 'self' data:",
    )
    return _getapp().handle_request(req)
