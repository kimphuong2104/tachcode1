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
from __future__ import print_function

__docformat__ = "restructuredtext en"

import os.path

import logging
from cdb import sqlapi
from cdb.objects import ByID
from cdb.objects.cdb_file import cdb_file_base

from cs.wsm.srvappinfocache import AppInfoCache
from cs.wsm.srvappinfoparser import AppInfoParser
from cs.wsm.wstable import TableDataRow, RawTable


class FileTypes(object):
    NotComplete = 0
    Directory = 1
    MainFile = 2
    GroupFile = 3
    DerivedFile = 4


class FilenameNotUnique(Exception):
    def __init__(self, filename, directory, docs):
        Exception.__init__(
            self,
            "File '%s' occurs multiple times in directory '%s' (documents: %s)"
            % (filename, directory, ", ".join(docs)),
        )
        self.filename = filename
        self.directory = directory
        self.docs = docs


class FileRecord(TableDataRow):
    """
    Ein Eintrag in der In memory Tabelle fuer ein cdb_file,cdb_folder_item
    """

    keys = [
        "cdb_object_id",
        "cdb_classname",
        "cdb_link",
        "cdb_belongsto",
        "cdb_folder",
        "cdb_wspitem_id",
        "cdbf_object_id",
        "cdbf_name",
        "cdbf_primary",
        "dirname",
        "wsrootdir",
        "filetype",
    ]

    caseInsensitiveKeys = {"cdbf_name", "dirname", "wsrootdir"}

    def __init__(self, ws_object, directory, wsRootDir):
        self.obj = ws_object
        TableDataRow.__init__(self)
        self.attrs = dict()
        aTag = dict()
        for field in self.obj.GetFieldNames():
            aTag[field] = self.obj[field]
        if aTag:
            for key in FileRecord.keys:
                if key == "dirname":
                    self.attrs[key] = directory
                elif key == "filetype":
                    self.attrs[key] = self._getFileType()
                elif key == "wsrootdir":
                    self.attrs[key] = wsRootDir
                elif key == "cdb_link":
                    self.attrs[key] = (
                        aTag.get("cdb_link", None),
                        aTag.get("cdb_link_condition", None),
                    )
                else:
                    self.attrs[key] = aTag.get(key, None)

        self.attributes = aTag  # Die Attribute des CDB_OBJECTS

    def _getFileType(self):
        fType = 0
        if self.obj.cdb_classname == "cdb_folder_item":
            fType = FileTypes.Directory
        elif self.obj.cdb_classname == "cdb_file_record":
            fType = FileTypes.NotComplete
        elif self.obj.cdb_classname == "cdb_file":
            if (
                self.obj.cdbf_derived_from is not None
                and self.obj.cdbf_derived_from != ""
            ):
                fType = FileTypes.DerivedFile
            elif self.obj.cdb_belongsto is not None and self.obj.cdb_belongsto != "":
                fType = FileTypes.GroupFile
            else:
                fType = FileTypes.MainFile
        return fType

    def getFileType(self):
        """
        Abfrage der Art der Datei, Directory,Primaere Datei einer Gruppe,Datei einer Gruppe,
        abgeleitete Datei
        """
        return self.attrs["filetype"]

    def getWsRootDir(self):
        """
        Abfrage des Workspace-Root-Verzeichnisses.

        """
        return self.attrs["wsrootdir"]

    def getObject(self):
        """
        Gibt das Object-Framework-Objekt zurueck
        """
        return self.obj

    def getKeys(self):
        """
        protected  Methode zum zugriff auf die Schluessel des Datensatzes fuer einen Neueintrag
        """
        return self.attrs

    def getRelFilename(self):
        return os.path.join(self.attrs["dirname"], self.attrs["cdbf_name"]).replace(
            "\\", "/"
        )

    def getDirectory(self):
        return self.attrs["dirname"]


