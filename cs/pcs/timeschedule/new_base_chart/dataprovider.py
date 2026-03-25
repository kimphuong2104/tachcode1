#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

__revision__ = "$Id$"

import collections

from cdb import elink


class DataProviderBase(elink.VirtualPathTemplate):

    __text__ = "${result}"

    def __init__(self, router):
        super().__init__()
        self.router = router

    def _render(self, req):
        self.content_type("application/json")
        super()._render(req)

    def render(self, _context, **_kwargs):
        vpath = self.get_path_segments(cleanup=True)
        # leave exceptions to propagate to HTTP 500 error code
        result = self.router.handle_request(self, vpath)
        return {"result": result}

    def make_link(self, path=None):
        if path is None:
            path = []
        elif isinstance(path, str):
            path = path.split("/")
        paths = list(map(str, path + [""]))
        return "%sapi/%s" % (self.application.getURLPaths()["approot"], "/".join(paths))

    def get_form_data(self, keyname, default=None):
        form_data = getattr(self.request, "form_data", {}).copy()
        result = form_data.get(keyname, default)
        if isinstance(result, (str, str)):
            result = self._convert_to_unicode(result)
        elif isinstance(result, collections.Iterable):
            result = [self._convert_to_unicode(url) for url in result]
        return result

    def _convert_to_unicode(self, bs):
        # Ensure that the text parameters are converted to unicode objects.
        if isinstance(bs, str):
            charset = getattr(self.request, "charset", None)
            if not charset:
                charset = elink.ELINK_ENCODING
            return bs.decode(charset)
        else:
            return bs
