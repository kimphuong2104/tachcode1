# -*- mode: python; coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module bolistcommand

Implements getbolist command
"""
from __future__ import absolute_import

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cs.wsm.pkgs.wscommand import WsCommand
from cs.wsm.pkgs.attributesaccessor import ReducedAttributes
from cs.wsm.pkgs.xmlmapper import COMMANDSTATUSLIST
from cs.wsm.pkgs.cdbversion import GetCdbVersionProcessor

from cdb import typeconversion
from cdb import CADDOK
from cdb.objects.cdb_file import CDB_File
from cs.wsm.pkgs.cmdprocessorbase import WsmCmdErrCodes
from cdb import fls


class BoListCommand(WsCommand):
    NAME = "getbolist"

    def __init__(self, request):
        WsCommand.__init__(self, request)
        self._presignedUrlsEnabled = (
            GetCdbVersionProcessor.checkPresignedBlobConfig() == 0
        )
        self._webrequest = None

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

        # simplified xml result, e.g. for getbolist command
        self._simplifiedReply = True

        if self._filterFilename:
            self._reducedAttributes = ReducedAttributes.FILTER_ATTRIBUTES
        else:
            self._reducedAttributes = ReducedAttributes.LEAST_ATTRIBUTES

        self._searchReferrers = self._request.getSearchReferrers()

    def verifyFastBlob(self):
        """
        :return WsmErrorCode
        """
        ret = WsmCmdErrCodes.messageOk
        if self._presignedUrlsEnabled:
            if not fls.get_license("WSM_004"):
                ret = WsmCmdErrCodes.fastBlobLicense
            elif not hasattr(CDB_File, "presigned_blob_url"):
                ret = WsmCmdErrCodes.fastBlobOldServer
        return ret

    def setupCaching(self, webrequest):
        self._webrequest = webrequest
        doRightsChecks = self._forceCheckout
        WsCommand._setupCaching(self, doRightsChecks, extendedCaching=False)

        self._cache.updateObjectHandles = False
        self._cache.setLinkStatusCaching(False)
        self._cache.setFileAttributesCaching(self._ignoreExternalLinks)

        self._performCaching(cacheLockInfos=False)
