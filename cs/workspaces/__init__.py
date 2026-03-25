#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import base64
import json
import os
import io
import logging

from cdb import CADDOK, sqlapi
from cdb import auth
from cdb import util
from cdb import constants
from cdb import sig

from cdb.objects import Object, Reference_N, Forward
from cdb.objects.cdb_file import CDB_File, _UnknownFileType
from cdb.platform import mom
from cs.documents import Document

from cs.workspaces.sqlutils import partionedSqlQuery


_CDBWSCALL_FILE = u"""<?xml version="1.0"?>
<cdbwsinfo>
   <command>loadworkspacebyid</command>
   <parameters>
     <parameter>{cdb_object_id}</parameter>
   </parameters>
</cdbwsinfo>
"""


fWsDocuments = Forward(__name__ + ".WsDocuments")
fWorkspace = Forward(__name__ + ".Workspace")
f_cdb_file_base = Forward("cdb.objects.cdb_file.cdb_file_base")


class WsDocuments(Object):
    __classname__ = "ws_documents"
    __maps_to__ = "ws_documents"

    WorkspaceItems = Reference_N(
        f_cdb_file_base, f_cdb_file_base.cdbf_object_id == fWsDocuments.cdb_object_id
    )

    Files = Reference_N(CDB_File, CDB_File.cdbf_object_id == fWsDocuments.cdb_object_id)

    PrimaryFiles = Reference_N(
        CDB_File,
        CDB_File.cdbf_object_id == fWsDocuments.cdb_object_id,
        CDB_File.cdbf_primary == "1",
    )

    # use a list, because otherwise the function
    # will be attached to the attribute and
    # needs a the "WsDocuments" parameter as
    # first argument, which is nonsense
    generate_name_for_document_impl = [None]

    def getJsonObjectAttrs(self):
        """
        Retrieve the attributes and convert these from string to json.

        :return: The JSON attributes as dictionary.
        :rtype: dict
        """
        jsonObjAttrs = {}
        if self.json_object_attrs:
            jsonObjAttrs = json.loads(self.json_object_attrs)
        return jsonObjAttrs

    @classmethod
    def set_generate_name_function(cls, func):
        cls.generate_name_for_document_impl = [func]

    @classmethod
    def get_generate_name_function(cls):
        return cls.generate_name_for_document_impl[0]

    @classmethod
    def generate_name_for_document(
        cls, wsdocumentfile, dst_doc_cdb_object_id, original_name=""
    ):
        if cls.generate_name_for_document_impl is not None:
            func = cls.get_generate_name_function()
            return func(wsdocumentfile, dst_doc_cdb_object_id, original_name)
        raise Exception("WsDocuments.generate_name_for_document_impl is not defined.")


def generate_name_for_document(wsdocumentfile, dst_doc_cdb_object_id, original_name=""):
    """
    Returns a filename for `wsdocumentfile`.

    The parent object is identified by the `dst_doc_cdb_object_id`.

    Further description can be found in
    `cdb.objects.cdb_file.cdb_file_record.generate_name`.
    """
    result = ""
    oh = None
    if dst_doc_cdb_object_id:
        oh = mom.getObjectHandleFromObjectID(dst_doc_cdb_object_id)

    if oh and oh.is_valid() and wsdocumentfile.cdbf_type:
        preferred_suffix = None
        if original_name:
            (base_name, preferred_suffix) = os.path.splitext(original_name)
        else:
            base_name = getattr(wsdocumentfile, "cdbf_original_name")

        if wsdocumentfile.cdbf_type != _UnknownFileType or preferred_suffix is None:
            result = oh.getStandardFilenameByFileTypeName(
                wsdocumentfile.cdbf_type, preferred_suffix, base_name
            )
        else:
            result = oh.getStandardFilenameBySuffix(preferred_suffix, base_name)

    if not result:
        result = original_name.replace("\\", "/").split("/")[-1]

    return wsdocumentfile.make_filename_unique(result)


WsDocuments.set_generate_name_function(generate_name_for_document)


