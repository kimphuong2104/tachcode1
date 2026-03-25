#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module cs.workflow.designer.urls

Calculate "external" urls (those outside of the designer's url namespace)
"""

import logging
import urllib.parse
from cs.platform.web.uisupport import get_ui_link
from cs.workflow import misc
from cs.workflow.protocols import Protocol

URL_PATTERN_SAFE_CHARS = '/?='
PROTOCOL_URL_PATTERN = (
    '/info/process_protocol/?search_attrs='
    '{{"cdbwf_protocol.cdb_process_id":"{cdb_process_id}"}}')


def quote(url):
    """
    Replaces url with http-escaped chars. Expects a relative url, e.g. no
    ``protocol://`` prefix, as colons are escaped, too.
    """
    return urllib.parse.quote(url, safe=URL_PATTERN_SAFE_CHARS)


def get_protocol_url(cdb_process_id):
    """
    Returns relative link to protocol entries with given ``cdb_process_id``.
    """
    cmsg = Protocol.MakeCdbcmsg(
        action="CDB_Search",
        interactive=False,
        cdb_process_id=cdb_process_id,
    )
    url = cmsg.cdbwin_url()
    return url


def get_object_url(obj, page=None, action=None):
    """
    cdbpc:
    :returns: Legacy cdb:// url for object's default action
    :rtype: str

    Elements 15.3.12 and newer:
    :returns: Relative link to ``/info/{rest_name}/{rest_key}`` of ``obj``.
    :rtype: str

    Older Elements versions:
    :returns: Absolute link to ``/info/{rest_name}/{rest_key}`` of ``obj``.
        May be derived from ``page``, otherwise requires
        ``CADDOK.WWWSERVICE_URL`` to be set.
    :rtype: str
    """
    if misc.is_csweb():
        try:
            result = get_ui_link(None, obj)
        except Exception:
            raise RuntimeError("Could not generate relative link . Please use Elements 15.3.12 or newer.")
    elif action is not None:
        result = obj.MakeURL(action=action, plain=2)
    else:
        result = obj.MakeURL(plain=2)

    if result is None:
        logging.error(
            "Cannot resolve object URL for %s '%s'. Class or "
            "operation not activated for cs.web?",
            obj.GetClassname(),
            obj.GetDescription(),
        )

    return result
