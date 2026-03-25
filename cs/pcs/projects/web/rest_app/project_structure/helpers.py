#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging

from webob.exc import HTTPBadRequest


def _check(json, key, expected_type, mandatory=True):
    value = json.get(key)
    if mandatory and value is None:
        logging.error("missing value for key: %s", key)
        raise HTTPBadRequest
    if value is not None and not isinstance(value, expected_type):
        logging.error("malformed '%s': %s", key, value)
        raise HTTPBadRequest
    return value


def parse_persist_drop_payload(json):
    target = _check(json, "targetId", str)
    parent = _check(json, "parentId", str)

    children = _check(json, "children", list, False)
    predecessor = _check(json, "predecessor", str, False)

    drop_effect = _check(json, "dropEffect", str)

    if drop_effect not in set(["move", "copy"]):
        logging.error("dropEffect may only be 'move' or 'copy', is '%s'", drop_effect)
        raise HTTPBadRequest

    is_move = drop_effect == "move"
    return target, parent, children, predecessor, is_move


def parse_revert_drop_payload(json):
    copy_id = _check(json, "copy_id", str)
    return copy_id