class VirtualWorkspace(object):
    """
    This represents a virtual workspace in memory for requesting information
    about existing files and information form appinfo files
    """

    # error codes
    LINKED_ITEM_NOT_FOUND = 1

    def __init__(
        self, businessObject, followReferences=True, errors=None, caseSensitive=True
    ):
        """

        :parameters:
            businessObject: ObjectFrame object
                Dieses Objekt benoetigt eine cdb_object_id und
                eine Eigenschaft WorkspaceItems!

            followReferences: Boolean
                Wenn False, werden die Referenzen des Workspace nicht aufgeloesst

            errors: list
                Hier werden Fehlermeldungen im Format (error code, description) angehaengt,
                wenn Probleme beim Lesen des Workspace auftreten.

            caseSensitive: bool
                How paths are handled in lookup of file records
        """
        if errors is None:
            errors = []
        self._bO = businessObject
        if caseSensitive:
            self._fileTable = RawTable(FileRecord.keys)
        else:
            self._fileTable = RawTable(FileRecord.keys, FileRecord.caseInsensitiveKeys)
        self._visited = set()
        self._loopDetect = set()
        self._followRefsRecursively = True
        self._ignoreExtRefs = False
        self._appinfoParser = AppInfoParser()
        self._appinfoCache = AppInfoCache(self._appinfoParser)
        refreshErrors = self.refreshFromDatabase(
            followReferences, self._followRefsRecursively, self._ignoreExtRefs
        )
        errors.extend(refreshErrors)

    def _insertDirectoryContentIntoTable(
        self, boItems, wsRootDir, path, folderId, followReferences, refsToIgnore, errors
    ):
        followReferencesInSub = followReferences and self._followRefsRecursively
        for obj in boItems:
            if obj.cdb_folder == folderId or (
                folderId == "" and obj.cdb_folder is None
            ):
                if obj.cdb_classname == "cdb_link_item" and followReferences:
                    if obj.cdb_wspitem_id not in refsToIgnore:
                        linkedBo = ByID(obj.cdb_link)
                        if linkedBo is not None:
                            self._insertBoIntoTable(
                                linkedBo, path, followReferencesInSub, errors
                            )
                        else:
                            desc = "<unknown>"
                            originalBo = ByID(obj.cdbf_object_id)
                            if originalBo is not None:
                                if hasattr(originalBo, "titel"):  # Document
                                    desc = originalBo.titel
                                elif hasattr(originalBo, "name"):  # Frame
                                    desc = originalBo.name
                            errors.append(
                                (VirtualWorkspace.LINKED_ITEM_NOT_FOUND, desc)
                            )
                elif obj.cdb_classname == "cdb_folder_item":
                    fRecord = FileRecord(obj, path, wsRootDir)
                    self._fileTable.addRow(fRecord, False)
                    newPath = os.path.join(path, obj.cdbf_name)
                    self._insertDirectoryContentIntoTable(
                        boItems,
                        wsRootDir,
                        newPath,
                        obj.cdb_wspitem_id,
                        followReferences,
                        refsToIgnore,
                        errors,
                    )
                elif obj.cdb_classname == "cdb_file":  # ignore cdb_file_records
                    fRecord = FileRecord(obj, path, wsRootDir)
                    self._fileTable.addRow(fRecord, False)

    def _insertBoIntoTable(self, bo, path, followReferences, errors):
        key = (bo.cdb_object_id, path)
        if bo.cdb_object_id not in self._loopDetect:
            refsToIgnore = set()  # set(cdb_wspitem_id)
            if self._ignoreExtRefs:
                # collect the external references for this bo
                file_attrs_of_bo = sqlapi.RecordSet2(
                    "cdb_file_wsm", condition="cdbf_object_id='%s'" % bo.cdb_object_id
                )
                for file_attrs in file_attrs_of_bo:
                    if file_attrs.is_external_link:
                        refsToIgnore.add(file_attrs.file_wspitem_id)

            self._loopDetect.add(bo.cdb_object_id)
            if key not in self._visited:
                self._visited.add(key)
                wsRootDir = path
                wsItems = cdb_file_base.KeywordQuery(cdbf_object_id=bo.cdb_object_id)
                if wsItems:
                    self._insertDirectoryContentIntoTable(
                        wsItems,
                        wsRootDir,
                        path,
                        "",
                        followReferences,
                        refsToIgnore,
                        errors,
                    )
            self._loopDetect.discard(bo.cdb_object_id)

    def refreshFromDatabase(
        self, followReferences, followRefsRecursively=True, ignoreExtRefs=False
    ):
        """
        Read a workspace from the database.

            ignoreExtRefs: bool
                If true, document references created from external references are ignored
                when following references.

            followReferencesRecursively: bool
                True: considers all objects directly and indirectly linked from businessObjects
                False: only consider directly linked objects
        :returns: errors: list of tuples, see __init__
        """
        self._followRefsRecursively = followRefsRecursively
        self._ignoreExtRefs = ignoreExtRefs
        errors = []
        self._visited = set()
        self._loopDetect.clear()
        self._fileTable.clear()
        self._insertBoIntoTable(self._bO, "", followReferences, errors)
        return errors

    def listdir(self, pathname, fileTypeSet=None):
        """
        list or files in pathnames
        if fileTypeSet is not None only Files that match a FileType in fileTypeSet are returned

        if a file/directory belongs to more than one bobject this function will a return a record for every bobject.
        :returns list of FileRecords

        """
        if pathname != "":
            normp = os.path.normpath(pathname)
        else:
            normp = ""

        if fileTypeSet is not None:
            retList = []
            for fType in fileTypeSet:
                condition = {"dirname": normp, "filetype": fType}
                retList.extend(self._fileTable.searchExact(condition))
        else:
            condition = {"dirname": normp}
            retList = self._fileTable.searchExact(condition)
        return retList

    def isfile(self, pathname):
        """
        Ueberprueft ob es sich bei dem Pfad um eine Datei handelt

        :parameters:
            pathname: string
                filename to check

        :returns: Boolean
        """
        fRecord = self.getFileRecord(pathname)
        return fRecord is not None and fRecord.getFileType() in [
            FileTypes.MainFile,
            FileTypes.DerivedFile,
            FileTypes.GroupFile,
        ]

    def isdir(self, pathname):
        """
        Ueberprueft ob es sich bei dem Pfad um ein Verzeichnis handelt

        :parameters:
            pathname: string
                filename to check


        :returns: Boolean
        """
        fRecord = self.getFileRecord(pathname)
        return fRecord is not None and fRecord.getFileType() == FileTypes.Directory

    def getFileType(self, pathname):
        """
        Gibt den Typ des Dateiobjekte zurueck

        :parameters:
            pathname: string
                filename to check
        :returns: FileTypes Konstante oder None wenn das Objekt nicht existiert
        """
        ret = None
        fRecord = self.getFileRecord(pathname)
        if fRecord is not None:
            ret = fRecord.getFileType()
        return ret

    def getFileRecord(self, pathname, refererDir=None, throwIfNotUnique=False):
        """
        Sucht nach dem Dateinamen nach einem FileRecord.

        Falls refererDir angegeben ist, wird zunaechst lokal in diesem Verzeichnis
        nach einer Datei basename(pathname) gesucht. Nur wenn es diese nicht gibt, wird
        der volle pathname beruecksichtigt.

        :parameters:
            pathname: string
                filename to check
            refererDir: string or None
                directory path of the appinfo where pathname is referred
        :returns None or FileRecord
        """
        d = ""
        b = ""
        if pathname:
            d, b = os.path.split(os.path.normpath(pathname))

        dirsToCheck = []
        if refererDir is not None:
            dirsToCheck.append(refererDir)
        dirsToCheck.append(d)

        ret = None
        for dirToCheck in dirsToCheck:
            conditions = {"dirname": dirToCheck, "cdbf_name": b}
            fileRecords = self._fileTable.searchExact(conditions)
            if fileRecords:
                if len(fileRecords) == 1:
                    ret = fileRecords[0]
                    break
                elif len(fileRecords) > 1:
                    if throwIfNotUnique:
                        docs = [f.getObject().cdbf_object_id for f in fileRecords]
                        raise FilenameNotUnique(b, dirToCheck, docs)
        return ret

    def getGroupFiles(self, pathname):
        """
        Gibt alle Dateien, ausser der Hauptdatei eines DocWsItems (Dateigruppe) zurueck

        :parameters:
            pathname: string or FileRecord
                filename to check


        :returns list of FileRecords
             that belongs to pathname. pathname is included in group if
             inputname is a group file. the primary file doesnt belongs
             to result
        """
        retList = []
        if isinstance(pathname, FileRecord):
            fRecord = pathname
        else:
            fRecord = self.getFileRecord(pathname)
        if fRecord is not None:
            obj = fRecord.getObject()
            wsRootDir = fRecord.getWsRootDir()
            mainItemId = ""
            if obj.cdb_belongsto == "" or obj.cdb_belongsto is None:
                mainItemId = obj.cdb_wspitem_id
            else:
                mainItemId = obj.cdb_belongsto
            condition = {
                "cdbf_object_id": obj.cdbf_object_id,
                "wsrootdir": wsRootDir,
                "cdb_belongsto": mainItemId,
                "filetype": FileTypes.GroupFile,
            }
            retList = self._fileTable.searchExact(condition)
        return retList

    def getAppinfoRecord(self, pathname, ignoreGroupInformation=False):
        """
        searches for appinfo FileRecord of pathname
        :parameters:
              pathname: unicode string or FileRecord
                     relative path in Workspace or FileRecord of Object

              ignoreGroupInformation:  Boolean
                    if true the cdb_belongs_to attribute is ignored and a second request is
                    done with  os.path.splitext(os.path.basename(pathname))0]+".appinfo". This is
                    the format of an 1.1 (2.9.7 Workspacemanager) filename for the appinfo filename in
                    vault.
        """
        appinfoRecord = None
        if isinstance(pathname, FileRecord):
            fRecord = pathname
        else:
            fRecord = self.getFileRecord(pathname)
        if fRecord is not None:
            obj = fRecord.getObject()
            mainItemId = ""
            if obj.cdb_belongsto == "" or obj.cdb_belongsto is None:
                mainItemId = obj.cdb_wspitem_id
                mainFilename = obj.cdbf_name
                mainRecord = fRecord
            else:
                mainItemId = obj.cdb_belongsto
                mainRecord = self.getMainRecord(fRecord)
                if mainRecord is not None:
                    mainFilename = mainRecord.getObject().cdbf_name
                else:
                    mainFilename = None
            logging.info(
                "getAppinfoRecord: mainfilename : %s appinfofilename: %s",
                mainFilename,
                mainFilename + ".appinfo",
            )
            if mainFilename:
                condition = {
                    "cdbf_object_id": obj.cdbf_object_id,
                    "wsrootdir": mainRecord.getWsRootDir(),
                    "cdb_belongsto": mainItemId,
                    "cdbf_name": mainFilename + ".appinfo",
                    "dirname": fRecord.attrs["dirname"],
                    "filetype": FileTypes.GroupFile,
                }
                retList = self._fileTable.searchExact(condition)
                logging.debug("getAppinfoRecord first: len_retlist: %s", len(retList))
                if len(retList) == 1:
                    appinfoRecord = retList[0]
                if len(retList) == 0 and ignoreGroupInformation:
                    mainRoot = os.path.splitext(mainFilename)[0]
                    condition = {
                        "cdbf_object_id": obj.cdbf_object_id,
                        "wsrootdir": mainRecord.getWsRootDir(),
                        "cdbf_name": mainRoot + ".appinfo",
                        "dirname": fRecord.attrs["dirname"],
                    }
                    retList = self._fileTable.searchExact(condition)
                    logging.debug(
                        "getAppinfoRecord second: len_retlist: %s", len(retList)
                    )
                    if len(retList) == 1:
                        appinfoRecord = retList[0]
        return appinfoRecord

    def getMainRecord(self, fileRecord):
        """
        Gibt die Hauptdatei einer Dateigruppe zurueck

        :parameters:
            pathname: FileRecord

        :returns FileRecord or None

        """
        mainRecord = None
        obj = fileRecord.getObject()
        mainItemId = obj.cdb_belongsto
        if mainItemId:
            cdbf_object_id = obj.cdbf_object_id
            condition = {
                "cdb_wspitem_id": mainItemId,
                "wsrootdir": fileRecord.getWsRootDir(),
                "cdbf_object_id": cdbf_object_id,
                "dirname": fileRecord.attrs["dirname"],
            }
            retList = self._fileTable.searchExact(condition)
            if len(retList) == 1:
                mainRecord = retList[0]
        return mainRecord

    def getAllFiles(self, setOfFileTypes, boObjectId=None, boRootPath=None):
        """
        Eine Liste alle FileRecords aus allen Unterverzeichnissen ermitteln.
        Die Sucbedingung kann auf verschiedene Dateitypen (Main,Group)
        sowie auf ein BObject eingeschraenkt werden. Ein BObject ist nur vollstaendig
        beschrieben, wenn auch der Linkpfad (d.h. sein Rootpfad mit angegeben ist).

        :parameters:
            setOfFileTypes: list or set of FileTypes-Constants

            boObjectId: string
                cdb_object_id from businessobject (document, frame,..)
            boRootPath: string
                linking path of businessobject


        :returns : List of FileRecords
        """
        retList = []
        for fType in setOfFileTypes:
            condition = {"filetype": fType}
            if boObjectId is not None and boRootPath is not None:
                condition.update(
                    {"cdbf_object_id": boObjectId, "wsrootdir": boRootPath}
                )
            retList.extend(self._fileTable.searchExact(condition))
        return retList

    def getPrimaryFilesForBo(self, boObjectId, boRootPath=""):
        """
        Abfrage der primaeren Datei(en) fuer ein BoObjetcs

        :parameters:
            boObjectId: string
                cdb_object_id from businessobject (document, frame,..)
            boRootPath: string
                linking path of businessobject

        :returns: list of FileRecords
        """
        condition = {
            "cdbf_object_id": boObjectId,
            "wsrootdir": boRootPath,
            "cdbf_primary": "1",
        }
        return self._fileTable.searchExact(condition)

    def getMainFilesForBo(self, boObjectId, boRootPath=""):
        """ """
        condition = {"cdbf_object_id": boObjectId, "wsrootdir": boRootPath}
        files = self._fileTable.searchExact(condition)
        ret_files = [f for f in files if not f.obj.cdb_belongsto]
        return ret_files

    def getAppinfoTree(self, pathname, raiseOnEmpty=False):
        """
        Laedt die Appinfo-XML-Datei aus dem Blobstore
        und erzeugt Appinfo-Items wie im Workspacemanagers

        :parameters:
            pathname: string or FileRecord
                filename to check


        :returns: wsItemTree of Appinfos or None if no file is present or file is invalid
            or if raiseOnEmpty is False and appinfo file exists with empty root element <appinfo>
        """
        appinfoTree = None
        if isinstance(pathname, FileRecord):
            fRecord = pathname
        else:
            fRecord = self.getFileRecord(pathname)
        if fRecord is not None:
            appinfoTree = self._appinfoCache.getAppinfo(
                fRecord.getObject(), raiseOnEmpty
            )
        return appinfoTree


