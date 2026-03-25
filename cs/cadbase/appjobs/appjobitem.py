#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2009 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     appjobitem.py
# Author:   wen
# Creation: 20.03.09
# Purpose:

"""
Module appjobitem.py

This is the documentation for the appjobitem.py module.
"""

__docformat__ = "restructuredtext en"


import os
import time

from ..appjobs.appresponse import AppResponse
from ..fstools.fsutils import readLinesFromFile, safeOpen
from ..wsutils.stringutils import StringTransformer
from ..wsutils.translate import tr
from ..wsutils.wsconstants import DEFAULT_CAD_ENCODING
from ..wsutils.wserrorhandling import WsmException, NotImplementedException
from ..wsutils.wslog import cdblogv, logClasses

import pkg_resources
from cdb import misc
from cdb import fls


__licInformation = None

PLUGIN_ENTRY_POINT_GROUP = "cs.jobexec.plugins"


def getLicInformation():
    """
    :returns LicInformations from JobExec
    """
    _plgs = {}
    if __licInformation is None:
        for ep in pkg_resources.iter_entry_points(group=PLUGIN_ENTRY_POINT_GROUP):
            try:
                jobExec = ep.load()
                _plgs[ep.name] = jobExec().getLicInfos()
            except Exception:
                misc.log_traceback("warning plugin '%s' at '%s' is not a valid plugin!"
                                   % (ep.name, ep.module_name))
    return _plgs


class CommandLockError(WsmException):
    pass


# names for the processingFlags
class processingFlags(object):
    StopOnError = "StopOnError"
    ReloadFiles = "ReloadFiles"
    SaveWorkFileAfterAction = "SaveWorkFileAfterAction"
    SaveContextFileAfterAction = "SaveContextFileAfterAction"
    CloseWorkFileAfterAction = "CloseWorkFileAfterAction"
    CloseWorkFileIfOpenedByAction = "CloseWorkFileIfOpenedByAction"
    CloseContextFileAfterAction = "CloseContextFileAfterAction"
    CloseContextFileIfOpenedByAction = "CloseContextFileIfOpenedByAction"


# names for application command parameters
class appCommParams(object):
    new_filename = "newfile"
    loadmode = "ladeart"
    variantid = "variantId"
    bomposlist = "bomposlist"


COMM_FNAME_PATTERN = "%05d.command"
LOCK_FNAME_PATTERN = "%05d.command.blocked"
DATA_FNAME_PATTERN = "%05d.command_data"
RESPONSE_FNAME_PATTERN = "%05d.command_result"
RESDATA_FNAME_PATTERN = "%05d.result_data"


OPERATION_KW = "operation"
FLAGS_KW = "flags"
FILE_KW = "file"
CXT_FILES_KW = "contextFiles"


