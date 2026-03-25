#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from __future__ import absolute_import
import os

from cdb import util, sqlapi, auth
from cs.wsm.partnerexport import PartnerExport, ExportedFile

from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes


class SaveExportInfoProcessor(CmdProcessorBase):
    name = u"saveexportinfo"

    def call(self, resultStream, request):
        exportedFiles = self._rootElement.getChildrenByName("EXPORTED_FILE")
        partnerId = self._rootElement.export_partner_id
        exportTitle = self._rootElement.export_title
        timestamp = self._rootElement.timestamp

        self._saveExportInfo(partnerId, exportTitle, timestamp, exportedFiles)
        return WsmCmdErrCodes.messageOk

    def _saveExportInfo(self, partnerId, exportTitle, timestamp, exportedFiles):
        # the export may already exist (because this processor is called in multiple steps for better feedback)
        exports = PartnerExport.KeywordQuery(
            organization_id=partnerId, timestamp=timestamp
        )
        if exports:
            export = exports[0]
        else:
            newId = util.nextval("WSM_PARTNER_EXPORT_SEQ")
            export = PartnerExport.Create(
                export_id=newId,
                organization_id=partnerId,
                title=exportTitle,
                timestamp=timestamp,
                creator=auth.persno,
            )
        blobIds = self._findBlobIds(exportedFiles)
        for f in exportedFiles:
            blobId = blobIds.get(f.cdb_object_id)
            relPath = os.path.normcase(f.rel_path)
            ExportedFile.Create(
                export_id=export.export_id,
                hash=f.exported_hash,
                file_id=f.cdb_object_id,
                partner_filename=relPath,
                original_blob=blobId,
            )

    def _findBlobIds(self, exportedFiles):
        """
        :param exportedFiles: list of etree elements
        :return: dict(cdb_object_id of file -> cdbf_blob_id)
        """
        result = {}
        fileIds = ",".join(
            u"'%s'" % exportedFile.cdb_object_id for exportedFile in exportedFiles
        )
        sql = (
            "SELECT cdb_object_id, cdbf_blob_id FROM cdb_file WHERE cdb_object_id IN (%s)"
            % fileIds
        )
        rs = sqlapi.RecordSet2(sql=sql)
        for record in rs:
            result[record.cdb_object_id] = record.cdbf_blob_id
        return result
