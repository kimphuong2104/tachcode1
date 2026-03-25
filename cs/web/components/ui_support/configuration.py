#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Object classes to access the operation related konfiguration for the Web UI
"""

from __future__ import absolute_import
__revision__ = "$Id$"

from cdb import sqlapi
from cdb.objects import Forward, Reference_1
from cdb.objects.core import Object
from cdb.platform.mom import entities
from cdb.platform.mom.operations import OperationConfig, OperationInfo

fWebUIDialogHookFunction = Forward(__name__ + ".WebUIDialogHookFunction")
fWebUIDialogHook = Forward(__name__ + ".WebUIDialogHook")


class WebUIDialogHookFunction(Object):
    __maps_to__ = "csweb_dialog_hook_func"
    __classname__ = "csweb_dialog_hook_func"

    config_cache = {}

    @classmethod
    def get_config(cls, hook_name):
        """
        Returns the `WebUIDialogHookFunction` object. The function uses a
        cache, so you have to use `ByKeys` if you want the actual values.
        """
        try:
            result = cls.config_cache[hook_name]
        except KeyError:
            result = cls.ByKeys(hook_name)
            cls.config_cache[hook_name] = result
        return result


class WebUIDialogHook(Object):
    __maps_to__ = "csweb_dialog_hook"
    __classname__ = "csweb_dialog_hook"

    config_cache = {}

    HookFunction = Reference_1(fWebUIDialogHookFunction, fWebUIDialogHook.hook_name)

    @classmethod
    def _get_active_hooks_for_dialog(cls, dialog_name):
        try:
            result = cls.config_cache[dialog_name]
        except KeyError:
            result = cls.KeywordQuery(dialog_name=dialog_name, active=1,
                                      order_by="position").Execute()
            cls.config_cache[dialog_name] = result
        return result

    @classmethod
    def get_active_hooks(cls, dialog_names):
        """ Returns a list of active dialog hooks for a list of mask names. If
            there is more than one mask, all the masks are contained in a mask
            composition.
            The returned list is sorted by the position attribute across all
            masks (ie. all postion=10 hooks will occur before any position=20
            hook). The configuration is cached.
        """
        result = []
        for dlg_name in dialog_names:
            result.extend(cls._get_active_hooks_for_dialog(dlg_name))
        # sorted() provides a stable sort, so for the same position the order
        # is determined by the order of the dialog_names
        return sorted(result, key=lambda hook: hook.position)

    def set_next_position(self, ctx):
        """
        Calculates the maximum position of all hooks configured for the dialog.
        Adds ```10`` and sets the value.
        """
        t = sqlapi.SQL("SELECT max(position) FROM csweb_dialog_hook WHERE "
                       "dialog_name = '%s'" % sqlapi.quote(self.dialog_name))
        pos = 10
        if t and sqlapi.SQLrows(t) == 1:
            pos = sqlapi.SQLinteger(t, 0, 0) + 10
        ctx.set("position", pos)

    event_map = {(("create", "copy"), "pre_mask"): "set_next_position"}
