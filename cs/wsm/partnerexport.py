#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#

from __future__ import absolute_import

import os
import logging

import six

from cdb import sqlapi
from cdb.classbody import classbody
from cdb.objects import Object
from cdb.objects.org import Organization
from cdb.objects.cdb_file import CDB_File

from cs.documents import Document  # needed for classbody extension

# (these classes were part of this module pre 15.5.1)
from cs.workspaces.partnerfilename import (
    PartnerFilename,
    WSMPartnerCatalogContent,
    WSMPartnerCatalog,
)


class PartnerExport(Object):
    __maps_to__ = "partner_export"
    __classname__ = "partner_export"


class ExportedFile(Object):
    __maps_to__ = "exported_file"
    __classname__ = "exported_file"


@classbody
class Document(object):
    # customer export / generating partner names
    def on_cdbwsm_create_partner_filenames_now(self, ctx):
        org = ctx.dialog.organization_id
        self.create_partner_filenames(org)

    def create_partner_filenames(self, org):
        """
        Create partner filenames for all files of this doc and initialize them from cdbf_original_name.

        :param org cdb_object_id of an organization
        """
        for f in self.Files:
            if not f.cdb_belongsto and not f.cdbf_derived_from:
                existing = PartnerFilename.ByKeys(f.cdb_object_id, org)
                if existing:
                    logging.info(
                        u"Partner filename for file %s and partner %s already exists. No new entry created.",
                        f.cdbf_name,
                        org,
                    )
                else:
                    partner_filename = f.cdbf_original_name
                    if not partner_filename:
                        if f.cdbf_name:
                            partner_filename = os.path.splitext(f.cdbf_name)[0]
                        else:
                            partner_filename = ""
                    PartnerFilename.Create(
                        file_id=f.cdb_object_id,
                        organization_id=org,
                        document_id=self.cdb_object_id,
                        partner_filename=partner_filename,
                        generated=1,
                    )

    @classmethod
    def on_cdbwsm_create_partner_filenames_pre_mask(cls, ctx):
        """
        If there is a unique organization for previously generated entries (among all selected documents),
        reuse this organization.
        Otherwise, let the user select an org.
        """
        doc_ids = []
        for doc in cls.PersistentObjectsFromContext(ctx):
            doc_ids.append(doc.cdb_object_id)
        partners = Document.find_export_partners(doc_ids, only_generated=True)
        if len(partners) == 1:
            (partner,) = partners
            orgs = Organization.KeywordQuery(cdb_object_id=partner)
            if orgs:
                org = orgs[0]
                ctx.set("organization_id", org.cdb_object_id)
                ctx.set("organization", org.name)
                ctx.set_fields_readonly(["organization_id", "organization"])

    @staticmethod
    def find_export_partners(doc_ids, only_generated):
        partners = set()
        for chunk in chunks(doc_ids, 900):
            doc_ids_string = u",".join("'" + sqlapi.quote(val) + "'" for val in chunk)
            condition = u"document_id IN (%s)" % doc_ids_string
            if only_generated:
                condition += u" AND generated = 1"
            records = sqlapi.RecordSet2(
                "partner_filename", condition, columns=["organization_id"]
            )
            for record in records:
                partners.add(record.organization_id)
        return list(partners)

    @staticmethod
    def get_export_names(doc_ids, partner_id):
        doc_ids_string = u",".join("'" + sqlapi.quote(val) + "'" for val in doc_ids)
        sql = """
        SELECT cdb_file.cdbf_name,
               cdb_file.cdb_object_id,
               cdb_file.cdbf_object_id,
               partner_filename.partner_filename
        FROM
               cdb_file
        LEFT JOIN
               partner_filename
        ON
               cdb_file.cdb_object_id = partner_filename.file_id
        WHERE
               organization_id = '%s'
               AND partner_filename.document_id IN (%s)
        """ % (
            partner_id,
            doc_ids_string,
        )
        record_set = sqlapi.RecordSet2(sql=sql)
        return record_set

    def copy_partner_names(self, ctx):
        # when creating an index from Workspaces Desktop: copy partner filenames from original version
        if ctx.active_integration == "wspmanager":
            original_doc = ctx.cdbtemplate["cdb_object_id"]
            for file_copy in self.Files:
                if not file_copy.cdb_belongsto and not file_copy.cdbf_derived_from:
                    original_file = CDB_File.KeywordQuery(
                        cdb_wspitem_id=file_copy.cdb_wspitem_id,
                        cdbf_object_id=original_doc,
                    )
                    if original_file:
                        original_file = original_file[0]
                        original_partner_filenames = PartnerFilename.KeywordQuery(
                            file_id=original_file.cdb_object_id
                        )
                        for original_partner_filename in original_partner_filenames:
                            original_partner_filename.Copy(
                                document_id=self.cdb_object_id,
                                file_id=file_copy.cdb_object_id,
                            )

    event_map = {
        ("cdb_cad_wsm_edit", "now"): "open_cad_file",
        ("index", "post"): "copy_partner_names",
    }


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in six.moves.range(0, len(l), n):
        yield l[i : i + n]
