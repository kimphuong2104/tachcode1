#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2009 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     wsmcommandprocessor.py
# Author:   jro
# Creation: 07.12.09
# Purpose:

"""
Module wsmcommandprocessor.py

Registers and executes command processors
"""
from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import base64
import hmac
import zlib
import logging
import six
import hashlib
import pkg_resources


from cdb import fls
from cdb import sqlapi
from cdb import rte

from lxml import etree as ElementTree
from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes
from cs.wsm.pkgs.modifycdbobjectcommand import ModifyObjectsProcessor
from cs.wsm.pkgs.xmlmapper import (
    xmlTree2Object,
    LIC_FEATURE_REPLY,
    FEATURE_STATUS,
    SERVER_REPLY_HASH_EQUAL,
)
from cs.wsm.cdbwsmcommands import version_greater_equal

from cs.wsm.pkgs.cdbversion import GetCdbVersionProcessor
from cs.wsm.pkgs.licenserequest import LicenseRequestHandler
from cs.wsm.pkgs.servertimingwrapper import measuringPoint, timingWrapper, timingContext


class WsmCommandProcessor(object):
    def __init__(self, inputLines):
        self._input = inputLines
        self._cmdRegistry = dict()  # (cmdName->CommandProcessor)
        # register basic commands to make version and licence working
        # even if cs.workspaces package is incompatible (minimize number of
        # imports on module level)
        self._addCommand(GetCdbVersionProcessor)
        self._addCommand(LicenseRequestHandler)
        # do lazy initializing of advanced commands later
        self._commandsInitialized = False

    def _addCommand(self, cmdProcessor):
        cmdName = cmdProcessor.name
        self._cmdRegistry[cmdName] = cmdProcessor

    def _getCommand(self, cmdName):
        """
        Returns command with given name or None
        returns: CmdProcessorBase
        """
        command = None
        if cmdName in self._cmdRegistry:
            command = self._cmdRegistry[cmdName]
        else:
            # initialize advanced commands on first try
            self._initializeAdvancedCommands()
            command = self._cmdRegistry.get(cmdName, None)

        return command

    def _register_entry_point_cmds(self):
        """
        register commands provided by cad modules
        """
        for ep in pkg_resources.iter_entry_points(group="cs.workspaces.commands"):
            logging.debug("start registering entry point %s", ep.name)
            try:
                processor = ep.load()
                if issubclass(processor, CmdProcessorBase):
                    self._addCommand(processor)
                else:
                    logging.error(
                        "Loading WSCOMMAND %s failed because its a wrong class %s",
                        ep.name,
                        type(processor),
                    )
            except TypeError:
                logging.exception("Loading WSCOMMAND %s failed with exception", ep.name)

    def _initializeAdvancedCommands(self):
        """
        Imports and adds advanced commands
        """
        if not self._commandsInitialized:
            self._commandsInitialized = True
            try:
                from cs.wsm.pkgs.cdbfiletypes import FileTypeProcessor
                from cs.wsm.pkgs.cdbwsmcmdprocessor import CdbWsmCmdProcessor
                from cs.wsm.pkgs.uniquefilenameprocessor import UniqueFilenameProcessor
                from cs.wsm.pkgs.getboforfilenames import GetBoForFilenameProcessor
                from cs.wsm.pkgs.indexrulesprocessor import IndexRulesProcessor
                from cs.wsm.pkgs.getdrwformodels import GetdrwformodelsProcessor
                from cs.wsm.pkgs.pdmpostprocessor import PdmPostProcessor
                from cs.wsm.pkgs.adminsettingsprocessor import AdminSettingsProcessor
                from cs.wsm.pkgs.userrolesprocessor import UserRolesProcessor
                from cs.wsm.pkgs.fastserverrightsprocessor import (
                    FastServerRightsProcessor,
                )
                from cs.wsm.pkgs.findobjectsprocessor import FindObjectsProcessor
                from cs.wsm.pkgs.findexportpartnerprocessor import (
                    FindExportPartnerProcessor,
                )
                from cs.wsm.pkgs.lockcmdprocessor import LockCmdProcessor
                from cs.wsm.pkgs.generateexportnamesprocessor import (
                    GenerateExportNamesProcessor,
                )
                from cs.wsm.pkgs.getexportnamesprocessor import GetExportNamesProcessor
                from cs.wsm.pkgs.saveexportinfoprocessor import SaveExportInfoProcessor
                from cs.wsm.pkgs.findexportsprocessor import FindExportsProcessor
                from cs.wsm.pkgs.variantprocessors import (
                    GetCadVariantTableProcessor,
                    GetDrawingInformationProcessor,
                    GetAttrIdentifierProcessor,
                )
                from cs.wsm.pkgs.postblobdownprocessor import PostBlobDownProcessor
                from cs.wsm.pkgs.setfilenamesprocessor import SetFilenamesProcessor
                from cs.wsm.pkgs.indexversionsprocessor import IndexVersionsProcessor
                from cs.wsm.pkgs.getboattributes import GetBoAttributesProcessor
                from cs.wsm.pkgs.storeblobs import StoreBlobsProcessor
                from cs.wsm.pkgs.navigaterelshiprocessor import NavigateRelshipProcessor
                from cs.wsm.pkgs.office_config_processor import OfficeConfigProcessor
                from cs.wsm.pkgs.objectclassprocessor import ObjectToClass
                from cs.wsm.pkgs.acadpostconnect import AcadPostConnect
                from cs.wsm.pkgs.ucvariantprocessor import GetUCGenericProcessor
                from cs.wsm.pkgs.ucupdatecmd import UCGenericUpdateProcessor
                from cs.wsm.pkgs.ucvarianttable import UCGenericTableUpdateProcessor
                from cs.wsm.pkgs.ucvariantprocessor import (
                    GetUCDrawingInformationProcessor,
                )
                from cs.wsm.pkgs.readcatalogprocessor import ReadCatalogProcessor
                from cs.wsm.pkgs.ucobjectinfos import UCObjectInfos
                from cs.wsm.pkgs.applicationrpc import ApplRpcProcesssor

                cmdprocessors = {
                    FileTypeProcessor,
                    CdbWsmCmdProcessor,
                    GetBoForFilenameProcessor,
                    UniqueFilenameProcessor,
                    IndexRulesProcessor,
                    GetdrwformodelsProcessor,
                    PdmPostProcessor,
                    AdminSettingsProcessor,
                    UserRolesProcessor,
                    FastServerRightsProcessor,
                    FindObjectsProcessor,
                    FindExportPartnerProcessor,
                    LockCmdProcessor,
                    GenerateExportNamesProcessor,
                    GetExportNamesProcessor,
                    SaveExportInfoProcessor,
                    FindExportsProcessor,
                    GetCadVariantTableProcessor,
                    GetDrawingInformationProcessor,
                    GetAttrIdentifierProcessor,
                    PostBlobDownProcessor,
                    SetFilenamesProcessor,
                    IndexVersionsProcessor,
                    GetBoAttributesProcessor,
                    StoreBlobsProcessor,
                    NavigateRelshipProcessor,
                    OfficeConfigProcessor,
                    ObjectToClass,
                    AcadPostConnect,
                    ModifyObjectsProcessor,
                    GetUCGenericProcessor,
                    UCGenericUpdateProcessor,
                    UCGenericTableUpdateProcessor,
                    GetUCDrawingInformationProcessor,
                    UCObjectInfos,
                    ReadCatalogProcessor,
                    ApplRpcProcesssor,
                }
                for cmdprocessor in cmdprocessors:
                    self._addCommand(cmdprocessor)
                self._register_entry_point_cmds()
            except Exception:
                logging.exception(
                    "WsmCommandProcessor failed to import or add commands"
                )

    @timingWrapper
    @timingContext("WSM USEREXIT")
    def process(self, request=None):
        resultStream = CompressStream()

        with measuringPoint("DETAIL PARSEREQUEST"):
            root, returnCode = self._parseInput()

        sqlCount = None

        if root is not None:
            if root.tag == "WSCOMMANDS":
                cmdId = root.attrib.get("cmd")
                if cmdId:
                    cmdClass = self._getCommand(cmdId)
                    if cmdClass is not None:
                        logging.info(
                            "WsmCommandProcessor processing" " command '%s'", cmdId
                        )
                        sqlCountBefore = sqlapi.SQLget_statistics()["statement_count"]

                        # create WSCOMMANDS instance
                        wscommands = xmlTree2Object(root)
                        licOk, licFeatureReply = self._checkLicense(wscommands)
                        if licOk:
                            cmd = cmdClass(wscommands)
                            cmd.setLicReply(licFeatureReply.toXmlTree())
                            with measuringPoint("PROCESSOR %s" % cmdId):
                                returnCode = cmd.call(resultStream, request)

                            sqlCountAfter = sqlapi.SQLget_statistics()[
                                "statement_count"
                            ]
                            sqlCount = sqlCountAfter - sqlCountBefore
                            logging.info(
                                "SQL COUNT for WSD command '%s': %s", cmdId, sqlCount
                            )
                        else:
                            returnCode = WsmCmdErrCodes.licenseCheckFailed
                            xmlStr = licFeatureReply.toEncodedString()
                            resultStream.write(xmlStr)
                    else:
                        returnCode = WsmCmdErrCodes.unknownCommand
                        logging.error("unknown command received: '%s' ", cmdId)
                else:
                    returnCode = WsmCmdErrCodes.invalidCommandRequest
                    logging.error("invalid commandRequest missing cmdId: '%s'", cmdId)
            else:
                returnCode = WsmCmdErrCodes.unknownMessageType
                logging.error(
                    "unknown message type: root element doesn't match "
                    "WSCOMMANDS. root: %s",
                    root.tag,
                )

        resultLines = []
        if returnCode == WsmCmdErrCodes.messageOk and resultStream.equalsLastHash():
            returnCode = None
            resultLines = [SERVER_REPLY_HASH_EQUAL]
        else:
            if six.PY2:
                resultLines = resultStream.lines()
            else:
                for line in resultStream.lines():
                    resultLines.append(line.decode("utf-8"))

            if returnCode == WsmCmdErrCodes.messageOk:
                if sqlCount is not None:
                    wsVersion = rte.environ.get("WS_VERSION")
                    if wsVersion:
                        returnSqlCount = version_greater_equal(wsVersion, "15.5.1")
                        if returnSqlCount:
                            returnCode = six.text_type(returnCode) + u";%s" % sqlCount
                currHash = resultStream.getCurrentHash()
                if currHash is not None:
                    returnCode = six.text_type(returnCode) + u";" + currHash

        return returnCode, resultLines

    def _parseInput(self):
        """
        Consumes the input, decodes and decompresses it, then returns
        the parsed xml root element or None
        """
        root = None
        returnCode = WsmCmdErrCodes.messageOk
        if self._input:
            input_string = six.text_type("").join(self._input)
            decoded = base64.standard_b64decode(input_string)
            del self._input
            logging.debug("length (decoded):%s", len(decoded))
            uncompressed = zlib.decompress(decoded)
            del decoded
            logging.debug("uncompressedLen : %s", len(uncompressed))
            logging.debug("XML-Msg:\n%s", uncompressed)
            try:
                root = ElementTree.fromstring(uncompressed)
            except Exception:
                returnCode = WsmCmdErrCodes.messageNotWellFormed
                logging.exception("error parsing request")
        else:
            returnCode = WsmCmdErrCodes.emptyRequest
            logging.error("empty request")
        return root, returnCode

    def _checkLicense(self, wsCommands):
        """
        check for required license codes
        """
        retCode = True
        if six.PY2:
            sh = hmac.new("AYBABTU")
        else:
            sh = hmac.new("AYBABTU".encode("utf-8"), digestmod=hashlib.md5)
        features = dict()
        logging.info("Entering license check")
        licElement = wsCommands.getFirstChildByName("LIC_FEATURES")
        licFeatureReply = LIC_FEATURE_REPLY()
        if licElement is not None:
            genFeatures = licElement.getChildrenByName("GENERAL_FEATURE")
            if genFeatures:
                for genFeature in genFeatures:
                    featureId = genFeature.feature_id
                    granted = fls.get_license(featureId)
                    if granted:
                        logging.info("License for %s is granted", featureId)
                    else:
                        if genFeature.mandatory == "1":
                            logging.error(
                                "License check for mandatory feature '%s' failed",
                                featureId,
                            )
                            retCode = False
                        else:
                            logging.warning(
                                "License check for '%s' failed (not mandatory)",
                                featureId,
                            )
                    features[featureId] = granted
                    licFeatureReply.addChild(
                        FEATURE_STATUS(
                            feature_id=featureId, granted="1" if granted else "0"
                        )
                    )
            else:
                logging.debug("No genFeatures requested")
        else:
            logging.debug("No Licenserequest found")
        for feature in sorted(features):
            granted = features.get(feature)
            if six.PY2:
                sh.update(feature)
                sh.update(str(int(granted)))
            else:
                sh.update(feature.encode("utf-8"))
                sh.update(str(int(granted)).encode("utf-8"))
        licenseChecksum = sh.hexdigest()
        licFeatureReply.etreeElem.attrib["licensechecksum"] = licenseChecksum
        licFeatureReply.etreeElem.attrib["licenseversion"] = "1"
        logging.info("Leaving license check")
        return retCode, licFeatureReply


