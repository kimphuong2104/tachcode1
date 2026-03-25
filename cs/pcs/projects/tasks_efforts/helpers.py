#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


DISCARDED = set([180])


def norm_val(val, default_value):
    if val is None or val == "":
        return default_value
    return val


def find_min(x, y):
    if x is None or x == "":
        return y
    if y is None or y == "":
        return x
    return min(x, y)


def find_max(x, y):
    if x is None or x == "":
        return y
    if y is None or y == "":
        return x
    return max(x, y)


def find_max_all(x, y):
    if x == "start":
        return y
    if x is None or x == "" or y is None or y == "":
        return None
    return max(x, y)


def add(x, y):
    if x is None or x == "":
        return y
    if y is None or y == "":
        return x
    return x + y


def get_object_with_updated_values(object_dict, object_changes):
    object_values = object_dict.copy()
    object_values.update(**object_changes)
    return object_values


def is_discarded(obj_dict):
    return obj_dict["status"] in DISCARDED
