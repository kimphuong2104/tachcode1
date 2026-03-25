#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id$"

from cdb import ddl
from cdb import sqlapi
from cdb import util
from cdb.comparch import protocol
from cs.web.components.favorites.model import Favorite


class DropOldHistoryEntries(object):
    """ History entries for the Web UI are now stored in a different way. Drop
        all old entries, so that the DB relation can be changed.
    """
    def run(self):
        if ddl.Table('cdbweb_history_item').exists():
            sqlapi.SQLdelete("FROM cdbweb_history_item")


class ChangeHistoryTable(object):
    """ Drop attributes that are no longer used, and set new PK
    """
    def run(self):
        t = ddl.Table('cdbweb_history_item')
        if t.exists():
            t.setPrimaryKey(ddl.PrimaryKey('cdb_cpersno',
                                           'rest_name',
                                           'rest_id'))
            colnames = [cn for cn in ('cdb_object_id', 'classname',
                                      'frontend_url', 'icon_url', 'title')
                        if t.hasColumn(cn)]
            if colnames:
                t.dropAttributes(*colnames)


class AddNewSettings(object):
    """
    Adds the settings for the history entries
    """
    def run(self):
        from cdb.comparch import modules
        from cdb.comparch import content
        m = modules.Module.ByKeys('cs.web.components')
        content_filter = content.ModuleContentFilter(["cdb_setting"])
        mc = modules.ModuleContent(m.module_id, m.std_conf_exp_dir, content_filter)
        for mod_content in mc.getItems("cdb_setting").values():
            if mod_content.getAttr("setting_id") in ["csweb.history_objs_per_class",
                                                     "csweb.max_history_objs"]:
                try:
                    mod_content.insertIntoDB()
                except:
                    # Already there
                    pass


class UpdateFavorites(object):
    """ Update favorites with rest_name and rest_id
    """
    def run(self):
        for fav in Favorite.Query():
            if not fav.rest_name and fav.frontend_url:
                parts = fav.frontend_url.split('/')
                if len(parts) == 4 and parts[1] == 'info':
                    fav.Update(rest_name=parts[2], rest_id=parts[3])


class ChangeDialogHookConfig(object):
    """
    Some information has to be moved from ``csweb_dialog_hook``
    to ``csweb_dialog_hook_func``.
    """
    def run(self):
        hook = ddl.Table('csweb_dialog_hook')
        if hook.exists() and hook.hasColumn("function_name"):
            # Check which functions are already there
            funcs = sqlapi.SQLselect("hook_name, function_name FROM csweb_dialog_hook_func")
            fd = {}
            for row in range(0, sqlapi.SQLrows(funcs)):
                fd[sqlapi.SQLstring(funcs, 0, row)] = sqlapi.SQLstring(funcs, 1, row)
            t = sqlapi.SQLselect("DISTINCT hook_name, function_name, cdb_module_id"
                                 " FROM csweb_dialog_hook WHERE function_name"
                                 " IS NOT NULL AND function_name != ''")
            for row in range(0, sqlapi.SQLrows(t)):
                hook_name = sqlapi.SQLstring(t, 0, row)
                func_name = sqlapi.SQLstring(t, 1, row)
                if hook_name not in fd:
                    i = util.DBInserter("csweb_dialog_hook_func")
                    i.add("hook_name", hook_name)
                    i.add("function_name", func_name)
                    i.add("cdb_module_id", sqlapi.SQLstring(t, 2, row))
                    # No backend support in the past
                    i.add("backend", 0)
                    i.insert()
                    fd[hook_name] = func_name
                elif func_name != fd[hook_name]:
                    protocol.logWarning("Found different functions for hook '%s'" % hook_name)


pre = [DropOldHistoryEntries]
post = [ChangeHistoryTable,
        AddNewSettings,
        UpdateFavorites,
        ChangeDialogHookConfig]
