#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

"""
Add the file flag "readonly" to .appinfo files.
Use this script in CDB environments, where Python 2.7
is being used.

This script migrates .appinfo files for documents, where
the "standard_library" flag is set to "1". The flag
indicates, that the CAD model within the document is
used as a standard or norm part. These should never be
modified and therfore a read-only flag should be set for
those. To make sure, that all .appinfo files include the
read-only flag, this scripts checks or adds it for all
documents, that have the "standard_library" flag set.
"""

from __future__ import absolute_import
from __future__ import print_function

import os
import shutil
import sys
import time
import six
import traceback
import tempfile
import cProfile
import pstats
from datetime import datetime
from contextlib import contextmanager
from lxml import etree as ElementTree
from optparse import OptionParser

from cdb.dberrors import DBError
from cdb.storage import blob
from cdb import ddl, misc, sqlapi, transaction
from cdb.objects import OBJECT_STORE
from cdb import version
from cdb.storage.index import IndexListener

from cs.documents import Document

import six


MIGRATIONRESULT_SKIPPED = "SKIPPED"
# maximum number of values to put into a "WHERE X IN" query.
# most of all this is a Oracle limitation, see MAX_INLIST_VALUE constant
OBJ_IDS_PER_STMT = 1000
SCRIPT_DESCRIPTION = "Migration script to set read-only flags for .appinfo files"
APPINFO_EXTENSION = ".appinfo"

# global error messages indicator
global_errors = False


def getTimeStamp():
    return time.strftime("%d.%m.%Y %H:%M:%S", time.localtime(time.time()))


def isQuoted(string):
    return string.startswith(("'", '"')) and string.endswith(("'", '"'))


def msgLine(txt=""):
    sys.stderr.write("%s\n" % txt)


def msg(txt):
    sys.stderr.write(txt)


def showCalculatedTimes(startTime, docsTotal, processedTotal):
    now = time.time()
    elapsed = now - startTime
    if elapsed != 0:
        docsPerSecond = int(round(processedTotal / elapsed))
        docsPerMin = int(round(processedTotal / elapsed * 60))
        docsPerHour = int(round(processedTotal / elapsed * 3600))

        progressMsg = (
            "Average processing speed: %s docs/s %s "
            "docs/min %s docs/hour" % (docsPerSecond, docsPerMin, docsPerHour)
        )
        msgLine("%s\r" % progressMsg)
        logger.log(progressMsg)

        if processedTotal != 0:
            remaining = round((docsTotal - processedTotal) / (processedTotal / elapsed))
            formatString = "%H hours %M minutes"
            days = int(round(remaining / 86400))
            if days:
                formatString = "%s days %s" % (days, formatString)
            timeRemainingString = time.strftime(formatString, time.gmtime(remaining))
            msgLine("Estimated time remaining: %s\r" % timeRemainingString)


def is_blobstore_running():
    # from cdb/comparch/cdbpkg_sync
    try:
        bs = blob.getBlobStore("main")
        rg = bs.ReplicationGroup([])
        if rg is not None:
            rg.finalize()
    except Exception:
        bs = None
    return bs is not None


def checkWorkspacesVersion():
    """
    Checks minimum version of cs.workspaces package.
    (We need the "owner_application" attribute.)
    :return: bool
    """
    minVersion = "1.0.9"
    from cdb.comparch.packages import Package

    pkg = Package.ByKeys("cs.workspaces")
    if pkg is None:
        logger.syserr(
            "Package 'cs.workspaces' missing. Please install and try again.", True
        )
        return False

    logger.log("Platform version: %s" % version.getVersionDescription(), True)
    logger.log("'cs.workspaces' version found: %s" % pkg.version, True)

    majorVers, vers = pkg.version.split(".", 1)
    if "dev" in vers or vers == "0":
        return True

    versParts = vers.split(".")
    if len(versParts) != 3:
        logger.syserr("Unexpected version string for 'cs.workspaces': %s" % vers, True)
        logger.syserr("Quitting.", True)
        return False

    minParts = [int(p) for p in minVersion.split(".")]
    versParts = [int(p) for p in versParts]
    for found, expected in zip(versParts, minParts):
        if found > expected:
            return True
        if found < expected:
            logger.syserr(
                "Required version of 'cs.workspaces': %s.%s" % (majorVers, minVersion),
                True,
            )
            logger.syserr(
                "Please install the required version and and try again.", True
            )
            return False
    return True


