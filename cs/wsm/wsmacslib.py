#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# Revision: "$Id$"
#

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import collections
import os
import logging

import six

from cdb.sig import emit
from cdb.objects.pdd.Files import DuplicateFilenameError

from cs.wsm.wsobjectcache import WsObjectCache
from cs.wsm.index_helper import getIndexes
from cs.wsm.virtualworkspace import VirtualWorkspace, FileTypes
from cs.documents import Document
from cs.platform.cad import Frame


def _getDrawingOfSheet(sheetDoc):
    """
    :return Document: The Document containing the drawing file for the sheet document
    """
    drawingDoc = sheetDoc
    for sref in sheetDoc.DrawingOfSheetReferences:
        if sref.z_index == sref.z_index_origin:
            drawingDoc = sref.Drawing
    return drawingDoc


def _checkoutDoc(sb, doc, basedir, use_subdir_for_appinfo, checkout_files):
    fpathlist = []
    docVw = VirtualWorkspace(doc, followReferences=False)
    for docFile in docVw.getAllFiles([FileTypes.MainFile]):
        relFilename = docFile.getRelFilename()
        # main file
        dp = os.path.join(basedir, relFilename)
        doCheckout = True
        if sb is not None:
            doCheckout = os.path.join(sb.location, dp) not in checkout_files
            if doCheckout:
                f = docFile.getObject()
                fs_path_name = sb.checkout_to_path(f, dp)
                fpathlist.append(fs_path_name)
                checkout_files.add(fs_path_name)
        else:
            doCheckout = dp not in checkout_files
            if doCheckout:
                fpathlist.append(dp)
                checkout_files.add(dp)
        if doCheckout:
            # appinfo
            appinfoRecord = docVw.getAppinfoRecord(relFilename)
            for vwgf in docVw.getGroupFiles(relFilename):
                # move appinfo to correct directory
                if vwgf == appinfoRecord and use_subdir_for_appinfo:
                    dname = vwgf.getDirectory()
                    bname = vwgf.attrs["cdbf_name"]
                    dp = os.path.join(basedir, dname, ".wsm", ".info", bname)
                else:
                    dp = os.path.join(basedir, vwgf.getRelFilename())
                if sb is not None:
                    if os.path.join(sb.location, dp) not in checkout_files:
                        fs_path_name = sb.checkout_to_path(vwgf.getObject(), dp)
                        fpathlist.append(fs_path_name)
                        checkout_files.add(fs_path_name)
                else:
                    if dp not in checkout_files:
                        fpathlist.append(dp)
                        checkout_files.add(dp)
    return fpathlist


