#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     pdmpostprocessor.py
# Author:   dti
# Creation: 19.03.2013
# Purpose:


"""
Module pdmpostprocessor.py

Processor for concluding actions
"""
from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import six
import traceback
import logging
from collections import defaultdict

from cdb.sig import emit
from cdb import dberrors, sqlapi

from cs.documents import Document, DocumentReference
from cs.vp.cad import CADVariant
from cs.wsm.pkgs.pkgsutils import grouper

csDocumentsSupportsMultiSheet = False
try:
    from cs.documents import SheetReference  # @UnusedImport

    csDocumentsSupportsMultiSheet = True
    from cs.wsm.pkgs.multiple_sheets_handling import sync_sheets
except ImportError:
    logging.info(
        u"The installed version of cs.documents does not support "
        u"management of multiple sheets per drawing in the PDM "
        u"system. To use this feature, a more recent version "
        u"of cs.documents has to be installed."
    )

from cs.wsm.cadknowledge import (
    Appl2OccurrenceReltypes,
    getApplByClientName,
    WSM_RELTYPE,
    ApplWritesTNummer2,
)
from cs.wsm.result import Result, Error, ResultType

from cs.wsm.pkgs.xmlmapper import (
    WSCOMMANDRESULT,
    COMMANDSTATUSLIST,
    COMMANDSTATUS,
    INFO,
    ERROR,
)
from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes
from cs.wsm.pkgs.cad_variants import syncCadVariants
from cs.wsm.pkgs.servertimingwrapper import timingWrapper, timingContext
from cs.wsm.pkgs.pkgsutils import null2EmptyString
from cs.wsm.wsobjectcache import MAX_IN_ELEMENTS, MAX_PAIRS, WsObjectCache


def _getCdbLinkValue(_doc):
    # we are not able to calculate cdb_link effectively
    # to decide whether cdb_link is 1 we need to open
    # and analyse links inside of appinfo files which
    # could be very expensive in particular cases
    return 0


def _getLogischerNameValue(erzeug_system):
    return "Master" if erzeug_system.startswith("ProE") else ""


class DummyContext:
    action = "wsmcommit"
    mode = "post"


