#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import elink


@elink.using_template_engine("chameleon")
class App(elink.Application):
    def setup(self):
        from cs.pcs.resources.new_resource_chart import pages
        from cs.pcs.timeschedule.new_base_chart.dataprovider import DataProviderBase

        self.add("index", pages.MyPage())
        self.add("resource_api", DataProviderBase(pages.router))


# lazy instantiation
_APP = None


def _getapp():
    global _APP  # pylint: disable=W0603
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
