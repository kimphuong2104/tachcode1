#!/usr/bin/env python
# coding: utf-8
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from cdb.lru_cache import lru_cache


def boolify(str_val):
    return bool(int(str_val))


def unboolify(bool_val):
    return 1 if bool_val else 0


def is_ctx_from_web(ctx):
    try:
        return boolify(ctx.dialog["uses_web_ui"])
    except KeyError:
        return False


@lru_cache(maxsize=100)
def get_base_classname(cl_def):
    return cl_def.getRootClass().getClassname()


def get_form_context_adapter(owner, ctx):
    if is_ctx_from_web(ctx):
        return WebContextAdapter(owner, ctx)
    return ctx


class WebContextAdapter:
    def __init__(self, owner, ctx):
        self._owner = owner
        self._ctx = ctx
        self._passthrough_attributes(["changed_item", "action"])

    def _passthrough_attributes(self, attrs):
        for attr in attrs:
            try:
                val = getattr(self._ctx, attr)
            except AttributeError:
                break
            else:
                setattr(self, attr, val)

    def _prefix_field_name(self, name):
        return get_base_classname(self._owner.GetClassDef()) + "." + name

    # TODO [bgu 07-12-2018]:  we can generate these methods automatically
    def set_optional(self, field):
        self._ctx.set_optional(self._prefix_field_name(field))

    def set_mandatory(self, field):
        self._ctx.set_mandatory(self._prefix_field_name(field))

    def set_readonly(self, field):
        self._ctx.set_readonly(self._prefix_field_name(field))

    def set_writeable(self, field):
        self._ctx.set_writeable(self._prefix_field_name(field))

    def set(self, field, value):
        self._ctx.set(self._prefix_field_name(field), value)