def checkout_workspace(
    sb, mainDoc, ignore_duplicates=False, use_subdir_for_appinfo=False, result=None
):
    r"""
    :param sb: Sandbox or None
    :param mainDoc: Document
    :param ignore_duplicates: Boolean
        ignores files that belongs to different z_nummmer. The used
        documents is random.

    :param use_subdir_for_appinfo: Boolean
        For compatibility reasons. Classic plugins expect .appinfos in workdir,
        Plugins based on JobExecs and cad commands are using subdirs.

    :param result: optional dict to reuse for result. Dict Document to list of filenames

    :returns result dict dict Document to list of filename

    Checkout workspace in "as saved mode" like the WSM.

    If two documents instances are containing the filename
    DuplicateFilenameError will be raised if the documents don't
    have an equal z_nummer. In this case the maximum index of
    all  documents with equal z_nummer and a filename conflict
    will be used.
    The Index of the mainDoc will not be changed by ths function.
    In case of cyclic references with newer index versions the
    index from mainDoc will be used.

    If sb is None: no files will copied to disk. The returned filenames
    are relative in this case. With a given Sandbox the filenames are absolute.

    This method handle sheets document types.
    If more than one drawing references a sheet the default
    implementation will use the origin document.

    It's possible to overwrite the behaviour by connection
    to "getdrawingofsheet" signal. The function must
    accept the sheet Document as a parameter and must
    return the drawing Doc.

    Appinfo files will be written to .wsm/.info directory relative
    to the main file of a file group.

    Missing link documents are ignored by this function.

    Example usage:
    # simple testcall
    from cs.documents import Document
    import shutil
    from cdb.objects.cdb_file import CDB_File
    from cdb.objects.pdd.Files import Sandbox

    r = dict()
    wdir = u"C:\\temp\work\\"
    if os.path.isdir(wdir):
        shutil.rmtree(wdir)
    doc = Document.ByKeys("W000000","")
    sb = Sandbox(wdir)
    print checkout_workspace(sb, doc, True, result=r)
    sb.close()
    """
    # handle the case: mainDoc is a sheet
    if "additional_document_type" in mainDoc.keys():
        # 0 = no multisheet
        # 1 = multisheet master
        # 2 = multisheet sheet
        if mainDoc.additional_document_type == "2":
            drawingDocs = emit("getdrawingofsheet")(mainDoc)
            if drawingDocs:
                mainDoc = drawingDocs[0]
            else:
                drawingDoc = _getDrawingOfSheet(mainDoc)
                if drawingDoc is not None:
                    mainDoc = drawingDoc

    if result is None:
        result = dict()

    # collect all files reachable from mainDoc and remember their doc(s)
    eList = list()
    filenames = collections.defaultdict(
        list
    )  # filenames to list of (doc.cdb_object_ids, rootdir)
    vw = VirtualWorkspace(mainDoc, followReferences=True, errors=eList)
    vwFiles = vw.getAllFiles([FileTypes.MainFile])
    for vwFile in vwFiles:
        if vwFile.attrs["cdbf_object_id"] != mainDoc.cdb_object_id:
            filenames[vwFile.getRelFilename()].append(
                (vwFile.attrs["cdbf_object_id"], vwFile.attrs["wsrootdir"])
            )
    # make sure all affected documents are in the cache
    docObjIds = set()
    docObjIds.add(mainDoc.cdb_object_id)
    for objidsRootDir in six.itervalues(filenames):
        docObjIds.update([o[0] for o in objidsRootDir])
    wsCache = WsObjectCache(True)
    _docObjects = wsCache.getObjectsByID(list(docObjIds), False)
    objsToCheckOut = set()  # of tuples (document, rootDir)
    mainFilenames = []

    mainPrim = vw.getMainFilesForBo(mainDoc.cdb_object_id)
    for f in mainPrim:
        mainFilenames.append(f.getRelFilename())
    # check for conflicts find max index
    checkout_files = set()
    for fname, fobjectsAndDir in six.iteritems(filenames):
        if fname in mainFilenames:
            if ignore_duplicates:
                # always prefer files of the mainDoc
                continue
            else:
                cdb_object_ids = [mainDoc.cdb_object_id] + [
                    wsCache.getCachedObject(fO[0]).cdb_object_id
                    for fO in fobjectsAndDir
                ]
                raise DuplicateFilenameError(
                    "Duplicate name: %s, cdb_object_ids: %s"
                    % (fname, ",".join(cdb_object_ids))
                )

        # more than one business object for this file => there is a conflict
        if len(fobjectsAndDir) > 1:
            version_independent_keys = set()  # for docs, these are z_nummers
            indexDocs = list()
            for fobjidRootDir in fobjectsAndDir:
                bo = wsCache.getCachedObject(fobjidRootDir[0])
                if isinstance(bo, Document):
                    indexDocs.append(bo)
                    version_independent_keys.add(bo.z_nummer)
                elif isinstance(bo, Frame):
                    version_independent_keys.add((bo.name, bo.rahmen_gruppe))
                else:
                    logging.error(
                        "checkout_workspace: ignoring business object of unknown type: %s",
                        bo,
                    )
            # more than one (version-independent) bo for this file
            if len(version_independent_keys) > 1:
                # if duplicates are allowed, just use the first bo
                if ignore_duplicates:
                    fobjidRootDir = fobjectsAndDir[0]
                    objsToCheckOut.add(
                        (
                            fname,
                            wsCache.getCachedObject(fobjidRootDir[0]),
                            fobjidRootDir[1],
                        )
                    )
                else:
                    raise DuplicateFilenameError(
                        "Duplicate name: %s, numbers: %s"
                        % (fname, ",".join(map(str, version_independent_keys)))
                    )
            else:
                # only one (version-independent) bo:
                # manage index conflicts for docs, find the highest index
                maxIndex = -1
                maxDoc = None
                for doc in indexDocs:
                    # simple and hopefully fast enough, otherwise one call and compare the object_ids
                    _, _, myIndex = getIndexes(doc)
                    if myIndex > maxIndex:
                        maxDoc = doc
                        maxIndex = myIndex
                if maxDoc:
                    # Root dir never changes
                    objsToCheckOut.add((fname, maxDoc, fobjectsAndDir[0][1]))
        else:
            # simple case: no conflict
            objsToCheckOut.add(
                (
                    fname,
                    wsCache.getCachedObject(fobjectsAndDir[0][0]),
                    fobjectsAndDir[0][1],
                )
            )

    # now checkout all files to the root directories. We checkout every document
    # to the destination dictory als single wirtual workspaces
    visitedDocs = set()  # set of tuples. (doc, basedir)

    # checkout mainDoc first this always has priority
    visitedDocs.add((mainDoc, ""))
    fpathlist = _checkoutDoc(sb, mainDoc, "", use_subdir_for_appinfo, checkout_files)
    result[mainDoc] = fpathlist
    for _fname, doc, basedir in objsToCheckOut:
        visitedKey = (doc, basedir)
        if visitedKey not in visitedDocs:
            visitedDocs.add(visitedKey)
            fpathlist = _checkoutDoc(
                sb, doc, basedir, use_subdir_for_appinfo, checkout_files
            )
            existingPList = result.get(doc)
            # if we have multiple instances of a document just extend the list
            if existingPList is None:
                existingPList = []
                result[doc] = existingPList
            existingPList.extend(fpathlist)
    return result
