#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#

from __future__ import absolute_import

import os

from cdb import ue
from cdb.objects import Object, ByID, Rule
from cdb.objects.org import Organization
from cdb.platform.gui import CDBCatalogContent, CDBCatalog


class PartnerFilename(Object):
    __maps_to__ = "partner_filename"
    __classname__ = "partner_filename"

    def on_create_pre(self, ctx):
        self._check_unique()

    def on_modify_pre(self, ctx):
        self._check_unique()

    def _check_unique(self):
        others = PartnerFilename.KeywordQuery(
            document_id=self.document_id, organization_id=self.organization_id
        )
        own_file = ByID(self.file_id)
        if own_file:
            for other in others:
                other_file = ByID(other.file_id)
                if other_file:
                    # in same folder?
                    if other_file.cdb_folder == own_file.cdb_folder or (
                        not other_file.cdb_folder and not own_file.cdb_folder
                    ):  # NULL, ""
                        # same case-insensitive partner filename?
                        if (
                            self.partner_filename
                            and other.partner_filename
                            and self.partner_filename.lower()
                            == other.partner_filename.lower()
                        ):
                            # same file extension of original name?
                            if (
                                os.path.splitext(own_file.cdbf_name)[1].lower()
                                == os.path.splitext(other_file.cdbf_name)[1].lower()
                            ):
                                raise ue.Exception(
                                    "cdb_cad_wsm_partner_filename_already_exists",
                                    self.partner_filename,
                                )


class WSMPartnerCatalogContent(CDBCatalogContent):
    """
    We use Powerscript for this catalog
    because we want to filter the entries by the object rule "WSM: partners for export".
    """

    def __init__(self, catalog):
        # standard catalog init code
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        tabdef = self.cdef.getProjection(tabdefname, True)
        CDBCatalogContent.__init__(self, tabdef)

        # retrieve the matching organizations
        self.partners = []
        rule = Rule.ByKeys(name="WSM: partners for export")
        for org in Organization.Query():
            if rule is None or rule.match(org):
                self.partners.append(org)

    def getNumberOfRows(self):
        return len(self.partners)

    def getRowObject(self, row):
        return self.partners[row].ToObjectHandle()


class WSMPartnerCatalog(CDBCatalog):
    def init(self):
        self.setResultData(WSMPartnerCatalogContent(self))
