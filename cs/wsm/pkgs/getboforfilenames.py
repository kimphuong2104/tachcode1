#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2010 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Module getboforfilenames

Search matching documents for given filenames
"""
from __future__ import absolute_import

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


# Exported objects
__all__ = []

import os
import logging
from collections import defaultdict

from lxml.etree import Element
from lxml import etree as ElementTree

from cdb import sqlapi
from cdb.objects import ByID, NULL
from cdb.objects.cdb_file import cdb_folder_item
from cdb.platform.mom import getObjectHandlesFromObjectIDs

from cs.wsm.index_helper import getIndexes
from cs.wsm.wsobjectcache import WsObjectCache, getDocumentsById, MAX_PAIRS

from cs.wsm.pkgs.cdbobj2xml import buildElementWithAttributes
from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase
from cs.wsm.pkgs.xmlmapper import ATTRIBUTES
from cs.wsm.pkgs.attributesaccessor import AttributesCollector, ReducedAttributes
from cs.wsm.pkgs.pkgsutils import getCdbClassname, getRelPath


import six

if not six.PY2:
    import functools


class GetBoForFilenameProcessor(CmdProcessorBase):
    name = u"getboforfilenames"

    def __init__(self, rootElement):
        CmdProcessorBase.__init__(self, rootElement)
        self._dirnameBoCache = {}  # dname_boid->valid
        self._boFolderCache = {}  # boId->cdb_cdb_folder_items
        self._name2files = defaultdict(list)
        self._origName2files = defaultdict(list)
        self._docs = {}
        self.assignOnlyAnchorFile = False
        self.wsmWorkspaceClass = None
        self.useOriginalFileName = False
        self._requestedDocAttributes = None
        self.indexRule = self._rootElement.index_load_rule
        self.lang = self._rootElement.lang
        self._wsObjectCache = WsObjectCache(simplifiedRightsCheck=True)

    def _clearCache(self):
        self._dirnameBoCache.clear()
        self._boFolderCache = {}
        self._name2files.clear()
        self._origName2files.clear()
        self._docs.clear()

    def call(self, resultStream, request):
        """
        Needs xml-rquest:
        <WSCOMMANDS cmd="getboforfilenames">
         <PDMFILES>
           <FILE name="<relfilename in unix-konvention>">
             <FILETYPE name="<filetype1>"/>
             <FILETYPE name="<filetype2>"/>
           </FILE>
         </PDMFILES>
        </WSCOMMANDS>
        :Returns:
            (errCode, xmlLines) with
            errCode : integer indicating command success
            stringList : xmlString splitted into lines

            xmlLines:
              <PDMFILES>
               <FILE name="">
                 <object default="<0|1>" cdb_object_id="<>" numberkey="" indexsortvalue="" has_valid_path="<0|1|2>" >
                   # has_valid_path="<0|1|2>"
                   # 0 = Kein gueltiger Pfad,
                   # 1 = Absoluter Pad stimmt ueberein
                   # 2 = filename ist root des BObjects
                   # nummernschluessel und indexsortvalue fuer sortierung im wsm bereitstellen.
                   <ATTRIBUTES>
                   object-beschreibung bzw. die Attribute des Fachobjektes mit
                   cdbobj2xml erzeugt
                   </ATTRIBUTES>
                    <object_files>
                      <FILE name=""> #inkluse Pfad (unixkonvention!)
                                     (nur Dateien ohne belongs_to und nicht derived!
                    <object_files>
                 </object>
               </FILE>
             <PDMFILES>
        """
        self._clearCache()
        inputFilesAndTypes = self._parseInput()
        outList = []
        errCode = 0

        self._cacheFilesAndDocuments(inputFilesAndTypes)

        for f, fileTypes in inputFilesAndTypes:
            objectsForFiles = self._objectsForFile(f, fileTypes)
            outList.append((f, objectsForFiles))
        xmlStr = self._buildResult(outList)
        resultStream.write(xmlStr)
        return errCode

    def _cacheFilesAndDocuments(self, inputFilesAndTypes):
        chunks = []
        bnames = []
        origNames = []
        i = 1
        for filename, _fileTypes in inputFilesAndTypes:
            bname = os.path.basename(filename).lower()
            bnames.append(bname)

            origName, _ = os.path.splitext(bname)
            origNames.append(origName)
            if i % MAX_PAIRS == 0:
                chunks.append((bnames, origNames))
                bnames = []
                origNames = []
            i += 1
        chunks.append((bnames, origNames))

        nonDocs = {}
        for bnames, origNames in chunks:
            searchStmt = (
                "SELECT cdbf_object_id, cdbf_primary, cdbf_name, cdbf_original_name, cdb_folder, cdbf_type "
                "FROM cdb_file "
                "WHERE cdb_classname='cdb_file'"
            )
            fullStmt = searchStmt

            if self.assignOnlyAnchorFile:
                fullStmt = searchStmt + " AND cdbf_primary='1'"

            valueString = u",".join(u"'" + sqlapi.quote(val) + u"'" for val in bnames)
            fullStmt += " AND (lower(cdbf_name) IN (%s)" % valueString

            if self.useOriginalFileName:
                origNameSearchStmt = " OR (lower(cdbf_original_name) IN (%s))"
                valueString = u",".join(
                    u"'" + sqlapi.quote(val) + u"'" for val in origNames
                )
                origNameCondition = origNameSearchStmt % valueString

                fullStmt += origNameCondition
            fullStmt += ")"

            docIds = set()
            files = sqlapi.RecordSet2("cdb_file", sql=fullStmt)
            for f in files:
                self._name2files[f.cdbf_name.lower()].append(f)
                if self.useOriginalFileName:
                    origName = f.cdbf_original_name
                    if origName:
                        self._origName2files[origName.lower()].append(f)
                docIds.add(f.cdbf_object_id)
            docIds = docIds - set(six.iterkeys(self._docs))
            id2doc = getDocumentsById(docIds)
            self._docs.update(id2doc)
            missingIds = docIds - set(id2doc)
            # e.g. frames
            for missingId in missingIds:
                bObject = ByID(missingId)
                if bObject is not None:
                    nonDocs[missingId] = bObject

        self._wsObjectCache._retrieveRightsOf(six.iterkeys(self._docs))
        self._wsObjectCache._retrieveIndexesOf(six.itervalues(self._docs))
        getObjectHandlesFromObjectIDs(list(self._docs), True)
        self._docs.update(nonDocs)

    def _parseInput(self):
        """
        Analyze XML structure.

        :Return:
            (assignOnlyAnchorFileFlag, wsmWorkspaceClass, inputFiles) with
            assignOnlyAnchorFileFlag : bool
                indicate if only documents are to be suggested for assignment
                where the file is the anchor file
            wsmWorkspaceClass : string or None
                the configured workspace class, if existing
            inputFiles : list
                list of file names and filetypes with files for which documents are to be assigned
        """
        inputFilesAndTypes = []

        assignOnlyAnchorFileFlagTag = self._rootElement.etreeElem.find(
            "ASSIGN_ONLY_ANCHORFILE"
        )
        if assignOnlyAnchorFileFlagTag is not None:
            if "value" in assignOnlyAnchorFileFlagTag.attrib:
                value = assignOnlyAnchorFileFlagTag.attrib["value"]
                self.assignOnlyAnchorFile = u"1" == value

        useOriginalNameTag = self._rootElement.etreeElem.find("USE_ORIGINAL_NAME")
        if useOriginalNameTag is not None:
            if "value" in useOriginalNameTag.attrib:
                value = useOriginalNameTag.attrib["value"]
                self.useOriginalFileName = u"1" == value

        wsmWorkspaceClassTag = self._rootElement.etreeElem.find("WSM_WORKSPACE_CLASS")
        if wsmWorkspaceClassTag is not None:
            if "name" in wsmWorkspaceClassTag.attrib:
                value = wsmWorkspaceClassTag.attrib["name"]
                self.wsmWorkspaceClass = value

        pdmFilesTag = self._rootElement.etreeElem.find("PDMFILES")
        if pdmFilesTag is not None:
            for fileElement in pdmFilesTag:
                if fileElement.tag == "FILE":
                    filename = fileElement.attrib.get("name")
                    if filename is not None:
                        filetypes = []
                        for fileTypeElement in fileElement:
                            filetype = fileTypeElement.attrib.get("name")
                            if filetype is not None:
                                filetypes.append(filetype)
                        inputFilesAndTypes.append((filename, filetypes))

        additionalAttributesElem = self._rootElement.etreeElem.find(
            "ADDITIONAL_ATTRIBUTES"
        )
        if additionalAttributesElem is not None:
            self._requestedDocAttributes = set()
            for attr in additionalAttributesElem:
                if attr.tag == "attribute":
                    nameAttr = attr.attrib.get("name", None)
                    if nameAttr is not None:
                        self._requestedDocAttributes.add(nameAttr)

        return inputFilesAndTypes

    def _sortList(self, my, other):
        ret = (my[2] > other[2]) - (my[2] < other[2])
        if ret == 0:
            ret = (my[3] > other[3]) - (my[3] < other[3])
        return ret

    def _objectsForFile(self, filename, filetypes):
        """
        Searches cdb_files with given name, considering folders.
        :returns list of tuples
            (Object, hasValidPath, documentKey, indexsortValue), defaultObject
            Sorted descending. Last document checked in with highest indexSortValue
            ist first.
        """
        logging.info(u"_objectsForFile:filename=%s", filename)
        objectList = []
        validDirObjects = []
        boToKeyIndex = dict()
        bname = os.path.basename(filename).lower()

        files = set(self._name2files.get(bname, []))

        if self.useOriginalFileName:
            origName, _ = os.path.splitext(bname)
            origNameFiles = self._origName2files.get(origName)
            if origNameFiles is not None:
                for f in origNameFiles:
                    if filetypes:
                        if f.cdbf_type in filetypes:
                            files.add(f)
                            continue
                    else:
                        logging.error(
                            u"_objectsForFile: no file types for filename=%s: "
                            u"can't search by cdbf_original_name",
                            f,
                        )

        for f in files:
            logging.info(u"_objectsForFile:f=%s", f)

            bObjectId = f.cdbf_object_id
            bObject = self._docs.get(bObjectId)
            if bObject is not None and self._wsObjectCache.rightsOfBusinessObject(
                bObject
            ).get("get"):
                logging.info(u"_objectsForFile:f=%s", f)
                if (
                    hasattr(bObject, "cdb_classname")
                    and bObject.cdb_classname == self.wsmWorkspaceClass
                ):
                    logging.info(
                        u"_objectsForFile: skipping bObject: '%s' "
                        u"since its class is the workspace class",
                        bObject,
                    )
                    continue

                indexList, externalNumber, indexSortVal = getIndexes(
                    bObject,
                    self.indexRule,
                    wsObjectCache=self._wsObjectCache,
                    compatibilityMode=False,
                )
                ownIndexInfo = None
                for indexInfo in indexList:
                    if indexInfo.sort_value == indexSortVal:
                        ownIndexInfo = indexInfo
                        # own entry must always be included
                        break

                if ownIndexInfo:
                    boToKeyIndex[bObject] = (ownIndexInfo, externalNumber, indexSortVal)
                    dname = os.path.dirname(filename)
                    hasValidDir = self._validDirectory(bObjectId, dname, f.cdb_folder)
                    validDirVal = 0
                    if hasValidDir:
                        validDirObjects.append(bObject)
                        validDirVal = 1
                    else:
                        if f.cdb_folder == "" or f.cdb_folder is NULL:
                            validDirObjects.append(bObject)
                            validDirVal = 2
                    objectList.append(
                        (bObject, validDirVal, externalNumber, indexSortVal, f)
                    )
        # folder must be valid for the default object
        defaultObject = self._getDefaultObject(validDirObjects, boToKeyIndex)

        if six.PY2:
            objectList.sort(self._sortList, reverse=True)
        else:
            objectList.sort(key=functools.cmp_to_key(self._sortList), reverse=True)
        return objectList, defaultObject

    def _buildResult(self, outList):
        """
        outList is a tuple with (filename,(objectList,defaultObject))
        """
        root = ElementTree.Element("PDMFILES")
        attrCollector = AttributesCollector(self.lang)
        attrCollector.setRequestedDocAttributes(self._requestedDocAttributes)

        for fInfo in outList:
            fileElement = Element("FILE")
            fileElement.attrib["name"] = fInfo[0]
            objList, defaultObject = fInfo[1]
            for objInfo in objList:
                fObj = objInfo[0]
                objElement = Element("object")
                objElement.attrib["default"] = "1" if fObj == defaultObject else "0"
                objElement.attrib["cdb_object_id"] = fObj.cdb_object_id
                objElement.attrib["has_valid_path"] = six.text_type(objInfo[1])
                objElement.attrib["numberkey"] = objInfo[2]
                objElement.attrib["indexsortvalue"] = "%s" % objInfo[3]
                mainFile = objInfo[4]
                if getCdbClassname(fObj) == "cdb_frame":
                    nameValDict = attrCollector.getFrameAttributes(
                        fObj, ReducedAttributes.REDUCED_ATTRIBUTES
                    )
                else:
                    nameValDict = attrCollector.getDocumentAttributes(
                        fObj, ReducedAttributes.REDUCED_ATTRIBUTES
                    )
                attrElement = buildElementWithAttributes(ATTRIBUTES, nameValDict)
                objElement.append(attrElement.etreeElem)
                objFilesElement = Element("object_files")
                fElement = Element("FILE")
                fElement.attrib["filename"] = getRelPath(mainFile)
                objFilesElement.append(fElement)
                objElement.append(objFilesElement)
                fileElement.append(objElement)
            root.append(fileElement)
        xmlStr = ElementTree.tostring(root, encoding="utf-8")
        return xmlStr

    def _getDefaultObject(self, validDirObjects, boToKeyIndex):
        """
        Default objects only exist, if there is a distinct object
        of if all objects belong to the same z_nummer. The default
        objects has the maximum index.
        """
        defaultObject = None
        if len(validDirObjects) == 1:
            defaultObject = validDirObjects[0]

        else:
            keyToMaxObject = {}
            for doc in validDirObjects:
                indexInfo, externalNumber, indexSortVal = boToKeyIndex[doc]
                if (
                    self.indexRule
                ):  # if an index rule is configured, there must be a default!!!
                    if indexInfo.is_default:
                        keyToMaxObject[externalNumber] = (indexSortVal, doc)
                        break
                else:
                    maxInfo = keyToMaxObject.get(externalNumber)
                    if maxInfo is None or maxInfo[0] < indexSortVal:
                        keyToMaxObject[externalNumber] = (indexSortVal, doc)
            if len(keyToMaxObject) == 1:
                defaultObject = list(six.itervalues(keyToMaxObject))[0][1]
        return defaultObject

    def _validDirectory(self, bObjectId, dname, cdb_folder, folderItems=None):
        if dname == "" or dname == ".":
            valid = cdb_folder == NULL or cdb_folder == ""
        else:
            key = "@".join([bObjectId, dname])
            valid = self._dirnameBoCache.get(key)
            if valid is None:
                if folderItems is None:
                    folderItems = self._boFolderCache.get(bObjectId)
                    if folderItems is None:
                        folderItems = cdb_folder_item.KeywordQuery(
                            cdbf_object_id=bObjectId
                        )
                        self._boFolderCache[bObjectId] = folderItems
                bname = os.path.basename(dname)
                validFolder = None
                for f in folderItems:
                    if f.cdbf_name == bname and f.cdb_wspitem_id == cdb_folder:
                        validFolder = f
                        break
                if validFolder is not None:
                    valid = self._validDirectory(
                        bObjectId,
                        os.path.dirname(dname),
                        validFolder.cdb_folder,
                        folderItems,
                    )
                else:
                    valid = False
        return valid
