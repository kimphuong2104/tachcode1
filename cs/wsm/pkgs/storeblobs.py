# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module storeblobs

This is the documentation for the storeblobs module.
"""
from __future__ import absolute_import
import logging

from lxml.etree import Element
from lxml import etree as ElementTree

from cdb.objects.objectstore import OBJECT_STORE
from cdb.objects.cdb_file import CDB_File, cdb_file_base
from cdb import transactions
from cdb.storage.index import IndexListener
from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes

try:
    from cdb.platform.mom.hooks import PowerscriptHook
    from cdb.objects.cdb_file import FileChanges
except ImportError:
    PowerscriptHook = None
    FileChanges = None


class CTX(object):
    """
    Dummy Context for write file histroy
    """

    def __init__(self, action):
        self.action = action


class StoreBlobsProcessor(CmdProcessorBase):
    """
    Handler class for filetype command.

    This class is used to fetch the filetype definitions from the PDM server.
    """

    name = u"store_blobs"

    def __init__(self, rootElement):
        CmdProcessorBase.__init__(self, rootElement)
        self._use_cdbf_fsize = CDB_File.HasField("cdbf_fsize")
        self._cdbf_size_available = CDB_File.HasField("cdbf_size")

    def call(self, resultStream, request):
        """
        Retrieve file types from PDM system.

        :Returns: integer indicating command success
        """

        cmdResultElement = Element("WSCOMMANDRESULT")
        self.processBlobs(cmdResultElement)
        xmlStr = ElementTree.tostring(cmdResultElement, encoding="utf-8")
        resultStream.write(xmlStr)
        return WsmCmdErrCodes.messageOk

    def _fsizeAttrs(self, el):
        """
        :returns dict with f_size_attrs
        """
        attrs = {}
        cdbf_size = el.attrib["cdbf_size"]
        if self._use_cdbf_fsize and cdbf_size.isdigit():
            attrs["cdbf_fsize"] = int(cdbf_size)
        if self._cdbf_size_available:
            attrs["cdbf_size"] = cdbf_size
        return attrs

    def _updateFile(self, file_obj, el):
        """
        :param file_obj: CDB_File
        :param el: BLOBINFO Element
        """
        cc = CDB_File.MakeChangeControlAttributes()
        file_obj.writeFileHistory(CTX("modify"))
        file_obj.deleteDerivedFiles()
        attrs = {
            "cdbf_blob_id": el.attrib["cdbf_blob_id"],
            "cdb_mdate": cc["cdb_mdate"],
            "cdb_mpersno": cc["cdb_mpersno"],
            "cdbf_fdate": el.attrib["cdbf_fdate"],
            "cdbf_hash": el.attrib["cdbf_hash"],
        }
        attrs.update(self._fsizeAttrs(el))
        file_obj.Update(**attrs)

    def processBlobs(self, cmdResultElement):
        logging.debug("StoreBlobProcessor.processBlobs start***")
        use_index_blocker = hasattr(IndexListener, "block_relation")
        if use_index_blocker:
            file_changes = None
            logging.debug("StoreBlobProcessor.processBlobs is using indexblocker")
            with IndexListener().block_relation("cdb_file"):
                file_changes = self._processBlobs(cmdResultElement)
        else:
            file_changes = self._processBlobs(cmdResultElement)
        if file_changes is not None:
            # in this hook, cs.documents updates the affected documents (and also initiates text extractor jobs)
            self._wsmUploadFilesHook(file_changes, cmdResultElement)
        logging.debug("StoreBlobProcessor.processBlobs end***")

    def _processBlobs(self, cmdResultElement):
        """
        Input:
        <WSMCOMMANDS cmd="store_blobs">
          <BLOBINFO cdbf_blob_id = "" cdb_object_id="" cdbf_hash="", cdbf_fdate="", cdbf_size="" action="">
          <BLOBINFO cdbf_blob_id = "" cdb_object_id="" cdbf_hash="", cdbf_fdate="", cdbf_size="" action="">
        </WSMCOMMANDS>
        Result:
        <WSMCOMMANDRESULT>
          <ERROR>text</ERROR>, wenn es einen Fehler gab, gibt es error Eintraege, sonst ist die Liste leer
          <INFO>text</INFO>,   Mitteilungen, Hinweise koenen uber Info-Eintrage gesendet werden.
        </WSMCOMMANDRESULT>
        """
        if FileChanges is None or PowerscriptHook is None:
            el = Element("ERROR")
            el.text = """CE Platform doesn't support FileChange Hooks.
                         Fast blob transfer is not allowed."""
            cmdResultElement.append(el)
            return None
        bc = FileChanges()
        rootEl = self.getRoot().etreeElem
        file_items = dict()
        with transactions.Transaction():
            for el in rootEl:
                if el.tag == "BLOBINFO":
                    file_items[el.attrib["cdb_object_id"]] = el
                elif el.tag == "BO":
                    pass
                    # This is not an error, For backwards cmpabilty
                    # we got this elements, but it's not
                    # need anymore
                    # All other elements are not expected.
                else:
                    err_el = Element("ERROR")
                    err_el.text = "Unknown element '%s'" % el.tag
                    logging.error(err_el.text)
                    cmdResultElement.append(err_el)

            file_objs = cdb_file_base.KeywordQuery(cdb_object_id=list(file_items))
            cc = CDB_File.MakeChangeControlAttributes()
            for file_obj in file_objs:
                el = file_items.get(file_obj.cdb_object_id)
                if file_obj.cdb_classname == u"cdb_file_record":

                    attrs = {
                        "cdb_classname": "cdb_file",
                        "cdbf_blob_id": el.attrib["cdbf_blob_id"],
                        "cdb_mdate": cc["cdb_mdate"],
                        "cdb_cdate": cc["cdb_cdate"],
                        "cdb_cpersno": cc["cdb_cpersno"],
                        "cdb_mpersno": cc["cdb_mpersno"],
                        "cdbf_fdate": el.attrib["cdbf_fdate"],
                        "cdbf_hash": el.attrib["cdbf_hash"],
                    }
                    attrs.update(self._fsizeAttrs(el))
                    file_obj.Update(**attrs)
                    bc.addFile(file_obj.cdb_object_id, "create")
                elif file_obj.cdb_classname == u"cdb_file":
                    self._updateFile(file_obj, el)
                    bc.addFile(file_obj.cdb_object_id, "modify")
                else:
                    logging.error(
                        "Unexpected Class for file record: classname: %s , object_id: %s",
                        file_obj.cdb_classname,
                        file_obj.cdb_object_id,
                    )
                    err_el = Element("ERROR")
                    err_el.text = (
                        "Unexpected Class for file record: classname: %s, object_id: %s"
                        % (file_obj.cdb_classname, file_obj.cdb_object_id)
                    )
                    cmdResultElement.append(err_el)
        return bc

    def _wsmUploadFilesHook(self, file_changes, cmdResultElement):
        """
        :param file_changes: FileChanges
        """
        OBJECT_STORE.clear()
        callables = PowerscriptHook.get_active_callables("WSMUploadFiles")
        for c in callables:
            logging.debug("Calling WSMUploadFiles Hook")
            try:
                error_list = c(file_changes)
            except Exception as e:
                logging.error("Call of  WSMUploadFiles failed with: %s", e)
                error_list = [("ERROR", "WSMUploadFiles Hook: Exception: %s" % str(e))]
            # Transfer messages to WSM
            if error_list:
                for error_type, msg in error_list:
                    el = Element(error_type)
                    el.text = msg
                    cmdResultElement.append(el)
