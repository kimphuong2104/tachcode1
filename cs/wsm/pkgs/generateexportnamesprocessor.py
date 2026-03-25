#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from __future__ import absolute_import
from datetime import datetime
import logging
import os

from cdb import util
from cdb import auth
from cdb import sqlapi
from cdb.objects import ByID
from cdb.objects.org import Organization
from cs.wsm.partnerexport import PartnerExport, ExportedFile, PartnerFilename

from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes
from cs.wsm.pkgs.pkgsutils import grouper
import six


class GenerateExportNamesProcessor(CmdProcessorBase):
    """
    Generate initial partner names.
    """

    name = u"generateexportnames"

    def call(self, resultStream, request):
        bObjsWithFileHashes = self._parseInput()
        if bObjsWithFileHashes is None:
            return WsmCmdErrCodes.invalidCommandRequest

        partner_id = self._rootElement.export_partner_id
        self._generate_export_names(bObjsWithFileHashes, partner_id)
        self._saveInitialExportInfo(
            bObjsWithFileHashes, partner_id, self._rootElement.export_title
        )
        return WsmCmdErrCodes.messageOk

    def _parseInput(self):
        """
        :return: dict(cdb_object_id of BObject -> dict(cdb_object_id of file -> original_blob_hash))
        """
        res = None
        contexts = self._rootElement.getChildrenByName("WSCOMMANDS_CONTEXTOBJECT")
        if len(contexts) > 0:
            res = {}
            for context in contexts:
                hashes = {}
                for cmdObj in context.getChildrenByName("WSCOMMANDS_OBJECT"):
                    fileId = cmdObj.cdb_object_id
                    hashes[fileId] = cmdObj.hash
                res[context.cdb_object_id] = hashes
        return res

    def _generate_export_names(self, bObjsWithFileHashes, partner_id):
        for cdb_object_id in bObjsWithFileHashes:
            doc = ByID(cdb_object_id)
            if doc:
                doc.create_partner_filenames(partner_id)
            else:
                logging.error(
                    "GenerateExportNamesProcessor: unknown doc %s", cdb_object_id
                )

    def _saveInitialExportInfo(self, bObjsWithFileHashes, partner_id, title):
        """
        Creates an initial PartnerExport object and remembers the original hashes.
        If such an export already exist for the given partner, reuses that export object and adds the new hashes.

        Purpose: to allow for partner import without preceeding partner export.
        """
        orgs = Organization.KeywordQuery(cdb_object_id=partner_id)
        if orgs is None:
            logging.error("GenerateExportNamesProcessor: unknown org %s", partner_id)
            return

        allHashes = {}
        for hashes in six.itervalues(bObjsWithFileHashes):
            allHashes.update(hashes)

        if not allHashes:
            # this is ok for workspaces created before 3.13
            logging.warning("GenerateExportNamesProcessor: no hashes")
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # check if there already is a special initial export info
        exports = PartnerExport.KeywordQuery(
            organization_id=partner_id, is_initial_import=1
        )
        if exports:
            export = exports[0]
            export.Update(timestamp=timestamp)
        else:
            newId = util.nextval("WSM_PARTNER_EXPORT_SEQ")
            export = PartnerExport.Create(
                export_id=newId,
                is_initial_import=1,
                organization_id=partner_id,
                title=title,
                timestamp=timestamp,
                creator=auth.persno,
            )
        fileIds = list(allHashes)
        blobIds = self._findBlobIds(fileIds)

        for fileId, fileHash in six.iteritems(allHashes):
            blobId = blobIds.get(fileId)
            partnerFilename = PartnerFilename.KeywordQuery(
                file_id=fileId, organization_id=partner_id
            )
            if partnerFilename:
                partnerFilename = partnerFilename[0]
                basename = partnerFilename.partner_filename
                f = ByID(fileId)
                if f is not None:
                    full_filename = f.cdbf_name
                    _, ext = os.path.splitext(full_filename)
                    partner_filename = os.path.normcase(basename + ext)
                    exportedFile = ExportedFile.ByKeys(export.export_id, fileId)
                    if exportedFile is not None:
                        exportedFile.Update(
                            hash=fileHash,
                            partner_filename=partner_filename,
                            original_blob=blobId,
                        )
                    else:
                        ExportedFile.Create(
                            export_id=export.export_id,
                            hash=fileHash,
                            file_id=fileId,
                            partner_filename=partner_filename,
                            original_blob=blobId,
                        )
                else:
                    logging.error(
                        "_saveInitialExportInfo: can't find cdb_file %s", fileId
                    )
            else:
                logging.error(
                    "_saveInitialExportInfo: can't find parter filename for file %s",
                    fileId,
                )

    def _findBlobIds(self, fileIds):
        """
        :param fileIds sequence of cdb_object_ids of files
        :return: dict(cdb_object_id of file -> cdbf_blob_id)
        """
        result = {}
        for chunk in grouper(900, fileIds):
            expr = ",".join(u"'%s'" % fileId for fileId in chunk)
            sql = (
                "SELECT cdb_object_id, cdbf_blob_id FROM cdb_file WHERE cdb_object_id IN (%s)"
                % expr
            )
            rs = sqlapi.RecordSet2(sql=sql)
            for record in rs:
                result[record.cdb_object_id] = record.cdbf_blob_id
        return result
