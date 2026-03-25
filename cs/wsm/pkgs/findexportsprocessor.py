#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from __future__ import absolute_import

import logging
import os
import six

from lxml import etree
from cdb import sqlapi
from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes


class FindExportsProcessor(CmdProcessorBase):
    """
    Given a set of files to import from a partner,
    calculates the possible target documents and the change state of the files
    based on the information about previous partner exports.
    """

    name = u"findexports"

    def call(self, resultStream, request):
        importFiles = self._rootElement.getChildrenByName("IMPORT_FILE")
        files = {os.path.normcase(imp.rel_path): imp for imp in importFiles}

        mapping = self._assignExactMatches(files)
        exportCandidates = self._findExportCandidates(files)

        # retrieve document attributes (for display)
        allMappings = [mapping]
        for exportCandidate in exportCandidates:
            allMappings.append(exportCandidate["mapping"])
        documentInfo = self._retrieveDocInformation(allMappings)

        self._writeReply(resultStream, mapping, exportCandidates, documentInfo)
        return WsmCmdErrCodes.messageOk

    def _assignExactMatches(self, files):
        """
        Find documents for unchanged files, i.e. the hash is still the same as exported.

        :return: list({rel_path, document_id, server_status, local_status})
        """
        mapping = {}

        # split to limit size of SQL statement
        for chunk in chunks(list(six.iteritems(files)), 400):
            terms = []
            for importedFile in chunk:
                relPath = sqlapi.quote(importedFile[0])
                fileHash = sqlapi.quote(importedFile[1].hash)
                terms.append(
                    "(partner_filename = '%s' AND hash = '%s')" % (relPath, fileHash)
                )
            cond = " OR ".join(terms)
            sql = (
                "SELECT f.partner_filename, f.original_blob, f.hash, "
                "       e.timestamp, "
                "       f2.cdbf_object_id, f2.cdbf_blob_id, f2.cdbf_name, f2.cdb_mdate, "
                "       a.name "
                "FROM exported_file f "
                "JOIN partner_export e ON e.export_id = f.export_id "
                "JOIN cdb_file f2 ON f2.cdb_object_id = f.file_id "
                "JOIN angestellter a on a.personalnummer = f2.cdb_mpersno "
                "WHERE %s" % cond
            )
            rs = sqlapi.RecordSet2(sql=sql)
            for record in rs:
                relPath = record.partner_filename
                existing = mapping.get(relPath)
                if not existing or existing["timestamp"] < record.timestamp:
                    info = self._createExportInfoFromRecord(record, files)
                    info["timestamp"] = record.timestamp  # for comparison only
                    mapping[relPath] = info
        return mapping.values()

    def _findExportCandidates(self, files):
        """
        :return: list({title, partner, timestamp, mapping: {relPath -> {document_id, server_status, local_status})
        """
        # first find all exports containing at least one of the filenames
        exportIds = self._findAffectedExports(files)
        exports = []
        for exportId in exportIds:
            exportInfo = self._getExportInfo(exportId, files)
            if exportInfo:
                exports.append(exportInfo)
        exports.sort(key=lambda e: e["timestamp"], reverse=True)
        return exports

    def _findAffectedExports(self, files):
        """
        :return: set of export ids
        """
        exportIds = set()
        # split to limit size of SQL statement
        for chunk in chunks(list(files), 400):
            args = []
            for importedFile in chunk:
                relPath = "'%s'" % sqlapi.quote(importedFile)
                args.append(relPath)
            cond = ", ".join(args)
            sql = (
                "SELECT e.export_id "
                "FROM partner_export e "
                "WHERE EXISTS (SELECT NULL"
                "              FROM exported_file f"
                "              WHERE f.export_id = e.export_id "
                "                AND f.partner_filename IN (%s))" % cond
            )
            rs = sqlapi.RecordSet2(sql=sql)
            for record in rs:
                exportIds.add(record.export_id)
        return exportIds

    def _getExportInfo(self, exportId, files):
        """
        :return: list({title, timestamp, organization_name, mapping})
        """
        export = self._getExportMetaData(exportId)
        if export:
            mapping = self._getExportMapping(exportId, files)
            export["mapping"] = mapping
        return export

    def _getExportMetaData(self, exportId):
        res = None
        sql = (
            "SELECT e.title, e.timestamp, e.organization_id, o.name, a.name as creator "
            "FROM partner_export e "
            "LEFT JOIN cdb_org o ON o.cdb_object_id = e.organization_id "
            "LEFT JOIN angestellter a on a.personalnummer = e.creator "
            "WHERE e.export_id = '%s'" % exportId
        )
        rs = sqlapi.RecordSet2(sql=sql)
        if rs:
            res = {
                "title": rs[0].title,  # pylint: disable=no-member
                "timestamp": rs[0].timestamp,  # pylint: disable=no-member
                "organization_name": rs[0].name,  # pylint: disable=no-member
                "organization_id": rs[0].organization_id,  # pylint: disable=no-member
                "creator_name": rs[0].creator,  # pylint: disable=no-member
            }
        return res

    def _getExportMapping(self, exportId, files):
        """
        :return: list({rel_path, document_id, server_status, local_status})
        """
        sql = (
            "SELECT f.partner_filename, f.original_blob, f.hash, "
            "       f2.cdbf_object_id, f2.cdbf_blob_id, f2.cdbf_name, f2.cdb_mdate, "
            "       a.name "
            "FROM exported_file f "
            "LEFT JOIN cdb_file f2 ON f2.cdb_object_id = f.file_id "
            "JOIN angestellter a on a.personalnummer = f2.cdb_mpersno "
            "WHERE f.export_id = '%s'" % exportId
        )
        rs = sqlapi.RecordSet2(sql=sql)
        mapping = []
        for record in rs:
            mapping.append(self._createExportInfoFromRecord(record, files))
        return mapping

    def _createExportInfoFromRecord(self, record, files):
        """
        :param record: DB record representing an exported file
        :param dict(normcased relpath -> {rel_path, hash})
        :return: dict describing a doc assignment and file status
        """
        optionalLocalHash = None
        relPath = record.partner_filename
        importFile = files.get(relPath)
        if importFile:
            optionalLocalHash = importFile.hash
            relPath = importFile.rel_path

        server_status = " "
        if not record.cdbf_blob_id:
            server_status = "D"
        elif record.cdbf_blob_id != record.original_blob:
            server_status = "M"

        local_status = " "
        if not optionalLocalHash:
            local_status = "D"
        elif optionalLocalHash != record.hash:
            local_status = "M"

        res = {
            "rel_path": relPath,
            "document_id": record.cdbf_object_id,
            "cdbf_name": record.cdbf_name,
            "last_changed": record.cdb_mdate.isoformat(),
            "last_changed_by": record.name,
            "server_status": server_status,
            "local_status": local_status,
        }
        return res

    def _retrieveDocInformation(self, mappings):
        docIds = set()
        for mapping in mappings:
            for attrs in mapping:
                docIds.add(attrs["document_id"])
        result = []
        # split to limit size of SQL statement
        for chunk in chunks(list(docIds), 400):
            cond = ",".join("'%s'" % sqlapi.quote(docId) for docId in chunk)
            sql = (
                "SELECT z.cdb_object_id, z.z_nummer, z.z_index, z.titel, z.benennung "
                "FROM zeichnung_v z "
                "WHERE z.cdb_object_id in (%s)" % cond
            )
            rs = sqlapi.RecordSet2(sql=sql)
            for record in rs:
                attrs = {key: record[key] or u"" for key in record.keys()}
                result.append(attrs)
        return result

    def _writeReply(self, resultStream, assignedDocs, exports, docInfos):
        logging.info(u"FindExportsProcessor: building reply")
        result = etree.Element("WSCOMMANDRESULT")

        if assignedDocs:
            mapping = self._serializeMapping(assignedDocs)
            result.append(mapping)

        exportsEl = etree.Element("EXPORTS")
        for export in exports:
            exportMapping = export["mapping"]
            del export["mapping"]
            exportEl = etree.Element("EXPORT", export)
            mapping = self._serializeMapping(exportMapping)
            exportEl.append(mapping)
            exportsEl.append(exportEl)
        result.append(exportsEl)

        docsInfosEl = etree.Element("DOCUMENTS")
        for docInfo in docInfos:
            docInfoEl = etree.Element("DOCUMENT", docInfo)
            docsInfosEl.append(docInfoEl)
        result.append(docsInfosEl)

        xmlStr = etree.tostring(result, encoding="utf-8")
        resultStream.write(xmlStr)
        return WsmCmdErrCodes.messageOk

    def _serializeMapping(self, mapping):
        el = etree.Element("MAPPING")
        for attrs in mapping:
            fileEl = etree.Element("FILE", attrs)
            el.append(fileEl)
        return el


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in six.moves.range(0, len(l), n):
        yield l[i : i + n]
