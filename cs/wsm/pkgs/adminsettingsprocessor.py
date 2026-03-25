#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from __future__ import absolute_import
import logging
import uuid
from lxml import etree

from cdb.objects.cdb_file import cdb_file_record
from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes
from cs.wsm.pkgs.cdbversion import GetCdbVersionProcessor
from cs.wsm.wsm_settings import WsmSettings


class AdminSettingsProcessor(CmdProcessorBase):
    """
    Read and write administrative Workspaces Desktop settings.
    """

    name = u"syncwsmsettings"

    def call(self, resultStream, request):

        self._use_direct_blob = GetCdbVersionProcessor.checkPresignedBlobConfig() == 0
        parameter = self._parseInput()
        if parameter is None:
            return WsmCmdErrCodes.invalidCommandRequest

        context, wsm_version, mode, requested_files = parameter

        wsmSettings = None
        if mode == "read":
            wsmSettings = WsmSettings.find_valid_settings(context, wsm_version)
        elif mode == "write":
            wsmSettings = WsmSettings.find_settings_to_update(context, wsm_version)
            if wsmSettings:
                # only Delete Files that did not exist anymore,
                # and  create records for new files if we are in blobstore mode
                if wsmSettings.CheckAccess("save"):
                    if self._use_direct_blob:
                        self._syncFiles(wsmSettings, requested_files)
                    else:
                        wsmSettings.Files.Delete()
                else:
                    wsmSettings = None

        reply = self._createReply(wsmSettings, mode)
        replyString = etree.tostring(reply, encoding="utf-8")
        resultStream.write(replyString)

        return WsmCmdErrCodes.messageOk

    def _syncFiles(self, settingsBo, filenames):
        """
        settingsBo: WsmSettingsObject
        filenames: set of basenames
        """
        existing = dict()
        for f in settingsBo.Files:
            existing[f.cdbf_name] = f
        existingSet = set(existing.keys())
        toDel = existingSet - filenames
        toAdd = filenames - existingSet
        logging.debug("adminsettings._syncFiles: To delete: %s", toDel)
        for d in toDel:
            existing[d].Delete()
        logging.debug("adminsettings._syncFiles: To add: %s", toAdd)
        for a in toAdd:
            cdb_file_record.Create(
                cdbf_name=a,
                cdbf_object_id=settingsBo.cdb_object_id,
                cdb_wspitem_id=str(uuid.uuid4()),
                cdb_folder="",
                cdbf_primary="0",
                cdbf_type="wsmsettings",
                cdb_lock="",
                cdb_lock_id="",
            )

    def _parseInput(self):
        """
        Get input parameters from XML.

        :Return:
            Either None or (context, wsm_version, mode) with
            context : string
                settings context which Workspaces Desktop is running in
            wsm_version: string
                e.g. "3.6"
            mode : "read" or "write"
                True if writing, False if reading
        """
        mode = "read"
        requested_filenames = None
        mainElement = self._rootElement.etreeElem.find("READWSMSETTINGS")
        if mainElement is None:
            mainElement = self._rootElement.etreeElem.find("SAVEWSMSETTINGS")
            mode = "write"
            if mainElement is None:
                logging.error(
                    "AdminSettingsProcessor: invalid request; no READWSMSETTINGS or SAVEWSMSETTINGS element"
                )
                return None
            requested_filenames = set()
            for f in mainElement:
                if f.tag == "FILE":
                    fname = f.attrib["name"]
                    requested_filenames.add(fname)

        if "context" not in mainElement.attrib:
            logging.error(
                "AdminSettingsProcessor: invalid request; no context attribute"
            )
            return None
        context = mainElement.attrib["context"]

        if "wsmversion" not in mainElement.attrib:
            logging.error(
                "AdminSettingsProcessor: invalid request; no wsmversion attribute"
            )
            return None
        wsm_version = mainElement.attrib["wsmversion"]

        return context, wsm_version, mode, requested_filenames

    def _createReply(self, wsmSettings, mode):
        """
        :param wsmSettings WsmSettings object or None
        """
        root = etree.Element("REPLY")

        if wsmSettings is not None:
            settingsEl = etree.Element(
                "WSMSETTINGS",
                {
                    "cdb_object_id": wsmSettings.cdb_object_id,
                    "context": wsmSettings.context,
                    "index": str(wsmSettings.s_index),
                    "wsmversion": wsmSettings.wsm_version,
                },
            )
            root.append(settingsEl)
            if mode == "write":
                files = cdb_file_record.KeywordQuery(
                    cdbf_object_id=wsmSettings.cdb_object_id
                )
            else:
                files = wsmSettings.Files
            for f in files:
                blob_id = f.cdbf_blob_id
                if blob_id is None:
                    blob_id = ""
                accessible = f.CheckAccess("read_file")
                attrs = {
                    "cdb_object_id": f.cdb_object_id,
                    "name": f.cdbf_name,
                    "blobid": blob_id,
                    "accessible": "1" if accessible else "0",
                }
                if self._use_direct_blob:
                    if mode == "write":
                        attrs["blob_url"] = f.presigned_blob_write_url(
                            check_access=False
                        )
                    else:
                        attrs["blob_url"] = f.presigned_blob_url(
                            check_access=False, emit_read_signal=False
                        )
                logging.debug("AdminSettingsProcessor: BlobAttrs: %s", attrs)
                fileEl = etree.Element("FILE", attrs)
                settingsEl.append(fileEl)
        return root