@contextmanager
def disabledIndexListener():
    index_listener = IndexListener()
    reEnableListener = index_listener.disable()
    try:
        yield
    finally:
        if reEnableListener:
            index_listener.enable()


class Logger(object):

    LOG_INDENT = "    "

    def __init__(self):
        self._indent = None
        # lazy init
        self.logFile = None
        self.logFileName = ""

    def getlogFile(self):
        if self.logFile is None:
            while True:
                # considers parallel execution
                timeStamp = "_" + datetime.now().strftime("%y.%m.%d_%H.%M.%S")
                self.logFileName = self.getLogFilePrefix() + timeStamp + ".log"
                absPath = os.path.join(os.path.dirname(__file__), self.logFileName)
                if not os.path.exists(absPath):
                    self.logFile = open(absPath, "w")
                    break
                time.sleep(1)

        return self.logFile

    def getLogFilePrefix(self):
        # e.g. wsm_migrate_classic_and_1x
        return os.path.splitext(os.path.basename(__file__))[0]

    def getLogFileBaseName(self):
        # absolute path without extension
        root, _ext = os.path.splitext(self.getlogFile().name)
        return root

    def syserr(self, txt, logToStderr=False):
        ErrMsg = "ERROR: %s" % txt
        self.log(ErrMsg)
        if logToStderr:
            sys.stderr.write(ErrMsg)
        global global_errors
        global_errors = True

    def log(self, logMsg, logToStderr=False, linebreak=True):
        if linebreak:
            logMsg = "%s\n" % logMsg
        logMsg = self._indentMsg(logMsg)

        if logToStderr:
            sys.stderr.write(logMsg)

        logFile = self.getlogFile()
        logFile.write(logMsg)
        logFile.flush()

    def addIndent(self, indent=LOG_INDENT):
        if self._indent is None:
            self._indent = indent
        else:
            self._indent = "%s%s" % (self._indent, indent)

    def removeIndent(self, indent=LOG_INDENT):
        if self._indent is not None:
            self._indent = self._indent[: -len(indent)]

    def clearIndent(self):
        self._indent = None

    def _indentMsg(self, logMsg):
        if self._indent is not None:
            logMsg = "%s%s" % (self._indent, logMsg)
        return logMsg

    def __del__(self):
        if self.logFile:
            self.logFile.close()


logger = Logger()


def processUserInput(usrMsg, **kwargs):
    """
    Handle user input.

    y confirm action
    n refuse action
    a abort program (only available if function was called with abort=1)
    """
    usrMsg = usrMsg + "("
    allowedKeys = ["y", "n"]
    if "abort" in kwargs and kwargs["abort"]:
        usrMsg = usrMsg + "y)es n)o a)bort"
        allowedKeys.append("a")
    else:
        usrMsg = usrMsg + "y/n"
    usrMsg = usrMsg + ")\n"
    userInput = ""
    while userInput not in allowedKeys:
        sys.stderr.write("%s" % usrMsg)
        userInput = six.moves.input()

    if "y" == userInput:
        return 1
    elif "n" == userInput:
        return 0
    else:
        logger.log("Script aborted by user", logToStderr=True)
        sys.exit(2)


def mkZName(docRec):
    return "%s-%s" % (docRec.z_nummer, docRec.z_index)


def toStringTuple(iterable):
    strTuple = "','".join(iterable)
    strTuple = "('%s')" % strTuple
    return strTuple


