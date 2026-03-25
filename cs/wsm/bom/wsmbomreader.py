#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import

from cdb.objects import ByID
from cdb.storage.exceptions import UnknownObjectError

from cs.vp.bomcreator import msg
from cs.vp.bomcreator.bomreader import BOMReader

from cs.wsm.srvappinfoparser import NoAppinfoContentError
from cs.wsm.virtualworkspace import VirtualWorkspace


class WSMBOMReader(BOMReader):
    """
    Common super class of BOMReaders that use Workspaces
    application information (appinfo) in any form.

    self.anchor_file: virtualworkspace.FileRecord or None
              the first main/anchor file of the business object

    self.workspace: virtualworkspace.VirtualWorkspace
              the virtual workspace that `anchor_file` belongs to;
              does not contain the reference structure by default
              (but implementations may call `refreshFromDatabase` on it)
    """

    def __init__(self, bom_context, factory, _custom_state):
        object_id = bom_context.object_id
        doc = ByID(object_id)
        self.workspace = factory.createVirtualWorkspace(
            doc, followReferences=False, caseSensitive=False
        )
        self.anchor_file = None

        anchor_items = self.workspace.getPrimaryFilesForBo(object_id)
        if not anchor_items:
            bom_context.global_user_hints.append_error(
                msg("WSM_BOM_no_anchor_files") % getattr(doc, "titel", object_id)
            )
        else:
            self.anchor_file = anchor_items[0]

        if len(anchor_items) > 1:
            bom_context.global_user_hints.append(
                msg("WSM_BOM_further_anchor_files_ignored")
                % getattr(doc, "titel", object_id)
            )

    def refresh_workspace_with_references(self, virtual_workspace, user_hints):
        wserrors = virtual_workspace.refreshFromDatabase(
            followReferences=True, followRefsRecursively=False, ignoreExtRefs=True
        )
        errors = []
        for (errorcode, description) in wserrors:
            if errorcode == VirtualWorkspace.LINKED_ITEM_NOT_FOUND:
                errors.append(msg("WSM_BOM_linked_item_missing") % description)
        if len(errors) > 0:
            m = msg("WSM_BOM_loading_workspace_errors")
            errs = ", ".join(errors)
            hint = m + " [" + errs + "]"
            user_hints.append(hint)


def filename_of_record(file_record):
    return file_record.attrs.get("cdbf_name")


def get_appinfo_tree(file_record, workspace, user_hints):
    """
    Helper function to access the Appinfo tree of an anchor file.
    """
    try:
        app_info_rec = workspace.getAppinfoRecord(file_record)
        if app_info_rec is None:
            user_hints.append_error(
                msg("WSM_BOM_appinfo_missing") % filename_of_record(file_record)
            )
            return None

        appinfo_tree = workspace.getAppinfoTree(app_info_rec, raiseOnEmpty=True)
        if appinfo_tree is None:
            user_hints.append_error(
                msg("WSM_BOM_appinfo_invalid") % filename_of_record(file_record)
            )
            return None

        if appinfo_tree.isIncomplete(u"structureOnly") or appinfo_tree.isIncomplete(
            u"noStructure"
        ):
            user_hints.append_error(
                msg("WSM_BOM_appinfo_incomplete") % filename_of_record(file_record)
            )
            return None

        return appinfo_tree

    except NoAppinfoContentError:
        # ignore silently
        return None

    except UnknownObjectError:
        user_hints.append_error(
            msg("WSM_BOM_replication_error") % filename_of_record(file_record)
        )
        return None