def test():
    from cs.documents import Document

    # TODO: MAKE UNIT TEST FROM THIS METHOD AND MOVE TO
    #       test_virtualworkspace.py
    #    vW = VirtualWorkspace(doc,True)
    #    print len(vW._fileTable)
    #    for fRecord in vW.listdir("",None):
    #        print fRecord.attrs
    #    print "Anzahl Dirs:%s" % len(vW.listdir("",set([FileTypes.Directory])))
    #    print vW.isfile("000045-1-.asm")
    #
    doc = Document.ByKeys("000000-12", "")
    vW = VirtualWorkspace(doc, True)
    print("Anzahl Dirs:%s" % len(vW.listdir("", set([FileTypes.Directory]))))
    for d in vW.listdir("", set([FileTypes.Directory])):
        print(d.getObject().cdbf_name, d.getObject().cdbf_object_id)
    print(vW.isdir("normteile/din_a"))
    print(vW.isdir("normteile/din_a/norm_din_a.CATPart"))
    print(vW.isfile("normteile/din_a/norm_din_a.CATPart"))
    for f in vW.getGroupFiles("normteile/din_a/norm_din_a.CATPart"):
        print(f.getObject().cdbf_name, f.attrs)
    appinfoRecord = vW.getAppinfoRecord("normteile/din_a/norm_din_a.CATPart")
    print("Appinfo: %s " % appinfoRecord.attrs["cdbf_name"])
    appinfoTree = vW.getAppinfoTree(appinfoRecord)
    print("AppinfoTree: %s" % appinfoTree)

    appinfoTree = vW.getAppinfoTree("normteile/din_a/norm_din_a.CATPart.appinfo")
    print("AppinfoTree by name: %s" % appinfoTree)

    mainRecord = vW.getMainRecord(appinfoRecord)
    print("MainRecord: %s " % mainRecord.attrs["cdbf_name"])

    mainFiles = vW.getAllFiles([FileTypes.MainFile])
    print("MainFilelist")
    for f in mainFiles:
        print(os.path.join(f.attrs["dirname"], f.attrs["cdbf_name"]))
    for f in vW.getPrimaryFilesForBo(doc.cdb_object_id, ""):
        print("Primary File: %s" % f.attrs["cdbf_name"])

    print("MainFiles for Doc")
    mainFiles = vW.getAllFiles([FileTypes.MainFile], doc.cdb_object_id, "")
    for f in mainFiles:
        print(os.path.join(f.attrs["dirname"], f.attrs["cdbf_name"]))

    vW = VirtualWorkspace(doc, False)
    mainFiles = vW.getAllFiles([FileTypes.MainFile])
    print("MainFilelist keine Referenzen")
    for f in mainFiles:
        print(os.path.join(f.attrs["dirname"], f.attrs["cdbf_name"]))

    frame = ByID("3463a2c4-1f2d-4016-a630-7212410f04f9")
    vW = VirtualWorkspace(frame, False)
    vW.listdir("")