class MigrationTool(object):

    # Number of zeichnung records to process before commit
    # (one record takes approx. 13k)
    DEFAULT_PAGESIZE = 500

    def __init__(self, options):
        self._options = options
        self.Appl2ClientNames = {}
        self.setAppl2ClientNames()
        self.ClientNames = []
        self.setClientNames()
        # temporary folder for downloaded appinfos
        self.tmpAppinfoDir = tempfile.mkdtemp(
            prefix=logger.getLogFilePrefix(), dir=os.environ.get("CADDOK_TMPDIR")
        )
        self._clientNamesToMigrate = self.collectClientNamesToMigrate(options)
        # result counters
        self._successfulMigrated = 0

    def getTmpAppinfoDir(self):
        return self.tmpAppinfoDir

    def setAppl2ClientNames(self):
        # set mapping of supported cdb application names to cdb client names.
        # The cdb client name lists are copied from the WSM PDMExtension plugins
        self.Appl2ClientNames = {
            u"acad": [u"acad", u"acad:dwt"],
            # Catia:session: see script for migrating catiav4 documents to CIM DATABASE 2.9.8
            # http://svn.contact.de/svn/src/cad/catiav4/branches/9.8/migrate298/v4_migrate298.py
            u"Catia:model": [u"Catia:model", u"Catia:session"],
            u"CatiaV5": [
                u"CatiaV5",
                u"CatiaV5:Part",
                u"CatiaV5:Prod",
                u"CatiaV5:Drawing",
                u"CatiaV5:cgr",
                u"CatiaV5:Process",
                u"CatiaV5:Processz",
                u"CatiaV5:Prodz",
            ],
            u"inventor": [
                u"inventor",
                u"inventor:prt",
                u"inventor:asm",
                u"inventor:dft",
                u"inventor:dwg",
                u"inventor:weld",
                u"inventor:psm",
                u"inventor:iprae",
            ],
            u"NESCAD": [
                u"NESCAD"
            ],  # first known since wsm 2.x but we keep it for setting wsm_is_cad.
            # ProE:DrawSheet, ProE:Papier: ignored, these are only 'placeholders', see E025980
            # ProE:UDF: ignored, see E025980
            # ProE:Manufact: supported, see E025980
            u"ProE": [
                u"ProE",
                u"ProE:Asmbly",
                u"ProE:Part",
                u"ProE:Drawing",
                u"ProE:Diagram",
                u"ProE:Format",
                u"ProE:Layout",
                u"ProE:Markup",
                u"ProE:Sketch",
                u"ProE:Report",
                u"ProE:Symbol",
                u"ProE:Table",
                u"ProE:Manufact",
            ],
            u"SolidEdge": [
                u"SolidEdge",
                u"SolidEdge:asm",
                u"SolidEdge:part",
                u"SolidEdge:draft",
                u"SolidEdge:psm",
                u"SolidEdge:pwd",
            ],
            u"SolidWorks": [
                u"SolidWorks",
                u"SolidWorks:asm",
                u"SolidWorks:part",
                u"SolidWorks:frm",
            ],
            u"Unigraphics": [u"Unigraphics", u"Unigraphics:prt", u"Unigraphics:drw"],
        }

    def setClientNames(self):
        # collects all supported cdb client names
        tmpClientNames = [clntNames for clntNames in self.Appl2ClientNames.values()]
        for el in tmpClientNames:
            self.ClientNames.extend(el)

    def collectClientNamesToMigrate(self, options):
        clientNames = set()

        # generating systems to migrate
        if not options.gensyslist or options.gensyslist == "all":
            clientNames = set(self.ClientNames)
        else:
            toMigrate = set(options.gensyslist.split(","))

            for entry in toMigrate:
                if entry in self.Appl2ClientNames:
                    clientNames.update(self.Appl2ClientNames[entry])

                elif entry in self.ClientNames:
                    clientNames.add(entry)

                else:
                    logger.log("Unknown generating system %s" % entry, logToStderr=True)
                    sys.exit(1)
        return clientNames

    def getAppinfoContent(self, doc):
        """
        If the document has exactly one primary file and
        his file has a .appinfo file, then read and
        return its content.

        :param doc: Read the .appinfo file from this document.
        :type doc: Document
        :return: A byte string or None.
        :rtype: str|None
        """
        appinfo_file = None
        content = None
        appinfos = dict()
        primary = None
        for f in doc.Files:
            if f.cdbf_type == "Appinfo":
                appinfos[f.cdb_belongsto] = f
            elif f.cdbf_primary == "1":
                if primary is None:
                    primary = f
                else:
                    return None
        if primary is not None:
            appinfo_file = appinfos.get(primary.cdb_wspitem_id)
            if appinfo_file:
                content = appinfo_file.get_content()
                content = six.text_type(content, encoding="utf-8")
        return appinfo_file, content

    def writeAppinfoToTempFile(self, appinfo_root, work_dir, appinfo_file):
        dst_name = os.path.join(work_dir, appinfo_file.cdbf_name)
        if six.PY2:
            # will be unicode for PY2, cannot be parsed with PY3
            encoding = six.text_type
        else:
            encoding = "unicode"
        appinfoContent = ElementTree.tostring(
            appinfo_root, encoding=encoding, pretty_print=True
        )
        if os.linesep == "\n":
            # force windows newlines. file was opened in binary mode and lxml
            # pretty print produces '\n' that are translated to unix newlines.
            # replace performance: 0.024-0.038 sec. for 84720 calls (25mb .appinfo-files)
            appinfoOutput = appinfoContent.replace("\n", "\r\n")
        elif os.linesep == "\r\n":  # windows line endings
            appinfoOutput = appinfoContent
        else:
            appinfoOutput = appinfoContent
        from io import open

        with open(dst_name, "w+", encoding="utf-8", newline="\r\n") as fd:
            fd.write(appinfoOutput)
        return dst_name

    def setAppinfoReadOnlyFileFlag(self, doc):
        appinfo_filename = None
        appinfo_file, content = self.getAppinfoContent(doc)
        if appinfo_file is not None and content is not None:
            # must be done this way, because otherwise the output is not pretty printed
            xmlParser = ElementTree.XMLParser(remove_blank_text=True)
            xmlTree = ElementTree.parse(six.StringIO(content), xmlParser)
            xmlRootNode = xmlTree.getroot()
            flagName = "readonly"
            flagToRewrite = xmlRootNode.find(
                ".//fileflag[@id='%s'][@value='true']" % flagName
            )
            if flagToRewrite is None:
                # remove the readOnly=false flag if existing
                readOnlyFalseFlag = xmlRootNode.find(
                    ".//fileflag[@id='%s'][@value='false']" % flagName
                )
                if readOnlyFalseFlag is not None:
                    readOnlyFalseFlag.getparent().remove(readOnlyFalseFlag)
                flagElem = ElementTree.Element("fileflag")
                flagElem.attrib["id"] = flagName
                flagElem.attrib["value"] = "true"
                # <fileflags> should be exactly one or none
                fileFlagsNode = xmlRootNode.find(".//fileflags")
                if fileFlagsNode:
                    # there is already existing <fileflags>
                    # node in appinfo. Take existing one
                    fileFlagsNode.append(flagElem)
                else:
                    # there is no existing <fileflags>
                    # node in appinfo create one
                    fileFlagsNode = ElementTree.Element("fileflags")
                    fileFlagsNode.append(flagElem)
                    xmlRootNode.append(fileFlagsNode)
                    # sort the same way appinfoparser does
                    xmlRootNode[:] = sorted(xmlRootNode, key=lambda elem: elem.tag)

                work_dir = self.getTmpAppinfoDir()
                appinfo_filename = self.writeAppinfoToTempFile(
                    xmlRootNode, work_dir, appinfo_file
                )
        return appinfo_filename, appinfo_file

    def run(self):
        """
        Run migration tool according to previously passed options.
        """
        if self._options.info:
            self.printInfo()

        else:
            logger.log(SCRIPT_DESCRIPTION, logToStderr=True)
            msgLine(len(SCRIPT_DESCRIPTION) * "-")
            logger.log("command line arguments: " + " ".join(sys.argv))

            # blobstore is needed by correctAndUpdateInvalidDocuments
            if not is_blobstore_running():
                sys.exit("\n BlobStore not running, please start it and try again.")

            if not checkWorkspacesVersion():
                sys.exit(1)

            logger.log(
                "Generating systems to migrate: %s"
                % ", ".join(sorted(self._clientNamesToMigrate)),
                logToStderr=True,
            )

            logger.log(
                "\nConnected with database %s " % misc.getConfigValue("CADDOK_SERVER"),
                logToStderr=True,
            )

            msgLine("\nWarning: Don't run this script in productive operation!\n")
            if not self._options.passive:
                proceedMsg = "Do you want to proceed?"
                if self._options.preparations_only:
                    proceedMsg = "Do you want to proceed with preparations (no migration will be done)?"
                if not processUserInput(proceedMsg):
                    sys.exit(2)

            with disabledIndexListener():
                self._migrateDocs()

            logger.log("\nMigration finished", logToStderr=True)

            if global_errors:
                logger.log(
                    "Errors occurred! See 'ERROR' entries in %s" % logger.logFileName,
                    logToStderr=True,
                )

    def _migrateDocs(self):
        startTime = datetime.now()
        logger.log(
            "\nStart time is %s" % startTime.strftime("%d.%m.%Y %H:%M:%S"),
            logToStderr=True,
        )
        try:
            if self._options.with_profiling:
                prof = cProfile.Profile()
                prof.runcall(self.prepareMigratedDocs)
                # write profile stats
                profilePath = logger.getLogFileBaseName() + ".preparations.pstats"
                prof.dump_stats(profilePath)
                fStream = open(profilePath + ".txt", "w")
                pstats.Stats(prof, stream=fStream).sort_stats(
                    "cumulative", "time", "calls"
                ).print_stats(100)
                fStream.close()
            else:
                self.prepareMigratedDocs()

            if not self._options.preparations_only:
                cdbObjectIds = self._getDocumentsToMigrate()

                if self._options.with_profiling:
                    prof = cProfile.Profile()
                    prof.runcall(self.migrateDocs, cdbObjectIds)
                    # write profile stats
                    profilePath = logger.getLogFileBaseName() + ".pstats"
                    prof.dump_stats(profilePath)
                    # print profile stats
                    pstats.Stats(prof).strip_dirs().sort_stats(
                        "cumulative", "time", "calls"
                    ).print_stats(50)
                    fStream = open(profilePath + ".txt", "w")
                    pstats.Stats(prof, stream=fStream).sort_stats(
                        "cumulative", "time", "calls"
                    ).print_stats(100)
                    fStream.close()
                else:
                    self.migrateDocs(cdbObjectIds)
        finally:
            endTime = datetime.now()
            totTime = endTime - startTime
            logger.log(
                "\nEnd time is %s" % endTime.strftime("%d.%m.%Y %H:%M:%S"),
                logToStderr=True,
            )
            logger.log("Total time %s" % totTime, logToStderr=True)

        logger.log("\nDocuments migration result:", logToStderr=True)
        logger.log("\ttotal migrated: %s" % self._successfulMigrated, logToStderr=True)

    def prepareMigratedDocs(self):
        """
        Prepare table MIGRATED_STANDARD_DOCS for the migration run.
        """
        msgLine("Preparing migration process...")
        msgLine()
        self._unlockAppinfos()
        self._updateTableMigratedStandardDocs()
        msgLine("\nPreparation of migration process finished.")

    def _unlockAppinfos(self):
        """
        Unlocks all .appinfo files
        """
        lockedAppinfoCount = 0
        lockedAppinfoStmnt = "cdbf_type='Appinfo' AND (cdb_lock IS NOT NULL AND cdb_lock <> '' AND cdbf_hash <> '')"
        try:
            sqlTable = sqlapi.SQLselect(
                "COUNT(*) FROM cdb_file WHERE %s" % lockedAppinfoStmnt
            )
            lockedAppinfoCount = sqlapi.SQLinteger(sqlTable, 0, 0)
        except DBError as ex:
            logger.log(
                "Unlocking .appinfo cdb_file entries failed: %s" % six.text_type(ex),
                True,
            )

        if lockedAppinfoCount > 0:
            msg("Unlocking appinfo files... ")
            stmt = (
                "UPDATE cdb_file SET cdb_lock='', cdb_lock_id=NULL, cdb_lock_date=NULL WHERE %s"
                % lockedAppinfoStmnt
            )
            if self._options.sqlcondition:
                stmt = (
                    "%s AND cdbf_object_id IN (select cdb_object_id from zeichnung where (%s))"
                    % (stmt, self._options.sqlcondition)
                )
            rows = sqlapi.SQL(stmt)
            msgLine("%s appinfo files unlocked" % rows)

    def printInfo(self):
        """
        Print information on the available CAD System formats.

        Show all supported CAD system formats ordered by CAD system.
        """
        for appl, clientNames in six.iteritems(self.Appl2ClientNames):
            print("\nApplications:%s" % appl)
            print("=====================")
            print("Available client names:")
            for clientName in clientNames:
                print(clientName)

    def _createTableMigratedStandardDocs(self):
        """
        Create table MIGRATED_STANDARD_DOCS and fill it with the keys in ZEICHNUNG.
        """
        # Find out if table exists. Somehow ddl.Table().exists() does not work.
        table_exists = True
        try:
            sqlapi.SQLselect("* FROM migrated_standard_docs")
        except Exception:
            table_exists = False

        if not table_exists:
            msgLine("\nCreating migration progress table...")
            t = ddl.Table(
                "migrated_standard_docs",
                ddl.Char("cdb_object_id", 40, 1),
                ddl.Char("appinfo_updated", 20),
                ddl.PrimaryKey("cdb_object_id"),
            )
            t.create()
            msgLine("\nMigration progress table created.")
        else:
            msgLine("\nMigration progress table already exists.")

    def _updateTableMigratedStandardDocs(self):
        """
        Maintains relation MIGRATED_STANDARD_DOCS
        """
        with transaction.Transaction():
            self._createTableMigratedStandardDocs()

        # check if there are new entries in ZEICHNUNG which are not
        # contained in MIGRATED_STANDARD_DOCS
        clientNamesStrTuple = toStringTuple(self._clientNamesToMigrate)

        selectStmt = (
            "SELECT cdb_object_id FROM zeichnung "
            "WHERE erzeug_system IN %s "
            "AND standard_library='1' "
            "AND cdb_object_id NOT IN "
            "(SELECT cdb_object_id FROM migrated_standard_docs)" % clientNamesStrTuple
        )
        if self._options.sqlcondition:
            selectStmt = "%s AND (%s)" % (selectStmt, self._options.sqlcondition)

        msgLine("Registering found documents for migration...")

        with transaction.Transaction():
            insertCount = sqlapi.SQLinsert(
                "INTO migrated_standard_docs (cdb_object_id) %s" % selectStmt
            )

        logger.log("Inserted %s records into migrated_standard_docs" % insertCount)

    def getPage(self, cdbObjectIds, bufNo, pageSize):
        """
        Return pageSize Document entries constructed from cdbObjectIds.
        """
        # use migrated_doc cache for this page
        object_id2migrated_standard_docs = {}

        start = bufNo * pageSize
        end = (bufNo + 1) * pageSize - 1
        keys = cdbObjectIds[start : end + 1]
        docs = []
        while keys:
            # pop OBJ_IDS_PER_STMT entries from keys
            ids = keys[:OBJ_IDS_PER_STMT]
            keys = keys[OBJ_IDS_PER_STMT:]
            objIdTuple = toStringTuple(ids)
            stmt = "cdb_object_id IN %s" % objIdTuple
            docs.extend(Document.Query(stmt))

            page_migrated_standard_docs = sqlapi.RecordSet2(
                "migrated_standard_docs", stmt
            )
            for entry in page_migrated_standard_docs:
                object_id2migrated_standard_docs[entry.cdb_object_id] = entry

        return docs, object_id2migrated_standard_docs

    def _getDocumentsToMigrate(self):
        clientNamesStrTuple = toStringTuple(self._clientNamesToMigrate)

        cond = (
            "erzeug_system IN %s "
            "AND EXISTS "
            "(SELECT * FROM migrated_standard_docs m "
            " WHERE zeichnung.cdb_object_id=m.cdb_object_id)" % clientNamesStrTuple
        )

        stmt = "SELECT cdb_object_id FROM zeichnung WHERE %s" % cond

        rs = sqlapi.RecordSet2(sql=stmt)

        cdbObjectIds = [r.cdb_object_id for r in rs]

        return list(set(cdbObjectIds))

    def migrateDocs(self, cdbObjectIds):
        """
        Main loop
        """
        docsTotal = len(cdbObjectIds)
        logger.log("Starting migration of %d documents" % docsTotal, True)
        # iterate document records in pages with separate transactions
        bufNo = 0
        pageSize = int(self._options.pagesize)
        percent = 0
        startTime = time.time()

        while (bufNo * pageSize) < docsTotal:
            page, object_id2migrated_standard_docs = self.getPage(
                cdbObjectIds, bufNo, pageSize
            )

            try:
                with transaction.Transaction():
                    msgLine(
                        "Migrating documents #%s - #%s   \r"
                        % (bufNo * pageSize, (bufNo + 1) * pageSize - 1)
                    )

                    for i, docRec in enumerate(page):
                        processedTotal = bufNo * pageSize + i
                        if (processedTotal > 0) and (processedTotal % 100 == 0):
                            percent = int((processedTotal / docsTotal) * 100)
                            if processedTotal % 1000 == 0:
                                showCalculatedTimes(
                                    startTime, docsTotal, processedTotal
                                )
                            msg(
                                "Processed %s documents of %s (~ %s percent)\r"
                                % (processedTotal, docsTotal, percent)
                            )
                        logger.log(
                            "Migrating document %s..." % mkZName(docRec),
                            logToStderr=False,
                        )
                        logger.addIndent()
                        migrated_doc = object_id2migrated_standard_docs.get(
                            docRec.cdb_object_id
                        )
                        if migrated_doc is not None:
                            try:
                                self._migrateDoc(docRec, migrated_doc)
                            except Exception as e:
                                logger.syserr("%s" % six.text_type(e))
                                logger.log("%s" % traceback.format_exc(), True)
                        else:
                            logger.syserr(
                                "Document has no entry in migrated_standard_docs."
                            )

                        logger.clearIndent()

            except Exception as e:
                logger.syserr(str(e), True)
                logger.log(
                    "Exception occurred:\nBacktrace:\n%s" % traceback.format_exc(), True
                )

            # clear cdb objects cache
            OBJECT_STORE.clear()
            bufNo += 1

    def _commitAppinfoFile(self, appinfo_filename, existing_appinfo_file):
        """
        Bulkapi import of locally created .appinfos
        """
        logger.log("Check in Appinfo to existing file record")
        existing_appinfo_file.checkin_file(appinfo_filename)
        logger.log("Appinfo file checked-in")
        try:
            os.unlink(appinfo_filename)
        except EnvironmentError as e:
            logger.log(
                "Deleting temp file '%s' failed: %s"
                % (appinfo_filename, six.text_type(e))
            )

    def _migrateDoc(self, docRec, migrated_doc):
        """
        Migrate single document
        """
        appinfo_updated = None if self._options.force else migrated_doc.appinfo_updated

        if not appinfo_updated:
            appinfo_updated = self._setReadonlyAppinfoOfDoc(docRec)

        migrated_doc.update(appinfo_updated=appinfo_updated)

        self._successfulMigrated += 1

    def _setReadonlyAppinfoOfDoc(self, docRec):
        """
        Set readonly flag for appinfo file.
        """
        ret = ""
        logger.log("Set readonly for appinfo...")
        logger.addIndent()

        # Check if there are multiple primary files
        primaryFiles = []
        nonCadFilesExist = False
        for rec in docRec.Files:
            if not rec.cdbf_derived_from and not rec.cdb_belongsto:
                primaryFiles.append(rec)
                if rec.cdbf_type not in self.ClientNames:
                    nonCadFilesExist = True

        if len(primaryFiles) == 1 and not nonCadFilesExist:
            appinfo_filename, appinfo_file = self.setAppinfoReadOnlyFileFlag(docRec)
            if appinfo_file is not None and appinfo_filename is not None:
                self._commitAppinfoFile(appinfo_filename, appinfo_file)
                ret = "1"
            else:
                logger.log("No Appinfo file for primary file exists for document...")
                ret = MIGRATIONRESULT_SKIPPED
        elif len(primaryFiles) > 1:
            logger.log("More than one primary file exists for document...")
            ret = MIGRATIONRESULT_SKIPPED
        elif len(primaryFiles) == 0:
            logger.log("No primary file exists for document...")
            ret = MIGRATIONRESULT_SKIPPED
        else:  # nonCadFilesExist
            logger.log(
                "The 'cdbf_type' of the primary file of the Appinfo does not belong to a value for 'erzeug_system' that should be migrated..."
            )
            ret = MIGRATIONRESULT_SKIPPED

        logger.log("Set readonly for appinfo result set to '%s'." % ret)
        logger.removeIndent()
        return ret


