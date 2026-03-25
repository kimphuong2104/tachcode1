# -*- mode: python; coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module checkoutcommand

Implements checkout command
"""
from __future__ import absolute_import

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import typeconversion
from cdb import CADDOK

from cs.wsm.pkgs.wscommand import WsCommand
from cs.wsm.pkgs.xmlmapper import COMMANDSTATUSLIST
from cs.wsm.pkgs.cdbversion import GetCdbVersionProcessor


class CheckoutCommand(WsCommand):
    NAME = "checkout"

    def __init__(self, request):
        WsCommand.__init__(self, request)
        self._presignedUrlsEnabled = False
        self._webrequest = None

    def setupCaching(self, webrequest=None):
        self._webrequest = webrequest
        if not self._isStatusRequest:
            self._presignedUrlsEnabled = (
                GetCdbVersionProcessor.checkPresignedBlobConfig() == 0
            )

        WsCommand._setupCaching(self)

        if self._presignedUrlsEnabled:
            # this feature needs a cdb object
            self._cache.limitedFileAttrs = None
        self._performCaching()

    def executeCommand(self):
        cmd = self._request.getFirstChildByName("COMMAND")

        for wsCmdContextObj in self._contextObjs:
            cntxCdbObjectId = wsCmdContextObj.cdb_object_id

            # backward compatibility. Use first elem, its the same for all elements.
            if cmd is None:
                cmd = wsCmdContextObj.getFirstChildByName("COMMAND")

            self._contextStatusDict[cntxCdbObjectId] = COMMANDSTATUSLIST()
            self._addCtxObjectCmdStatus(cntxCdbObjectId, "ok")

        if cmd is not None:
            self._readIgnoreLinkParams(cmd)

            commandAttributes = cmd.getObjectAttributes()
            if commandAttributes:
                checkoutRecords = commandAttributes.get("checkout_records", None)
                if checkoutRecords:
                    self._skipRecordsWhileCheckout = checkoutRecords == "no"

                withBomAttr = commandAttributes.get("with_bom", None)
                if withBomAttr is not None:
                    self._withBom = withBomAttr == "yes"

                isStatusRequest = commandAttributes.get("is_status_request", None)
                if isStatusRequest is not None:
                    self._isStatusRequest = isStatusRequest == "yes"

                replyHash = commandAttributes.get("get_reply_hash", None)
                self._getReplyHash = replyHash == "yes"

                lastReplyHash = commandAttributes.get("last_reply_hash", None)
                if lastReplyHash is not None:
                    self._lastReplyHash = lastReplyHash

    def generateReply(self):
        self._setupXmlGenerator()
        if self._presignedUrlsEnabled:
            self._xmlGenerator.attrCollector.setPresignedBlobsEnabled(True)
        self._generateReply()
