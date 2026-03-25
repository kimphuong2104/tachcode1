#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2010 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# Author:   wme

"""
Module bomconfig

Reading configuration information for the bomcreator module.
"""

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import re
import logging

from cs.vp.bom import AssemblyComponent
from cs.vp.bomcreator.bom import localizedWithFallback
from cdb.objects import Object, Reference, Forward, N, ClassNameBrowser
from cdb.tools import getObjectByName
from cdb.platform import gui
from cdb import sqlapi, auth, util, misc
from cdb.objects.cdb_filetype import CDB_FileType


fBOMConfig = Forward("cs.vp.bomcreator.bomconfig.BOMConfig")
fBOMColumn = Forward("cs.vp.bomcreator.bomconfig.BOMColumn")
fBOMKeyAttribute = Forward("cs.vp.bomcreator.bomconfig.BOMKeyAttribute")
fBOMSyncAttribute = Forward("cs.vp.bomcreator.bomconfig.BOMSyncAttribute")
fBOMMapping = Forward("cs.vp.bomcreator.bomconfig.BOMMapping")


class BOMMethod(Object):
    __maps_to__ = "bom_method"
    __classname__ = "bom_method"


class BOMConfigToRole(Object):
    __maps_to__ = "bom_config_to_role"
    __classname__ = "bom_config_to_role"


class BOMKeyAttribute(Object):
    __maps_to__ = "bom_key_attribute"
    __classname__ = "bom_key_attribute"


class BOMSyncAttribute(Object):
    __maps_to__ = "bom_sync_attribute"
    __classname__ = "bom_sync_attribute"


class BOMMapping(Object):
    __maps_to__ = "bom_mapping"
    __classname__ = "bom_mapping"


class BOMColumn(Object):
    __maps_to__ = "bom_column"
    __classname__ = "bom_column"

    event_map = {
        (('create', 'copy', 'modify', 'query'), 'dialogitem_change'):
        "dialog_item_change",
        (('create', 'copy'), 'pre_mask'): 'preset_position',
        (('create', 'modify', 'copy'), 'pre_mask'): 'before_mask_editable'
        }

    Label = Reference(1, gui.Label, fBOMColumn.label)

    def set_browse(self, ctx):
        ctx.set("attr5", "-- browse --")

    def dialog_item_change(self, ctx):
        # handle attribute browser
        if ctx.changed_item == 'attr5' and ctx.dialog.attr5 != "-- browse --":
            attrs = ["attr1", "attr2", "attr3", "attr4", "attr5"]
            values = [ctx.dialog[attr] for attr in attrs]
            values = [v for v in values if v]
            self.attribute = ".".join(values)
            for attr in attrs:
                ctx.set(attr, "")
            self.set_browse(ctx)
            self.update_is_editable_enabled(ctx)

    def before_mask_editable(self, ctx):
        self.update_is_editable_enabled(ctx)
        self.scan_class_properties(ctx)

    def scan_class_properties(self, _ctx):
        # to select attributes, this class uses a browser
        # based on the same relations as the one to create terms in
        # object rules
        ClassNameBrowser.Scan(scan_props=True)

    @staticmethod
    def is_allowed_editable_attribute(attr_name):
        ret = False
        try:
            field = AssemblyComponent.GetFieldByName(attr_name)
            if field is not None and field.type == sqlapi.SQL_CHAR:
                is_key_attr = attr_name in AssemblyComponent.KeyNames()
                is_cadsource = attr_name == "cadsource"
                ret = not is_key_attr and not is_cadsource
        except AttributeError:
            pass  # attribute does not exist; keep readonly
        return ret

    def update_is_editable_enabled(self, ctx):
        enabled = False
        if self.attribute:
            enabled = self.is_allowed_editable_attribute(self.attribute)
        if enabled:
            ctx.set_fields_writeable(["is_editable"])
        else:
            ctx.set_fields_readonly(["is_editable"])
            ctx.set("is_editable", 0)

    def preset_position(self, _ctx):
        # handle automatically increasing position
        self.position = self._next_position()

    def _next_position(self):
        rset = sqlapi.RecordSet2(sql="SELECT MAX(position) AS maxpos "
                                     "FROM %s WHERE configuration = '%s'"
                                     % (self.__maps_to__,
                                        sqlapi.quote(self.configuration)))
        maxpos = rset[0].maxpos
        if maxpos is not None:
            return maxpos + 10
        else:
            return 10


def find_first_by(seq, pred):
    """Find the first element in a sequence that fulfills
    the given predicate."""
    for e in seq:
        if pred(e):
            return e
    return None


