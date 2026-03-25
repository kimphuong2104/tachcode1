#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#

from __future__ import absolute_import

from cdb import rte
from cdb import ue, ElementsError
from cdb.classbody import classbody
from cdb.objects.cdb_file import CDB_File
from cdb.objects import NULL
from cdb.objects.cdb_filetype import CDB_FileType
from cdb.sig import connect
from cdb import util
from cdb import auth
from cdb import sqlapi
from cdb.util import DBInserter

from cs.documents import Document  # needed for classbody extension
from cs.vp.cad import CADVariant  # needed for classbody extension
from cs.workspaces import open_with_cdbwscall

from .cadfiletypes import collect_cad_file_types
from .wseditview import register_edit_and_view


ROLE_ADMINISTRATOR_WSM = u"Administrator: WSM"


# Immediately unlock cdb_belongsto files after lock
@connect(CDB_File, "CDB_Lock", "post")
def _unlockBelongstoFiles(self, _ctx):
    if self.cdb_belongsto:
        pObj = self.getPersistentObject()
        pObj.Update(cdb_lock="", cdb_lock_date=NULL, cdb_lock_id=NULL)


def is_primary_of_automatic_cad(f):
    """
    Check if this file is a primary file of an automatically managed CAD document.
    :param f: User exit input
    :return: bool
    """
    res = False
    if not f.cdbf_derived_from and not f.cdb_belongsto:
        parent = f.ParentObject
        if parent and isinstance(parent, Document):
            if parent.wsm_is_cad == "1":
                res = True
    return res


@connect(CDB_File, "create", "pre")
def pre_create_file(f, ctx):
    if ctx.interactive:
        if is_primary_of_automatic_cad(f):
            # disallow creating CAD files (because this should happen in Workspaces Desktop)
            ft = CDB_FileType.ByKeys(f.cdbf_type)
            if ft is not None and ft.ft_genonlycad:
                # except for the admin
                user_roles = util.get_roles("GlobalContext", "", auth.persno)
                if ROLE_ADMINISTRATOR_WSM not in user_roles:
                    raise ue.Exception("cdb_cad_wsm_document_must_be_edited_in_wsm")


@connect(CDB_File, "create", "post")
@connect(CDB_File, "copy", "post")
def post_create_or_copy_file(f, ctx):
    if ctx.interactive:
        if is_primary_of_automatic_cad(f):
            # set the flag that marks manually assigned files
            dbi = DBInserter("cdb_file_wsm")
            dbi.add("cdbf_object_id", f.cdbf_object_id)
            dbi.add("file_wspitem_id", f.cdb_wspitem_id)
            dbi.add("wsm_manual_assigned", 1)
            dbi.insert()


@connect(CDB_File, "delete", "pre")
def pre_delete_file(f, ctx):
    if ctx.interactive:
        if is_primary_of_automatic_cad(f):
            # allow deletion if manually assigned (or admin)
            is_manually_assigned = False
            file_attrs = sqlapi.RecordSet2(
                "cdb_file_wsm",
                condition="cdbf_object_id = '%s'"
                " AND file_wspitem_id = '%s'"
                % (sqlapi.quote(f.cdbf_object_id), sqlapi.quote(f.cdb_wspitem_id)),
            )
            if file_attrs:
                is_manually_assigned = (
                    file_attrs[0].wsm_manual_assigned == 1
                )  # pylint: disable=no-member
            if not is_manually_assigned:
                user_roles = util.get_roles("GlobalContext", "", auth.persno)
                if ROLE_ADMINISTRATOR_WSM not in user_roles:
                    raise ue.Exception("cdb_cad_wsm_document_must_be_edited_in_wsm")


@connect(CDB_File, "delete", "post")
def post_delete_file(f, ctx):
    if ctx.interactive:
        if is_primary_of_automatic_cad(f):
            # also delete secondary files (appinfo, preview)
            if f.cdb_wspitem_id:
                CDB_File.KeywordQuery(
                    cdbf_object_id=f.cdbf_object_id, cdb_belongsto=f.cdb_wspitem_id
                ).Delete()


_CDBWSCALL_LOAD_AND_OPEN_CAD_DOCUMENT_FILE = u"""<?xml version="1.0"?>
<cdbwsinfo>
   <command>loadandopencaddocument</command>
   <options>
      <pdmadapter>{pdmadapter}</pdmadapter>
      <office_mode>{office_mode_value}</office_mode>
      <requiredversion>3.2.0</requiredversion>
   </options>
   <parameters>
       <parameter>{cdb_object_id}</parameter>
   </parameters>
</cdbwsinfo>
"""


@classbody
class CADVariant(object):
    def open_cad_variant(self, ctx=None):
        doc = Document.ByKeys(z_nummer=self.z_nummer, z_index=self.z_index)
        if doc is not None:
            numPrimaryFiles = len(doc.PrimaryFiles)
            if numPrimaryFiles == 1:
                open_with_cdbwscall(
                    ctx,
                    _CDBWSCALL_LOAD_AND_OPEN_CAD_VARIANT,
                    cdb_object_id=doc.cdb_object_id,
                    variant_id=self.variant_id,
                )
            elif numPrimaryFiles == 0:
                raise ue.Exception("cdb_cad_wsm_no_anchor_file")
            else:
                raise ue.Exception("cdb_cad_wsm_no_unique_anchor_file")

    event_map = {("cdb_cad_wsm_edit_variant", "now"): "open_cad_variant"}


_CDBWSCALL_LOAD_AND_OPEN_CAD_VARIANT = u"""<?xml version="1.0"?>
<cdbwsinfo>
   <command>loadandopencaddocument</command>
   <options>
      <pdmadapter>{pdmadapter}</pdmadapter>
      <requiredversion>3.2.0</requiredversion>
   </options>
   <parameters>
       <parameter>{cdb_object_id}</parameter>
       <parameter>{variant_id}</parameter>
   </parameters>
</cdbwsinfo>
"""

connect(rte.USER_IMPERSONATED_HOOK)(register_edit_and_view)
connect(rte.USER_IMPERSONATED_HOOK)(collect_cad_file_types)