class PdmPostProcessor(CmdProcessorBase):
    name = u"pdmpostprocessing"

    def __init__(self, rootElement):
        CmdProcessorBase.__init__(self, rootElement)
        self._cache = WsObjectCache(simplifiedRightsCheck=True, doRightsCheck=False)
        self._cache.setUpdateObjectHandles(False)

    def call(self, resultStream, request):
        """
        Collects given ids and emits wsm_commit_finished
        signal with collected ids as parameter
        """
        self._storeVariants = self._rootElement.store_variants_on_server == "1"
        self._combineModelLayout = self._rootElement.combine_model_layout == "1"

        contextObjs = self._rootElement.getChildrenByName("WSCOMMANDS_CONTEXTOBJECT")
        objIds = []
        for contextObj in contextObjs:
            # get the ids of context objects
            objIds.append(contextObj.cdb_object_id)

        self._cache.prefetchObjects(objIds, alsoFetchLinkedObjects=False)

        results = self.postProcess(objIds)

        wsCmdResult = WSCOMMANDRESULT(primary_object="")
        statusList = COMMANDSTATUSLIST()
        wsCmdResult.addChild(statusList)

        for objId, result in results:
            commandStatus = resultToCommandStatus(objId, result)
            statusList.addChild(commandStatus)

        xmlStr = wsCmdResult.toEncodedString()
        resultStream.write(xmlStr)

        return WsmCmdErrCodes.messageOk

    def _cacheVariants(self, docs):
        """
        Efficiently collect all CAD variants of the given documents.
        :return: dict((z_nummer, z_index) -> CADVariant)
        """
        variantsByDocKeys = defaultdict(list)
        for chunk in grouper(MAX_PAIRS, docs):
            conds = []
            for doc in chunk:
                conds.append(
                    "z_nummer='%s' AND z_index='%s'"
                    % (sqlapi.quote(doc.z_nummer), sqlapi.quote(doc.z_index))
                )
            condition = " OR ".join(conds)
            queryResult = CADVariant.Query(condition=condition, lazy=0)
            for variant in queryResult:
                variantsByDocKeys[(variant.z_nummer, variant.z_index)].append(variant)
        return variantsByDocKeys

    def postProcess(self, objIds):
        objects = self._cache.getObjectsByID(objIds)
        docs = []
        docIds = []
        for obj in objects:
            if isinstance(obj, Document):
                docs.append(obj)
                docIds.append(obj.cdb_object_id)

        self._setCdbDocRelForClassicIntegrations(docs)
        self.updateLocks(docs)

        ueContext = DummyContext()

        if self._storeVariants:
            variants = self._cacheVariants(docs)

        for obj in docs:
            try:
                result = Result()

                files = self._cache.workspaceItemsOf(obj.cdb_object_id)
                if self._storeVariants:
                    docVariants = variants[(obj.z_nummer, obj.z_index)]
                    result += syncCadVariants(obj, files, docVariants)
                if csDocumentsSupportsMultiSheet:
                    # always sync the sheets since we have
                    # a flag to recognize main sheets fast
                    result += sync_sheets(obj, self._combineModelLayout, files)

                results = emit(type(obj), "wsmcommit", "post")(obj, ueContext)

                results = [r for r in results if r is not None]
                result += sum(results, Result())
                yield (obj.cdb_object_id, result)
            except Exception:
                logging.exception(
                    u'Server exception in "wsmcommit" user exit, '
                    u'running for object "%s".',
                    obj.cdb_object_id,
                )
                r = Error(
                    u'Server exception in "wsmcommit" user exit, '
                    'running for object "%s". \n\n'
                    "Details: %s" % (obj.cdb_object_id, traceback.format_exc())
                )
                yield (obj.cdb_object_id, r)

        if docIds:
            try:
                results = emit(Document, list, "wsmcommit", "post")(docIds, ueContext)
                yield ("all", sum([r for r in results if r is not None], Result()))
            except Exception:
                logging.exception(
                    u'Server exception in "wsmcommit" user exit, '
                    u'running for objects "%s".',
                    docIds,
                )
                r = Error(
                    u'Server exception in "wsmcommit" user exit, '
                    u'running for objects "%s". \n\n'
                    u"Details: %s" % (docIds, traceback.format_exc())
                )
                yield ("all", r)

    @timingWrapper
    @timingContext("PDMPOSTPROCESSOR setCdbDocRelForClassicIntegrations")
    def _setCdbDocRelForClassicIntegrations(self, docs):
        """
        check whether this document is cad_document
        fetch documents cdb_doc_rel records
        get erzeug_system and write reltype of cdb_doc_rel
        fill cdb_link of cdb_doc_rel if needed

        :param docs: list of Document
        """
        try:
            keys2doc = {}
            for doc in docs:
                if doc.wsm_is_cad == "1":
                    appl = getApplByClientName(doc.erzeug_system)
                    occurrenceReltypes = Appl2OccurrenceReltypes.get(appl)
                    if occurrenceReltypes and len(occurrenceReltypes):
                        keys2doc[(doc.z_nummer, doc.z_index)] = doc

                    else:
                        logging.info(
                            u"PostCommitProcessor._setCdbDocRelForClassicIntegrations:"
                            u" not supported application found while"
                            u" updating cdb_doc_rel for classic integrations:"
                            u" application: %s, z_nummer: %s, z_index: %s",
                            appl,
                            doc.z_nummer,
                            doc.z_index,
                        )
                else:
                    logging.debug(
                        u"PostCommitProcessor._setCdbDocRelForClassicIntegrations:"
                        u" wsm_is_cad not set for document: z_nummer: %s, z_index: %s",
                        doc.z_nummer,
                        doc.z_index,
                    )

            if keys2doc:
                docRelRecs = []
                # for 500 max elements with a length of 10 for both teilenummer and t_index
                # the condition takes around 27.500 chars
                entries = defaultdict(list)
                for chunk in grouper(MAX_PAIRS, six.iterkeys(keys2doc)):
                    condition = u""
                    conds = []
                    for z_nummer, z_index in chunk:
                        conds.append(
                            "z_nummer='%s' AND z_index='%s'"
                            % (sqlapi.quote(z_nummer), sqlapi.quote(z_index))
                        )
                    condition = " OR ".join(conds)
                    # not lazy avoids a COUNT statement caused by the following list.extend
                    queryResult = DocumentReference.Query(condition=condition, lazy=0)
                    for rec in queryResult:
                        entries[
                            (rec.z_nummer, rec.z_index, rec.z_nummer2, rec.z_index2)
                        ].append(rec)
                for docRelRecs in entries.values():
                    # we need exactly one entry per z_nummmer tuple
                    # delete the rest
                    if len(docRelRecs) > 1:
                        logging.info(
                            "Multiple cdb_doc_rel entries found. "
                            "Deleting not necessary entries."
                        )
                    for rec in docRelRecs[1:]:
                        rec.Delete()
                    # and now fix the values from first entry
                    # for classic integration
                    docRelRec = docRelRecs[0]
                    doc = keys2doc[(docRelRec.z_nummer, docRelRec.z_index)]
                    t_nummer2 = docRelRec.t_nummer2
                    t_index2 = docRelRec.t_index2

                    erzeug_system = doc.erzeug_system
                    appl = getApplByClientName(erzeug_system)
                    if appl in ApplWritesTNummer2:
                        dst = docRelRec.ReferencedDocument
                        if dst is not None:
                            t_nummer2 = null2EmptyString(dst.teilenummer)
                            t_index2 = null2EmptyString(dst.t_index)

                    occurrenceReltypes = Appl2OccurrenceReltypes.get(appl)
                    reltype = occurrenceReltypes[0]
                    cdb_link = _getCdbLinkValue(doc)
                    logischer_name = _getLogischerNameValue(erzeug_system)
                    if (
                        docRelRec.reltype != reltype
                        or docRelRec.owner_application != WSM_RELTYPE
                        or docRelRec.cdb_link != cdb_link
                        or docRelRec.logischer_name != logischer_name
                        or docRelRec.t_nummer2 != t_nummer2
                        or docRelRec.t_index2 != t_index2
                    ):
                        docRelRec.Update(
                            reltype=reltype,
                            owner_application=WSM_RELTYPE,
                            cdb_link=cdb_link,
                            logischer_name=logischer_name,
                            t_nummer2=t_nummer2,
                            t_index2=t_index2,
                        )

        except Exception:
            logging.exception(
                u"PostCommitProcessor._setCdbDocRelForClassicIntegrations:"
                u" exception occurred while updating cdb_doc_rel"
                u" for classic integrations:"
            )

    @timingWrapper
    @timingContext("PDMPOSTPROCESSOR updateLocks")
    def updateLocks(self, docs):
        try:
            cdb_locks = defaultdict(list)
            for doc in docs:
                files = self._cache.workspaceItemsOf(doc.cdb_object_id)
                for f in files:
                    if f.cdbf_primary == "1":
                        cdb_locks[f.cdbf_object_id].append(f.cdb_lock)

            lock2doc = defaultdict(list)
            removeLock = []
            for doc in docs:
                objId = doc.cdb_object_id
                locks = cdb_locks.get(objId)
                if locks and any(locks):
                    # just take the first
                    for lock in locks:
                        if lock:
                            if doc.cdb_lock != lock:
                                lock2doc[lock].append(objId)
                            break
                else:
                    # nothing locked or no primary files
                    if doc.cdb_lock:
                        removeLock.append(objId)

            stmt = "zeichnung SET cdb_lock='%s' WHERE cdb_object_id IN (%s)"
            for chunk in grouper(MAX_IN_ELEMENTS, removeLock):
                valueString = u",".join(
                    u"'" + sqlapi.quote(val) + u"'" for val in chunk
                )
                sqlapi.SQLupdate(stmt % ("", valueString))

            for lockId, docIds in six.iteritems(lock2doc):
                for chunk in grouper(MAX_IN_ELEMENTS, docIds):
                    valueString = u",".join(
                        u"'" + sqlapi.quote(val) + u"'" for val in chunk
                    )
                    sqlapi.SQLupdate(stmt % (sqlapi.quote(lockId), valueString))

        except Exception:
            logging.exception(
                u"PostCommitProcessor.updateLocks:"
                u" exception occurred while updating locks:"
            )


def resultToCommandStatus(objId, result):
    """
    :param objId: a cdb object id
    :param result: cs.wsm.result.Result
    :return: COMMANDSTATUS
    """
    if result.isOk():
        status = "info" if result.hasMessages() else "ok"
    else:
        status = "error"
    commandStatus = COMMANDSTATUS(cdb_object_id=objId, value=status)
    for message in result:
        if message.resultType == ResultType.Error:
            child = ERROR(msg=message.text)
        else:
            child = INFO(msg=message.text)
        commandStatus.addChild(child)
    return commandStatus
