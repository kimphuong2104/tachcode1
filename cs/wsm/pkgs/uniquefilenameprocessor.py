#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2011 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
Module uniquefilenameprocessor

Retrieve file types
"""
from __future__ import absolute_import

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = []


from collections import namedtuple

import logging
import six

from lxml import etree as ElementTree

from cdb import sqlapi, util

from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase


class UniqueFilenameProcessor(CmdProcessorBase):
    name = u"uniquefilename"

    FileTuple = namedtuple("FILETUPLE", "currentname,filemask")

    def __init__(self, rootElement):
        CmdProcessorBase.__init__(self, rootElement)

    def _parseInput(self):
        """
        parse input and return contextstring, dict(filetype)->list of (currentname,filemask)
        """
        renameFilesTag = self._rootElement.etreeElem.find("renamefiles")
        context = None
        err = 0
        filetypeDict = dict()
        if renameFilesTag is not None:
            context = renameFilesTag.attrib.get("filecontext", u"")
            for fileElement in renameFilesTag:
                if fileElement.tag == "file":
                    filetype = fileElement.attrib.get("filetype")
                    filemask = fileElement.attrib.get("filemask")
                    currentname = fileElement.attrib.get("currentname")
                    if (
                        filemask is not None
                        and filetype is not None
                        and currentname is not None
                    ):
                        typeList = filetypeDict.get(filetype)
                        if filemask.count("%") and filemask.find("%d") >= 0:
                            ft = UniqueFilenameProcessor.FileTuple(
                                currentname, filemask
                            )
                            if typeList is None:
                                typeList = [ft]
                                filetypeDict[filetype] = typeList
                            else:
                                typeList.append(ft)
                        else:
                            err = -10
                            logging.error("invalid filemask")
                            break
        return err, context, filetypeDict

    def _generateFilenames(self, context, fileTypeDict):
        """
        generate result as XML-String
        """
        root = ElementTree.Element("renamefiles")
        for fileType, fileList in six.iteritems(fileTypeDict):
            for f in fileList:
                countername = u"ufc_%s_%s" % (fileType, context)
                fnameUnique = False
                tries = 0
                while tries < 100 and not fnameUnique:
                    number = util.nextval(countername)
                    mask = f.filemask.replace("%d", "%08d")
                    newfilename = mask % number
                    rset = sqlapi.RecordSet2(
                        sql="select count(*) as cnt from cdb_file where cdbf_name ='%s' and cdb_classname in ('cdb_file', 'cdb_filerecord')"
                        % sqlapi.quote(newfilename)
                    )
                    cnt = rset[0].cnt  # pylint: disable=no-member
                    if cnt == 0:
                        fnameUnique = True
                    else:
                        tries += 1
                        logging.info(
                            "filename %s in use try again %d", newfilename, tries
                        )
                if fnameUnique:
                    fElement = ElementTree.Element("file")
                    fElement.attrib["currentname"] = f.currentname
                    fElement.attrib["newfilename"] = newfilename
                    root.append(fElement)
        xmlStr = ElementTree.tostring(root, encoding="utf-8")
        return xmlStr

    def call(self, resultStream, request):
        """
        Retrieve file types from PDM system.

        :Returns:
            errCode : integer indicating command success
        """
        errCode, context, fileTypeDict = self._parseInput()
        if errCode == 0:
            xmlOutput = self._generateFilenames(context, fileTypeDict)
            resultStream.write(xmlOutput)
        return errCode
