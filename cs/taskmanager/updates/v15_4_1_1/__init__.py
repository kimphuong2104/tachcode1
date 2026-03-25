#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=broad-except

from cdb.comparch import content, modules, protocol


def revert_deleted_patch(module_id, table, **kwargs):
    m = modules.Module.ByKeys(module_id)
    content_filter = content.ModuleContentFilter([table])
    mc = modules.ModuleContent(m.module_id, m.std_conf_exp_dir, content_filter)

    for mod_content in mc.getItems(table).values():
        mod_keys = {key: mod_content.getAttr(key) for key in list(kwargs)}
        if mod_keys == kwargs:
            try:
                # Effectively revert patch
                mod_content.insertIntoDB()
            except Exception as e:
                protocol.logError(
                    "could not revert DELETED patch "
                    "(module {}, table {}, keys {})".format(module_id, table, kwargs),
                    details_longtext="{}".format(e),
                )


class EnsureDefaultSettingsExist(object):
    """
    Revert eventual DELETED-Patch for default settings for public.
    """

    def run(self):
        revert_deleted_patch(
            "cs.taskmanager",
            "cs_tasks_user_view",
            cdb_object_id="4fb33321-9570-11e8-ba1d-68f7284ff046",
        )


pre = []
post = [EnsureDefaultSettingsExist]
