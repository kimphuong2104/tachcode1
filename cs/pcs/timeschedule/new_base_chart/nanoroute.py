#!/usr/bin/env python
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__revision__ = "$Id$"

import json

from cdb import misc, typeconversion


class App:
    # App responses directly to request(writes the data back)
    def __init__(self):
        self.routes = {}

    def handle_request(self, req, path=None):
        path = tuple(path)
        for route, handler in list(self.routes.items()):
            matched = match_route(route, path)
            if matched is not None:
                return handler(req, **matched)
        misc.log_error("No route for path '%s'" % req.request.env["PATH_INFO"])
        return None

    def register(self, route, handler):
        self.routes[parse_route(route)] = handler

    def register_with_render(self, route, func, render):
        def wrapper(req, **kw):
            result = func(req, **kw)
            result = render(req, result)
            req.write(result)

        self.register(route, wrapper)

    def registration(self, route, render):
        def wrapper(func):
            self.register_with_render(route, func, render)
            return func

        return wrapper

    def resource(self, route):
        return self.registration(route, resource_render)

    def json(self, route):
        return self.registration(route, json_render)


class LookUp(App):
    # LookUp just returns the rendered data and
    # let the caller deal with the data
    def register_with_render(self, route, func, render):
        def wrapper(req, **kw):
            result = func(req, **kw)
            return render(req, result)

        self.register(route, wrapper)


def parse_route(s):
    return tuple(s.split("/"))


def match_route(route, path):
    if len(route) != len(path):
        return None
    result = {}
    for pattern, step in zip(route, path):
        if pattern.startswith(":"):
            result[pattern[1:]] = step
        else:
            if pattern != step:
                return None
    return result


def resource_render(req, data):
    return data


def json_render(req, data):
    req.type = "application"
    req.subtype = "json"
    return json.dumps(
        data,
        indent=2,
        sort_keys=True,
        default=typeconversion.to_legacy_date_format_auto,
    )


def posted_json(req):
    if len(req.upstreams) != 1:
        raise AssertionError(
            "len(req.upstreams) is not 1: {}".format(len(req.upstreams))
        )

    charset = req.charset
    path = req.upstreams[0]["id"].decode(charset)

    if not isinstance(path, str):
        raise AssertionError("path is not unicode: {}".format(type(path)))

    with open(path, "rb") as f:
        return json.load(f)