class BOMConfig(Object):
    __maps_to__ = "bom_config"
    __classname__ = "bom_config"

    Method = Reference(1, BOMMethod, fBOMConfig.method_name)
    Columns = Reference(N, BOMColumn,
                        fBOMColumn.configuration == fBOMConfig.cdb_object_id)
    KeyAttributes = Reference(N, BOMKeyAttribute,
                              fBOMKeyAttribute.configuration
                              == fBOMConfig.cdb_object_id)
    SyncAttributes = Reference(N, BOMSyncAttribute,
                               fBOMSyncAttribute.configuration
                               == fBOMConfig.cdb_object_id)
    Mappings = Reference(N, BOMMapping,
                         fBOMMapping.configuration == fBOMConfig.cdb_object_id)

    event_map = {(('create', 'copy'), 'pre_mask'): 'disable_priority',
                 (('create', 'copy'), 'post_mask'): 'preset_priority'}

    def __init__(self):
        Object.__init__(self)
        self.isolang = misc.getConfigValue("CADDOK_ISOLANG")

    def disable_priority(self, ctx):
        # disable priority because we calculate if afterwards
        # when we know the cad_system
        self.priority = 0
        ctx.set_fields_readonly(['priority'])

    def preset_priority(self, ctx):
        # handle automatically increasing position
        ctx.set_fields_writeable(['priority'])
        # handle automatically increasing priority
        self.priority = self._next_priority()

    def _next_priority(self):
        rset = sqlapi.RecordSet2(sql="SELECT MAX(priority) AS maxpriority "
                                 "FROM %s WHERE cad_system = '%s'"
                                 % (self.__maps_to__,
                                    sqlapi.quote(self.cad_system)))
        maxpriority = rset[0].maxpriority
        if maxpriority is not None:
            return maxpriority + 10
        else:
            return 10

    def _roles(self):
        """Roles associated with this configuration."""
        c2rs = BOMConfigToRole.KeywordQuery(bom_config=self.cdb_object_id)
        return [c2r.role_id for c2r in c2rs]

    def is_usable_by_current_user(self):
        """Whether the current user has one of the supported roles."""
        config_roles = self._roles()
        user_roles = util.get_roles("GlobalContext", "", auth.persno)
        for r in user_roles:
            if r in config_roles:
                return True
        return False

    def is_applicable_to(self, object_id):
        """Whether this configuration can be applied
        to the given business object.
        Delegates to the BOM method implementation."""
        reader_type = self.get_reader_type()
        if reader_type is None:
            # There is a misconfiguration. We do not try to hide it.
            return True
        try:
            applicable_check = reader_type.is_applicable_to
        except AttributeError:  # i.e. does not have is_applicable_to
            return True
        return applicable_check(object_id)

    def get_reader_type(self):
        class_name = self.Method.class_name
        if class_name is None:
            return None
        try:
            reader_class = getObjectByName(class_name)
            return reader_class
        except ImportError:
            logging.error("bomconfig: cannot find BOM class: %s", class_name)
            return None

    def _sorted_columns(self):
        return sorted(self.Columns, key=lambda c: c.position)

    def get_column_attributes(self):
        attrs = [c.attribute for c in self._sorted_columns()]
        attrs = [re.sub(r"\$\(CADDOK_ISOLANG\)", self.isolang, a)
                 for a in attrs]
        return attrs

    def get_column_headers(self):
        return [(localizedWithFallback(c.Label.Text, allowEmpty=False), c.is_editable)
                for c in self._sorted_columns()]

    def get_key_attributes(self):
        return [k.attribute_name for k in self.KeyAttributes]

    def get_sync_attributes(self):
        return [s.attribute_name for s in self.SyncAttributes]

    def get_mappings(self):
        return [(m.cdb_attribute_name, m.appinfo_name, m.is_property)
                for m in self.Mappings]

    def get_cadsource_to_replace(self):
        """
        E.g. "manuell" if manual positions should be replaced with
        generated positions if the key attributes match.

        May return an empty string or NULL. In this case, nothing is replaced.
        """
        return self.cadsource

    @staticmethod
    def find_config(cadsource, object_id, only_applicables=True):
        """Loads the correct configuration for the given CAD system,
        the object identified by object_id and the current user.
        If no configuration is found for the CAD system,
        it tries to find one for the part before ':'.
        If this does not work either, is tries 'default_cad'.
        For some users, the result may still be None!
        """
        # try to load config for exact cad source
        config = BOMConfig._select_config(cadsource,
                                          object_id,
                                          only_applicables)
        # otherwise, try to load config for general cad source
        if config is None:
            split_source = cadsource.split(":")
            if len(split_source) > 1:
                config = BOMConfig._select_config(split_source[0],
                                                  object_id,
                                                  only_applicables)
        # otherwise, load default config
        if config is None:
            config = BOMConfig._select_config('default_cad', object_id,
                                              only_applicables)
        return config

    @staticmethod
    def _select_config(cadsource, object_id, only_applicables):
        """Tries to find a configuration that matches the roles
        of the current user and the given cadsource. Also considers priorities.
        Returns None if no such config is found.
        """
        config_candidates = BOMConfig.KeywordQuery(cad_system=cadsource)
        candidates_for_user = [c for c in config_candidates
                               if c.is_usable_by_current_user()]
        if not candidates_for_user:
            return None

        candidates_for_user.sort(key=lambda c: c.priority, reverse=True)
        if only_applicables:
            match = find_first_by(candidates_for_user,
                                  lambda c: c.is_applicable_to(object_id))
            return match
        else:
            if candidates_for_user:
                return candidates_for_user[0]
            else:
                return None


class CadSourceCatalog(gui.CDBCatalog):
    def handlesSimpleCatalog(self):
        return True

    def getCatalogEntries(self):
        cad_sources = set()
        for fileType in CDB_FileType.Query():
            cad_source = fileType.ft_name.split(":")[0]
            cad_sources.add(cad_source)
        cad_sources_list = list(sorted(cad_sources))
        cad_sources_list.insert(0, "manuell")  # constant used in all languages
        return cad_sources_list
