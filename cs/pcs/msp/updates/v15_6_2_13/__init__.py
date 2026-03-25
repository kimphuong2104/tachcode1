#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import io
import json

from cdb import sqlapi, transactions
from cdb.comparch import modules, protocol
from cdb.storage import blob
from cdb.storage.exceptions import DuplicateIdError

from cs.pcs.msp.updates.v15_5_0 import revert_deleted_patch


class InstallMSPTemplateFile:
    """This script installs the Microsoft Project Template File"""

    __uuid__ = "b5b7c1c3-1a68-11ea-bb02-dc4a3e92c6e8"
    __blob__ = "bd7f2e6b-aba1-4ade-acd7-8eaff06b98d1"

    def _upload_blob(self, blob_id):
        # copied from cdb.InstallScript.CDBInstallScripBase.install_blobs
        bs = blob.getBlobStore("main")
        m = modules.Module.ByKeys("cs.pcs.msp")
        fname = f"{m.std_conf_blobs_dir}/{blob_id}"
        fname_meta = f"{fname}.meta"

        with io.open(fname_meta, "rb") as fd:
            metadata = json.load(fd)

        ul = bs.Upload(meta=metadata, _blob_id=blob_id)

        try:
            with io.open(fname, "rb") as fd:
                while True:
                    block = fd.read(256 * 1024)
                    if block:
                        ul.write(block)
                    else:
                        break
            new_blob_id = ul.close()
        except DuplicateIdError:
            # can happen if there is a failure during PUT operation and
            # the close() fails, but the blob should have been written anyway.
            protocol.logMessage(
                f"Got duplicate ID for blob {blob_id}, " "verifying if it exists"
            )
            ul = None

            try:
                checker = bs.Download(blob_id, only_metadata=True)
                checker.close()
            except Exception:
                protocol.logError(
                    f"Failed to verify existence of blob {blob_id} in blobstore. "
                    "Try cleaning up the 'incoming' area of the blob store "
                    "and retry."
                )
                raise

            protocol.logMessage(f"OK. Blob {blob_id} exists in the blob store")
            new_blob_id = blob_id

        if new_blob_id != blob_id:
            raise RuntimeError(f"Blob upload failed; blob ID became '{new_blob_id}'")

    def run(self):
        files = sqlapi.RecordSet2(
            "cdb_file",
            """cdbf_object_id IN (
                SELECT cdb_object_id FROM zeichnung
                WHERE z_nummer = 'MSP_TEMPLATE')""",
        )

        if files:
            protocol.logMessage("MSP template file already present skipping...")
            return

        protocol.logMessage("MSP template file not found trying to revert patch...")
        with transactions.Transaction():
            revert_deleted_patch(
                "cs.pcs.msp",
                "cdb_file",
                cdb_object_id=self.__uuid__,
            )
            self._upload_blob(self.__blob__)


pre = []
post = [InstallMSPTemplateFile]
