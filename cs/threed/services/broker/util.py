# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module util

This module provides general utility functions for the Broker Service.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import CADDOK

# Exported objects
__all__ = ["default_head_response", "get_last_header", "default_options_response"]


def get_last_header(request, header_name, default):
    header = request.requestHeaders.getRawHeaders(header_name)
    if header:
        return header[-1]
    else:
        return default


def default_head_response(request):
    origin = get_last_header(request, 'origin', '*')
    request.setHeader("content-type", "application/json; charset=utf-8")
    request.setHeader('Access-Control-Allow-Origin', origin)
    request.setHeader('Access-Control-Allow-Credentials', "true")
    return b""


def default_options_response(request, methods=None):
    if methods is None:
        methods = ["GET", "HEAD", "OPTIONS"]
    origin = get_last_header(request, 'origin', '*')
    request.setHeader('Access-Control-Allow-Origin', origin)
    request.setHeader('Access-Control-Allow-Methods', ', '.join(methods))
    request.setHeader('Access-Control-Allow-Credentials', "true")
    request.setHeader("Access-Control-Allow-Headers",
                      "Content-Type, Accept, Cache, X-Csrf-Token, "
                      "Authorization")
    return b""


def read_env_param(name, default=None):
    result = None
    try:
        result = CADDOK.get(name)
    except (TypeError, ValueError):
        result = default
    if default:
        try:
            return type(default)(result)
        except TypeError:
            return default
    else:
        return result


# Guard importing as main module
if __name__ == "__main__":
    pass
