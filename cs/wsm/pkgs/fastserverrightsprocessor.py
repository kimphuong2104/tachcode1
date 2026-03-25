#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from __future__ import absolute_import
from lxml import etree
import logging

from cdb.i18n import default
from cdb.objects import NULL
from cs.wsm.wsobjectcache import WsObjectCache

from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes
from cs.wsm.pkgs.servertimingwrapper import timingWrapper, timingContext

import six


class FastServerRightsProcessor(CmdProcessorBase):
    """
    Creates a partial server status of known objects
    which only contains the rights of documents and primary files as well
    as the lock information of primary files.
    ("primary" in the Workspaces meaning, not the CDB meaning)

    This reply can be calculated much faster than a full server status.
    This processor assumes that the simplified rights check is active,
    i.e. file rights are derived from document rights.
    """

    name = u"fastserverrights"

    @timingWrapper
    @timingContext("FASTSERVERRIGHTS")
    def call(self, resultStream, request):
        coids = self._parseInput()
        if coids is None:
            return WsmCmdErrCodes.invalidCommandRequest

        lang = self._rootElement.lang or default()
        wsId = self._rootElement.ws_id or None

        self._writeReply(coids, resultStream, lang, wsId)

        return WsmCmdErrCodes.messageOk

    def _parseInput(self):
        res = None
        contexts = self._rootElement.getChildrenByName("WSCOMMANDS_CONTEXTOBJECT")
        if len(contexts) > 0:
            res = []
            for context in contexts:
                res.append(context.cdb_object_id)
        return res

    def _writeReply(self, coids, resultStream, lang, wsId):
        cache = WsObjectCache(simplifiedRightsCheck=True, lang=lang, workspaceId=wsId)
        logging.info("FastServerRightsProcessor: retrieving access rights and status")
        rights, status = cache.getCdbObjectRightsAndStatusTextByID(coids)
        logging.info("FastServerRightsProcessor: retrieving lock info")
        wsLockId = self._rootElement.wsplock_id
        lockInfos = cache.getLockInfoOfNonDerivedFiles(coids, wsLockId)

        logging.info("FastServerRightsProcessor: building reply")
        root = etree.Element("WSCOMMANDRESULT")
        for coid in coids:
            contextObject = etree.Element(
                "WSCOMMANDS_CONTEXTOBJECT", {"cdb_object_id": coid}
            )
            root.append(contextObject)

            objRights = rights.get(coid)
            if objRights:
                wsmObjectRights = cache.mapToWsmObjectRights(objRights)
                wsmObjectRights = {
                    k: six.text_type(v) for k, v in six.iteritems(wsmObjectRights)
                }
                r = etree.Element("RIGHTS", wsmObjectRights)
                contextObject.append(r)

            objStatus = status.get(coid)
            if objStatus is not None:
                status_txt = objStatus[1] or u""
                status_value = objStatus[3]
                if status_value is None or status_value is NULL:
                    status_value = u""
                else:
                    status_value = u"%s" % status_value
                s = etree.Element(
                    "STATUS",
                    {
                        "status_txt_name": objStatus[0],
                        "status_txt_value": status_txt,
                        "status_name": objStatus[2],
                        "status_value": status_value,
                    },
                )
                contextObject.append(s)

            objLockInfo = lockInfos.get(coid)
            if objLockInfo:
                if not objRights:
                    logging.error(
                        "FastServerRightsProcessor: skipping files without object (cdb_object_id of object: %s)",
                        coid,
                    )
                else:
                    wsmFileRights = cache.mapToWsmFileRights(objRights)
                    wsmFileRights = {
                        k: u"%s" % v for k, v in six.iteritems(wsmFileRights)
                    }

                    for fileCoid, fileLockInfo in six.iteritems(objLockInfo):
                        commandObject = etree.Element(
                            "WSCOMMANDS_OBJECT",
                            {"cdb_classname": "cdb_file", "cdb_object_id": fileCoid},
                        )
                        contextObject.append(commandObject)
                        attrs = {}
                        for attr in [
                            "status",
                            "locker",
                            "status_teamspace",
                            "locker_teamspace",
                        ]:
                            value = fileLockInfo.get(attr, None)
                            if value is not None:
                                attrs[attr] = value
                        lockInfo = etree.Element("LOCKINFO", attrs)
                        commandObject.append(lockInfo)
                        r = etree.Element("RIGHTS", wsmFileRights)
                        commandObject.append(r)

        replyString = etree.tostring(root, encoding="utf-8")
        resultStream.write(replyString)