class AppJobItem(object):

    """
    Represents a item of an application job.

    :ivar id:              unique id of this item.
    :ivar parentDir:       the directory where the parent of this item
                           resides in
    :ivar name:            the name of the requested appjob item
    :ivar fname:            the file to operate on
    :ivar contextFiles:    list of files the application has to load to perform
                           the command. e.g. the assembly or accociated drawing
    :ivar parameters:      parameters for the appjob item
                           (list of name/value pairs)
    :ivar flags:           processing flags to use different command policies
                           (list of processingFlags)
    """

    _nextFreeId = 0

    def __init__(self, name=None, fname=None, contextFiles=None,
                 parameters=None, flags=None):
        """
        Initializes self

        :Parameters:
            name : unicode or None
                The name of this item. Is evaluated by the integrated
                applications, for the list of possible names see
                CEDM document D012984
            fname : unicode or None
                The main file this item operates on
            contextFiles : list or None
                This item should operate in context of these files
            parameters : list or None
                Parameters of this item. For the list of possible parameters
                see CEDM document D012984
            flags : list or None
                The flags of this item as specified in CEDM document D012984
        """
        self.id = None
        self.parentDir = None
        self.name = name
        self.file = fname
        self.contextFiles = contextFiles
        self.parameters = parameters
        self.flags = flags

        self._response = None
        self._encoding = None

    def _checkLicense(self, application):
        """
        raises: cdb.fls-LicenseError, if check failed
        """
        licOk = False
        if self.name in ["SHUTDOWN",
                         "GET_WINDOW_TITLE",
                         "GET_PROJECT_ENVIRONMENT",
                         "SAVE_STATE",
                         "RESTORE_STATE",
                         "NOOP"]:
            return
        licInfo = getLicInformation()
        if application:
            applicationsLics = licInfo.get(application.lower())
            if applicationsLics:
                features = applicationsLics.getOperationFeatures(self.name)
                if features is None:
                    raise fls.LicenseError("Cadjobs: Not a licensed operation : %s" % self.name,
                                           "NO_OP_FEATURE")
                for f in features:
                    fls.allocate_license(f)
                    licOk = True
                if self.name == "SAVE_SECONDARY":
                    secFormat = None
                    if self.parameters:
                        for paramName, paramValue in self.parameters:
                            if paramName == "format":
                                secFormat = paramValue
                    if secFormat:
                        formatFeature = applicationsLics.getFormatFeatures(secFormat)
                        if formatFeature:
                            fls.allocate_license(formatFeature)
                        else:
                            raise fls.LicenseError("Cadjobs: No a licensed frm : %s" % secFormat,
                                                   "NO_SEC_FEATURE")
        if not licOk and application != "test_dummy":
            raise fls.LicenseError("No License Infos for System: %s Op: %s" % (application,
                                                                               self.name),
                                   "NO_APP_FEATURE")

    def _escape(self, fname):
        """
        Escapes or replaces ; in contextfiles by ?
        """
        return fname.replace(";", "?")

    def writeToFs(self, jobRoot, appl=None, parentDir=None,
                  encoding=DEFAULT_CAD_ENCODING):
        """
        Writes the item to the file system.

        :Parameters:
            jobRoot : unicode
                The job root directory
            appl : unicode
                the application which has to process this appjobitem
            parentDir : unicode
                The directory of the parent (AppJob) where this item resides in
            encoding : unicode
                The enconding to use when writing files

        :return: The path to the directory where the item has been written to
        """
        self._checkLicense(appl)
        if parentDir:
            self.parentDir = parentDir
            self._encoding = encoding

            commFilePath = os.path.join(self.parentDir, self._getFilename())
            commDataFilePath = os.path.join(self.parentDir,
                                            self._getDataFilename())

            cdblogv(logClasses.kLogMsg, 8,
                    "AppJobItem: writing to the fs, file: '%s'"
                    % commFilePath)

            commFile = commDataFile = None
            try:
                commFile = safeOpen(commFilePath, "w", encoding)

                # write command file
                commFile.write("%s=%s\n" % (OPERATION_KW, self.name))
                if self.flags:
                    commFile.write("%s=%s\n" %
                                   (FLAGS_KW, ";".join(self.flags)))
                if self.file:
                    commFile.write("%s=%s\n" %
                                   (FILE_KW, os.path.normpath(self.file)))
                if self.contextFiles:
                    commFile.write("%s=%s\n" %
                                   (CXT_FILES_KW,
                                    ";".join([self._escape(f) for f in self.contextFiles])))
                commFile.close()

                # write parameter data file, if necessary
                if self.parameters:
                    commDataFile = safeOpen(commDataFilePath, "w", encoding)
                    for paramName, paramValue in self.parameters:
                        commDataFile.write("%s=%s\n" %
                                           (str(paramName),
                                            self._escapeValue(paramValue)))
            finally:
                if commFile:
                    commFile.close()
                if commDataFile:
                    commDataFile.close()

            return parentDir

    def deleteFromFs(self):
        """
        Deletes the item from the file system.
        """
        myPotentialFiles = [os.path.join(self.parentDir, self._getFilename()),
                            os.path.join(self.parentDir,
                                         self._getDataFilename()),
                            os.path.join(self.parentDir,
                                         self._getLockFilename())]

        for fname in myPotentialFiles:
            if os.path.exists(fname):
                try:
                    cdblogv(logClasses.kLogMsg, 9,
                            "AppJobItem: deleting '%s'" % fname)
                    os.remove(fname)
                except EnvironmentError as envE:
                    cdblogv(logClasses.kLogErr, 0,
                            "AppJobItem: cannot remove the file '%s', "
                            "reason: '%s'" % (fname, envE))

    def lock(self):
        """
        locks this item to prevent the processing by the application
        """
        cdblogv(logClasses.kLogMsg, 9,
                "AppJobItem: locking %s" % self.id)

        if self.parentDir:
            lockFileName = os.path.join(self.parentDir,
                                        self._getLockFilename())
            try:
                fd = open(lockFileName, "w")
                fd.close()
                cdblogv(logClasses.kLogMsg, 9, "AppJobItem: created '%s'" % lockFileName)
            except EnvironmentError as envE:
                cdblogv(logClasses.kLogErr, 0,
                        "AppJobItem: cannot lock item %i, reason: '%s'"
                        % (self.id, envE))
                raise CommandLockError(tr("Error while locking "
                                          "the appjob item: '%1'"), str(envE))
        else:
            cdblogv(logClasses.kLogMsg, 0,
                    "AppJobItem.lock(): theres no parent dir")

    def unlock(self):
        """
        unlocks this item to allow the application to process it
        """
        cdblogv(logClasses.kLogMsg, 9, "AppJobItem: unlocking %s"
                % self.id)

        if self.parentDir:
            lockFileName = self.getExistingLockfile()
            if lockFileName:
                try:
                    os.remove(lockFileName)
                    cdblogv(logClasses.kLogMsg, 9, "AppJobItem: deleted '%s'" % lockFileName)
                except EnvironmentError as envE:
                    cdblogv(logClasses.kLogMsg, 5, "AppJobItem.unlock(): "
                            "cannot remove the lock file '%s', reason: %s"
                            % (lockFileName, envE))
            else:
                cdblogv(logClasses.kLogMsg, 9, "AppJobItem: no unlock file '%s'" % lockFileName)
        else:
            cdblogv(logClasses.kLogErr, 0,
                    "AppJobItem.unlock(): job not yet written to the fs")

    def getExistingLockfile(self):
        """
        Return True and a filename if a lock file exists for this job
        """
        returnPath = None
        if self.parentDir:
            lockFileName = os.path.join(self.parentDir,
                                        self._getLockFilename())
            try:
                if os.path.exists(lockFileName):
                    returnPath = lockFileName
            except EnvironmentError as e:
                cdblogv(logClasses.kLogErr, 0,
                        "AppJobItem.lockFileExists: %s" % str(e))
        return returnPath

    def isSucceeded(self):
        """
        returns True, if the item has been successfully processed by the
        application, False otherwise
        """
        self._checkResponse()
        succeeded = False
        if self._response:
            succeeded = self._response.errcode == 0
        return succeeded

    def isFailed(self):
        """
        returns True, if the item processing by the application has
        been failed, False otherwise
        """
        self._checkResponse()
        failed = False
        if self._response:
            failed = self._response.errcode != 0
        return failed

    def isRunning(self):
        """
        returns True, if the processing of this item isnt ready
        or is hasnt been touched at all, False otherwise.
        """
        self._checkResponse()
        return self._response is None

    def isCritical(self):
        """
        returns True, if an successful execution of this
        item is critical for the whole application job, False otherwise
        """
        critical = False
        if self.flags:
            critical = processingFlags.StopOnError in self.flags
        return critical

    def executionState(self):
        """
        returns the name and (if given) the errormessage of the
        last executed appjob item.
        :returns int, string|None, string|None, string|None
        """
        AppJobItem._checkResponse(self)
        if not self._response:
            return 0, None, None, None
        return 1, self.name, self._response.errmsg, self._response.filePath

    def errors(self):
        """
        returns the errors occurred during execution of this jobitem
        as two lists: critical and uncritical errors
        """
        criticalErrs = []
        uncriticalErrs = []

        self._checkResponse()
        if self._response:
            if self._response.isFailed():
                error = (self.name, self._response.errcode,
                         self._response.errmsg)
                if self.isCritical():
                    criticalErrs.append(error)
                else:
                    uncriticalErrs.append(error)
        return criticalErrs, uncriticalErrs

    def executePreActions(self):
        """
        executes the pre actions associated with this item
        """
        pass

    def _executePostActions(self):
        """
        executes the post actions associated with this item
        """
        raise NotImplementedException(tr("This method has to be implemented "
                                         "in the children of appjobitem"))

    def handoffResultEvent(self):
        """
        passes the result event to the associated objects
        """
        raise NotImplementedException(tr("This method has to be implemented "
                                         "in the children of appjobitem"))

    # protected: to use in children classes... ###########
    def _getResponse(self):
        """
        returns the applications' response
        """
        self._checkResponse()
        return self._response

    def _checkResponse(self):
        """
        checks if the applications' response is there.
        Stores it in the item, if so.
        """
        if not self._response:
            if self.parentDir:
                respFilePath = os.path.join(self.parentDir,
                                            self._getResponseFilename())
                self._response = self._readResponse(respFilePath)

    def _pullId(self):
        """
        pulls the next free id and assignes to this item
        """
        self.id = self._nextId()

    def _getFilename(self):
        """
        returns the filename to write this item to
        """
        return COMM_FNAME_PATTERN % self.id

    def _getLockFilename(self):
        """
        returns the file name to use when locking this item
        """
        return LOCK_FNAME_PATTERN % self.id

    def _getDataFilename(self):
        """
        returns the file name where additional data is written to
        """
        return DATA_FNAME_PATTERN % self.id

    def _getResponseFilename(self):
        """
        returns the file name where the application response is awaited
        """
        return RESPONSE_FNAME_PATTERN % self.id

    def _getResultDataFilename(self):
        """
        returns the file name where the command result data is stored
        """
        return RESDATA_FNAME_PATTERN % self.id

    def _escapeValue(self, val):
        # TODO: this is crap. reimplement
        v = "%s" % val
        v = v.replace("\\", "\\\\")
        v = v.replace("\n", "\\n")
        return v

    def _nextId(self):
        """
        returns the next free item id
        """
        nextId = AppJobItem._nextFreeId
        AppJobItem._nextFreeId += 1
        return nextId

    def _readResponse(self, respFilePath):
        """
        reads the response from the given file

        :return: None if the response isnt there or (error code, error message)
                 if the response file exists.
        """
        cdblogv(logClasses.kLogMsg, 9, "AppJobItem: reading response file %s"
                % respFilePath)
        response = None
        exists, lines = self._sharingViolationAwareFileReader(respFilePath)
        if exists:
            errcode = 0
            errmsg = ""

            # special handling of the responce file write-read race
            # condition
            # if the wsm does his read in when the file exists but isnt fully
            # written then just wait some time. Should be only relevant agains
            # the catia integration all newer implementations should provide
            # the .response file atomicly
            timeout = 10
            timecount = 0
            while len(lines) == 0 and timecount < timeout:
                time.sleep(0.05)
                exists, lines = readLinesFromFile(respFilePath, self._encoding)
                timecount += 1

            if len(lines) > 0:
                errcode = int(lines[0])
                if len(lines) > 1:
                    errmsg = lines[1]

                cdblogv(logClasses.kLogMsg, 9,
                        "AppJobItem: response read (%i, %s)"
                        % (errcode, errmsg))

                # try to read a .result_data-file
                result_data = self.__readResultData()
                response = AppResponse(errcode, errmsg, result_data,
                                       self.isCritical(), self.file)
            else:
                cdblogv(logClasses.kLogErr, 0,
                        "AppJobItem: response file '%s' is invalid"
                        % respFilePath)

        return response

    def __readResultData(self):
        """
        tries to read a .result-data file.

        :rtype: dict(string, list(string))
        :return: the parsed content of the result-data file or None
        """
        resdata = None
        if self.parentDir:
            resultDataFile = os.path.join(self.parentDir,
                                          self._getResultDataFilename())
            cdblogv(logClasses.kLogMsg, 9, "AppJobItem: reading result data file %s"
                    % resultDataFile)
            exists, lines = self._sharingViolationAwareFileReader(resultDataFile)
            if exists:
                resdata = self._parseResultData(lines)
        return resdata

    def _sharingViolationAwareFileReader(self, filePath):
        """
        Check if file exist, (sleep for best results), read content.

        If the integration is trying a operation on the file, e.g.
        System.IO.File.Delete, at the same time the wsm is reading,
        e.g. with codecs.open, the integration operation may fail with
        a sharing violation (...cannot access file because its used
        by another process..).
        # E037696: Sharing Violation error in integration if WSM tries
          to read file at same time
        """
        lines = []
        exists = os.path.exists(filePath)
        if exists:
            # tests on con-hth: errors with 0,05 sleep time no errors with 0.1
            # this is commented because of performance reasons.
            # time.sleep(0.1)
            exists, lines = readLinesFromFile(filePath, self._encoding)
        return exists, lines

    def _parseResultData(self, lines):
        """
        parses and returns the content of the .result_data file.

        :Parameters:
            lines : list(unicode)
                the content of the .result_data als list of lines. For format
                of .result_data see ...

        :rtype: dict(string, list(string))
        :return: the parsed content of the result-data file
        """
        # parses the following format:
        # ["key1=value1@value2@value3",
        #  "key2=value1@value2@value3", ...]

        KEY_VALUE_SEPARATOR = "="
        VALUE_SEPARATOR = "@"
        ESCAPER = "\\"
        resdata = {}
        for line in lines:
            keyVal = self.__split(line, KEY_VALUE_SEPARATOR)
            if len(keyVal) == 2:
                tmp = StringTransformer(separator=VALUE_SEPARATOR,
                                        escaper=ESCAPER).split(keyVal[1])
                values = []
                for value in tmp:
                    if not os.path.isabs(value):
                        value = value.replace(r"\n", "\n")
                    value = StringTransformer(escaper=ESCAPER).unmask(value)
                    values.append(value)
                resdata[keyVal[0]] = values
        return resdata

    def __split(self, txt, separator):
        """
        does an 2-split by looking up the first occurrence of the separator.

        returns (key,value)-tuple
        """
        # we do this shit do be compatible with cad systems which dont escape
        # separators in the values...
        keyPos = txt.find(separator)
        if keyPos == -1:
            return [txt]
        return list((txt[:keyPos], txt[keyPos + 1:]))