class CompressStream(object):
    """
    Compresses and encodes a large string iteratively.

    This class still holds the entire compressed string in memory,
    but it does not require a large contiguous block of memory.

    Use like this:

    s = CompressStream()
    s.write(data1)
    ...
    s.write(dataX)
    ls = s.lines()
    for l in ls:
       # do something with l
       pass
    """

    def __init__(self):
        self._compressObject = zlib.compressobj()
        self._compressedLines = []
        # for reply hash comparison. allows performance
        # optimizations if reply didnt change since last request
        self._hasher = None
        self._compareHash = None
        self._currentHash = None

    def enableHasher(self):
        self._hasher = hashlib.sha1()

    def setCompareHash(self, compareHash):
        self._compareHash = compareHash

    def getCurrentHash(self):
        if self._currentHash is None and self._hasher is not None:
            self._currentHash = self._hasher.hexdigest()
        return self._currentHash

    def equalsLastHash(self):
        equal = False
        if self._compareHash is not None and self._hasher is not None:
            equal = self.getCurrentHash() == self._compareHash
        return equal

    def write(self, bytesToWrite):
        if self._compressObject is None:
            raise ValueError("Trying to write to a closed CompressStream")

        if self._hasher is not None:
            self._hasher.update(bytesToWrite)

        compressed = self._compressObject.compress(bytesToWrite)
        if compressed:
            self._addContent(compressed)

    def _addContent(self, compressed):
        encoded = base64.standard_b64encode(compressed)
        self._compressedLines.append(encoded)

    def lines(self):
        """
        Consume content of the stream.
        Once this has been called, you can no longer write into the stream.

        :return: iterable of byte strings (compressed)
        """
        remaining = self._compressObject.flush()
        self._compressObject = None
        if remaining:
            self._addContent(remaining)

        return self._compressedLines