class Workspace(Document):
    __classname__ = "cdb_wsp"
    __match__ = Document.cdb_classname >= __classname__

    WsDocuments = Reference_N(
        fWsDocuments, fWsDocuments.ws_object_id == fWorkspace.cdb_object_id
    )

    def on_delete_pre(self, ctx):
        """Ask if Workspace should be deleted, if Teamspace content exists."""
        if (
            "question_workspace_has_teamspace_content"
            in ctx.dialog.get_attribute_names()
            or "question_workspace_has_teamspace_content"
            in ctx.sys_args.get_attribute_names()
        ):
            return

        if self.WsDocuments:
            lockerNames = []
            lockerAliasNames = []
            wsIdent = "%s (%s)" % (self.titel, self.z_nummer)

            # collect locker names
            wsDocIds = [wsDoc.cdb_object_id for wsDoc in self.WsDocuments]
            rawQuery = """
                SELECT cdb_lock
                FROM cdb_file
                WHERE %s
                GROUP BY cdb_lock
            """
            records = partionedSqlQuery(
                rawQuery, "cdbf_object_id", wsDocIds, withAnd=False, withFormat=True
            )
            for r in records:
                if r.cdb_lock:
                    lockerNames.append(r.cdb_lock)
            if lockerNames:
                rawQuery = """
                    SELECT name
                    FROM angestellter
                    WHERE %s
                    GROUP BY name
                    ORDER BY name
                """
                records = partionedSqlQuery(
                    rawQuery,
                    "personalnummer",
                    lockerNames,
                    withAnd=False,
                    withFormat=True,
                )
                for r in records:
                    if r.name:
                        lockerAliasNames.append(r.name)
            else:
                lockerAliasNames = ["-"]
            lockerAliasNamesStr = ", ".join(lockerAliasNames)
            # show message box
            mb = ctx.MessageBox(
                "cdb_cad_wsm_workspace_has_teamspace_content",
                [wsIdent, lockerAliasNamesStr],
                "question_workspace_has_teamspace_content",
                ctx.MessageBox.kMsgBoxIconAlert,
            )
            mb.addYesButton()
            mb.addCancelButton(1)
            ctx.show_message(mb)

    def on_delete_post(self, _ctx):
        """Delete Teamspace contents when workspace was deleted."""
        # pylint: disable=unused-variable
        for wsDoc in self.WsDocuments:
            sqlapi.SQLdelete(
                "FROM cdb_file WHERE cdbf_object_id = '%s'"
                % sqlapi.quote(wsDoc.cdb_object_id)
            )
            try:
                # use import to check if module cs.wsm is available
                from cs.wsm.cdbfilewsm import Cdb_file_wsm  # noqa: F401

                # only then, delete entries from relations in cs.wsm
                sqlapi.SQLdelete(
                    "FROM cdb_file_wsm WHERE cdbf_object_id = '%s'"
                    % sqlapi.quote(wsDoc.cdb_object_id)
                )
                sqlapi.SQLdelete(
                    "FROM cdb_file_links_status WHERE cdbf_object_id = '%s'"
                    % sqlapi.quote(wsDoc.cdb_object_id)
                )
            except ImportError:
                pass
            wsDoc.Delete()

    def stateChangeAllowed(self, _target_state, _batch):
        return True

    @classmethod
    def disable_activity_stream_reg(cls, ctx):
        ctx.disable_registers(["cdb_elink_activitystream"])

    @classmethod
    def create_workspace_number(cls):
        return "W%06d" % (util.nextval("WS_NR_SEQ"))

    def setDocumentNumber(self, _ctx):
        if not self.teilenummer:
            self.z_nummer = self.create_workspace_number()
        else:
            self.z_nummer = self.makeNumber(self)

    def open_file(self, ctx=None):
        open_with_cdbwscall(ctx, _CDBWSCALL_FILE, cdb_object_id=self.cdb_object_id)

    event_map = {
        ("cdb_wsp_edit", "now"): "open_file",
        (("query", "requery"), "pre_mask"): "disable_activity_stream_reg",
    }


def open_with_cdbwscall(ctx, template, **args):
    """
    Call cdbwscall.exe (Workspaces Desktop component) on the client.
    :param ctx: User Exit context (might be None in tests)
    :param template: XML str representing the parameters for cdbwscall
    :param args: to substitute in template
    """
    if ctx is not None:
        if ctx.uses_webui:
            xml = template.format(pdmadapter="CEWeb", **args)
            params = base64.urlsafe_b64encode(xml.encode("utf-8")).decode("utf-8")
            ctx.url("cdbwscall:%s" % params)
        else:
            xml = template.format(pdmadapter="CE", **args)
            filename = os.path.join(CADDOK.TMPDIR, "command_%s.cdbwscall" % auth.persno)
            f = io.open(filename, "w", encoding="utf-8")
            f.write(xml)
            f.close()
            ctx.file(filename, delete_file_after_view=True, view_extern=True)


@sig.connect(Workspace, "copy", "pre")
def set_active_integration(_ws, ctx):
    if not ctx.active_integration:
        # set integration to copy CAD files (ft_genonlycad=1)
        integration = "cs.workspaces"
        logging.debug("Copy Workspace: setting active integration '%s'", integration)
        ctx.set(constants.kArgumentActiveIntegration, integration)
        ctx.set(constants.kArgumentActiveCAD, integration)