def createParser():
    parser = OptionParser()

    parser.add_option(
        "-i",
        "--info",
        action="store_true",
        dest="info",
        help="show available generating systems for migration",
    )
    parser.add_option(
        "-g",
        "--gensyslist",
        dest="gensyslist",
        default=None,
        help="comma separated list of generating systems "
        "to migrate or 'all' for all known systems (default). Use without spacing, "
        "e.g. -g SolidWorks:part,inventor:prt",
    )
    parser.add_option(
        "-s",
        "--sqlcondition",
        dest="sqlcondition",
        default=None,
        help="additional SQL condition limiting the set of documents "
        "to migrate e.g.\n"
        "\"z_nummer LIKE '9%'\".",
    )
    parser.add_option(
        "--force",
        action="store_true",
        dest="force",
        default=False,
        help="force (re-)migration (ignore migration results in migrated_standard_docs table)",
    )
    parser.add_option(
        "--with_profiling",
        action="store_true",
        dest="with_profiling",
        default=False,
        help="write a python profiling dump to .pstats file. Example for printing profile data: "
        "pstats.Stats(<file>).sort_stats('cumulative').print_stats(50)",
    )
    parser.add_option(
        "--passive",
        action="store_true",
        dest="passive",
        default=False,
        help="runs migration in unattended mode. No user interaction is required if all "
        "mandatory options are given).",
    )
    parser.add_option(
        "-p",
        "--pagesize",
        dest="pagesize",
        default=MigrationTool.DEFAULT_PAGESIZE,
        help="number of document records to be processed in "
        "one step (default: %s)" % MigrationTool.DEFAULT_PAGESIZE,
    )
    parser.add_option(
        "--preparations_only",
        action="store_true",
        dest="preparations_only",
        default=False,
        help="perform preparing operations only (at least unlock appinfo files, "
        "create and update migrated_standard_docs table). May be used prior to parallel "
        "script execution. No documents will be migrated.",
    )

    return parser


# Guard importing as main module
if __name__ == "__main__":
    optsParser = createParser()

    if len(sys.argv) <= 1:
        msgLine(SCRIPT_DESCRIPTION)
        optsParser.print_help()

    else:
        (parsedOptions, _args) = optsParser.parse_args()

        mt = MigrationTool(parsedOptions)

        try:
            mt.run()
        except Exception as e:
            logger.clearIndent()
            logger.syserr(str(e), True)
            logger.log(
                "Unknown exception occurred:\nBacktrace:\n%s" % traceback.format_exc(),
                True,
            )
            logger.syserr("Migration cancelled.", True)
        finally:
            try:
                shutil.rmtree(mt.getTmpAppinfoDir(), ignore_errors=True)
            except EnvironmentErrora as e:
                logger.log(
                    "Failed to delete temporary appinfo folder %s: %s"
                    % (mt.getTmpAppinfoDir(), six.text_type(e))
                )
