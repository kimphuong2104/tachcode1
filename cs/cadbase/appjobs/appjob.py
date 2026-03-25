#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2008 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     appjob.py
# Author:   jro
# Creation: 08.07.08
# Purpose:

"""
Module appjob.py

This is the documentation for the appjob.py module.
"""

__docformat__ = "restructuredtext en"

import codecs
import os
import time
from cdb import util
from cdb import rte

from ..appjobs.appcommand import AppCommand
from ..appjobs.appjobitem import AppJobItem
from ..appjobs.appresponse import AppResponse
from ..fstools.fsutils import rmMinusRf, assertDirectory

from ..wsutils.resultmessage import Result, ResKind
from ..wsutils.translate import tr, translate
from ..wsutils.wsconstants import DEFAULT_CAD_ENCODING
from ..wsutils.wserrorhandling import WsmException, FsDirCreateError, \
    FsDirDeleteError
from ..wsutils.wslog import logClasses, cdblogv


NumberGenerator = None


class CDBNumber(object):

    def __init__(self):
        pass

    def nextval(self, countername):
        return util.nextval(countername)


NumberGenerator = CDBNumber


class NotWrittenToDiskError(WsmException):

    """ Will be raised when certain operations are called on an appjob
    which is not yet written to the file system """
    pass


class ApplCallError(WsmException):

    """ Represents an error while calling the authoring application """
    pass


NOTIF_FNAME_PATTERN = "%s.job"
NOTIF_FNAME_PATTERN2 = "%s.job2"
NOTIF_DIR_NAME = "cadcommunication"
JOB_DESCR_FILE_NAME = "jobdescription.txt"
KEEP_JOBS_ENVVAR = "KEEP_JOBS"
RESPONSE_FNAME = "joberr.txt"

EXECUTE_SUBJOB_COMM_NAME = "EXECUTE_SUBJOB"
FILES_KW = "FILES"
PROJ_ENV_KW = "PROJECT_ENVIRONMENT"
NO_OF_OPERATIONS_KW = "NUMBER_OF_OPERATIONS"
ENCODING_KW = "encoding"


class AppJob(AppJobItem):

    """
    Represents a job to be processed by the application.
    """

    _numberGenerator = NumberGenerator()

    def __init__(self, projectEnv, processingFlags=[]):
        """
        Initialize self

        :Parameters:
            projectEnv : unicode
                Project Environment Name, that is passed to the application
            processingFlags : []
                flags defining behaviour of the application when processing
                this job
        """
        AppJobItem.__init__(self, flags=processingFlags)

        self.jobDir = None
        self._projEnv = projectEnv
        self._jobitems = []

    def __len__(self):
        return len(self._jobitems)

    def append(self, appJobItem):
        """
        Appends an appJobItem this job.

        :Parameters:
            appJobItem : AppCommand or AppJob
                The item to append
        """
        if isinstance(appJobItem, AppJob):
            appJobItem._setupAsSubjob()

        appJobItem._pullId()

        cdblogv(logClasses.kLogMsg, 8,
                "AppJob: appending item (id=%s, name='%s')"
                % (appJobItem.id, appJobItem.name))

        self._jobitems.append(appJobItem)

    def writeToFs(self, jobRoot, appl=None, parentDir=None,
                  encoding=DEFAULT_CAD_ENCODING, notificationPath=None):
        """
        Writes the job to the file system. Creates the job directory, if not
        yet existing

        :Parameters:
            jobRoot : unicode
                The job root directory
            appl : unicode
                the application which has to process this appjob item
            parentDir : unicode
                The directory of the parent (AppJob) where this item resides in
            encoding : unicode
                The encoding to use when writing files

            notificationPath : unicode or None
                Path for notfication files

        :returns: the path to the job directory
        """
        cdblogv(logClasses.kLogMsg, 8, "AppJob %s: writing to the fs..." % self.id)

        if not self.jobDir:
            jobId = str(self._numberGenerator.nextval("appjob_ctr"))
            self.jobDir = os.path.join(jobRoot, jobId)

        self._encoding = encoding
        if parentDir:
            # this is a subjob
            self.file = self.jobDir
            AppJobItem.writeToFs(self, jobRoot, appl, parentDir, encoding)
        elif appl:
            # this is the top level appjob and the application is known
            self._writeNotificationFile(appl, encoding, notificationPath)

        if not os.path.exists(self.jobDir):
            try:
                cdblogv(logClasses.kLogMsg, 8,
                        "AppJob.writeToFs(): creating job directory '%s'"
                        % self.jobDir)
                os.makedirs(self.jobDir)
            except Exception:
                raise FsDirCreateError(tr("Cannot create directory '%1'"),
                                       self.jobDir)

        jobFilePath = os.path.join(self.jobDir, JOB_DESCR_FILE_NAME)
        jobFile = codecs.open(jobFilePath, "w", encoding)

        try:
            self._writeJobFileHeader(jobFile)

            for jobitem in self._jobitems:
                jobFile.write("%s;" % os.path.join(self.jobDir,
                                                   jobitem._getFilename()))
                jobitem.writeToFs(jobRoot, appl, self.jobDir, encoding)

            jobFile.write("\n")
        finally:
            jobFile.close()
            cdblogv(logClasses.kLogMsg, 8,
                    "AppJob.writeToFs(): job description file '%s' written"
                    % jobFilePath)

        return self.jobDir

    def deleteFromFs(self):
        """
        delete the whole job from disk (including responsefile)
        """
        cdblogv(logClasses.kLogMsg, 8, "AppJob: deleting '%s'" % self.jobDir)

        keepJobs = rte.environ.get(KEEP_JOBS_ENVVAR, None)
        if not keepJobs:
            for jobitem in self._jobitems:
                jobitem.deleteFromFs()

            if self.jobDir:
                try:
                    rmMinusRf(self.jobDir)
                except FsDirDeleteError:
                    cdblogv(logClasses.kLogMsg, 7, "AppJob.deleteFromFs(): "
                            "cannot delete the directory '%s' (ignored)"
                            % self.jobDir)

    def getCommands(self):
        """
        return directly included commands in this job
        """
        return [jobitem for jobitem in self._jobitems
                if isinstance(jobitem, AppCommand)]

    def size(self, recursive=True):
        """
        Return the size of this AppJob, i.e. the number of commands included

        :Parameters:
            recursive : boolean
                Of True: considers the size of subappjobs
        """
        noItems = len(self._jobitems)
        if recursive:
            for subjob in self.getSubJobs():
                noItems += subjob.size(recursive)
        return noItems

    def getSubJobs(self):
        """
        return directly included subjobs in this job
        """
        return [jobitem for jobitem in self._jobitems
                if isinstance(jobitem, AppJob)]

    def lock(self):
        """
        locks all jobitems in this jobs to prevent the execution by the
        CAD system
        """
        cdblogv(logClasses.kLogMsg, 8, "AppJob %s: locking '%s'" % (self.id, self.jobDir))

        if self.jobDir:  # has it been written correctly?
            AppJobItem.lock(self)

            for jobitem in self._jobitems:
                jobitem.lock()
        else:
            cdblogv(logClasses.kLogErr, 0,
                    "AppJob.lock(): job not yet written to the fs")

    def unlock(self):
        """
        unlocks this jobitem
        """
        cdblogv(logClasses.kLogMsg, 8, "AppJob %s: unlocking '%s'" % (self.id, self.jobDir))

        if self.jobDir:
            AppJobItem.unlock(self)
            for jobitem in self._jobitems:
                jobitem.unlock()
        else:
            cdblogv(logClasses.kLogErr, 0,
                    "AppJob.unlock(): job not yet written to the fs")

    def wait(self, userFeedbackObj, callErrorReporter=None, parentJob=None):
        """
        wait until the job is either cancelled, finished or failed.

        :Parameters:
            userFeedbackObj : object or None
                Optional; used for user interaction
                (receiving cancel events & providing user feedback)
            callErrorReporter : object
                used to check for an application call error

        :returns: a Result object containing the processing result for this job
        """
        cdblogv(logClasses.kLogMsg, 8,
                "AppJob %s: waiting for the job '%s' to be processed"
                " by the application ..." % (self.id, self.jobDir))

        result = Result()

        if not self.jobDir:
            raise NotWrittenToDiskError(tr("Cannot wait for an application "
                                           "job not yet written to disk"))

        if userFeedbackObj and not self._userFeedbackValueSetByCaller(userFeedbackObj):
            userFeedbackObj.setRange(0, self.size(True))
            userFeedbackObj.setValue(0)

        callError = None
        if len(self) > 0:
            cancelled = False
            if userFeedbackObj:
                cancelled = userFeedbackObj.wasCanceled()
            if callErrorReporter:
                callError = callErrorReporter()

            while self.isRunning() and (not cancelled) and (not callError):
                if parentJob and not parentJob.isRunning():
                    break

                cdblogv(logClasses.kLogMsg, 8,
                        "AppJob.wait(): job %s still running ..." % self.id)
                time.sleep(0.1)
                if userFeedbackObj:
                    cancelled = userFeedbackObj.wasCanceled()
                if callErrorReporter:
                    callError = callErrorReporter()

                cmdsDone, _lastExeced, _errmsg, _filePath = self.executionState()
                if userFeedbackObj and not self._userFeedbackValueSetByCaller(userFeedbackObj):
                    userFeedbackObj.setValue(cmdsDone)

            cmdsDone, lastExecCmd, lastExecErrMsg, lastFilePath = self.executionState()
            if lastExecCmd is None:
                lastExecCmd = "n/a"
            if userFeedbackObj and not self._userFeedbackValueSetByCaller(userFeedbackObj):
                userFeedbackObj.setValue(cmdsDone)

            if callError:
                if lastExecErrMsg:
                    result.append(ResKind.kResError,
                                  translate("appjob",
                                            "Error while calling the "
                                            "application '%1'. The last "
                                            "executed command returned: %2"),
                                  str(callError),
                                  str(lastExecErrMsg))
                else:
                    result.append(ResKind.kResError,
                                  translate("appjob",
                                            "Error while calling the "
                                            "application: '%1'"),
                                  str(callError))
            elif cancelled:
                result.append(ResKind.kResCancel,
                              translate("appjob",
                                        "Execution of the application jobs "
                                        "cancelled by the user. Last "
                                        "executed command: %1 on file: '%2'"),
                              str(lastExecCmd),
                              str(lastFilePath))
            elif self.isFailed():
                logMsg = ("AppJob failed. Last command: %s; last file: %s; error: %s"
                          % (str(lastExecCmd),
                             str(lastFilePath),
                             str(lastExecErrMsg)))
                cdblogv(logClasses.kLogErr, 0, logMsg)

                result.append(ResKind.kResError,
                              translate("appjob",
                                        "Application job not successful. "
                                        "Last executed command:"
                                        " %1 on file '%2', error: '%3'"),
                              str(lastExecCmd),
                              str(lastFilePath),
                              str(lastExecErrMsg))
            elif parentJob and parentJob.isFailed():
                cmdsDone, lastExecCmd, lastExecErrMsg, lastFilePath = \
                    parentJob.executionState()
                result.append(ResKind.kResError,
                              translate("appjob",
                                        "Application job not successful, "
                                        " error: '%1' on file '%2'"),
                              str(lastExecErrMsg),
                              str(lastFilePath))
            else:
                # check for uncritical errors and write them as
                # 'info'-level msgs
                # into the result object (for user feedback)
                _criticalErrors, uncriticalErrors = self.errors()
                for commandName, errcode, errmsg in uncriticalErrors:
                    result.append(ResKind.kResInfo,
                                  translate("appjob",
                                            "Command '%1' failed with '%2'"),
                                  str(commandName),
                                  "%s: %s" %
                                  (str(errcode), str(errmsg)))

            # Execute the actions associated with commands in this job
            # Those actions run on the WSM side and perform usually task
            # such as renaming all the related stuff or cleanup etc.
            self._executePostActions()

            self.handoffResultEvent()

        return result

    def _userFeedbackValueSetByCaller(self, userFeedbackObj):
        """
        Check if range and value of the feedback object, e.g. a progressdialog,
        is set by the caller that created the feedback object
        """
        setByCaller = False
        if userFeedbackObj and hasattr(userFeedbackObj, "isValueSetByCaller"):
            setByCaller = userFeedbackObj.isValueSetByCaller()
        return setByCaller

    def executePreActions(self):
        """
        executes the pre actions associated with this appjob
        """
        success = True
        for jobitem in self._jobitems:
            if not jobitem.executePreActions():
                success = False
                break
        return success

    def _executePostActions(self):
        """
        executes the post actions associated with this appjob
        """
        for jobitem in self._jobitems:
            jobitem._executePostActions()

    def handoffResultEvent(self):
        """
        hands off the result to the accociated application operations
        """
        for jobitem in self._jobitems:
            jobitem.handoffResultEvent()

    def executionState(self):
        """
        returns the number of already executed jobitems,
        last executed jobitem and the corresponding error message

        :returns int, string|None, string|None, string|None
        """
        numberOfExecuted, lastExecedCmd, errmsg, filePath = \
            AppJobItem.executionState(self)
        if not errmsg:
            for comm in self._jobitems:
                subCommsExecuted, subLastExecedCmd, subErrmsg, subFilePath = \
                    comm.executionState()
                numberOfExecuted += subCommsExecuted
                if subLastExecedCmd:
                    lastExecedCmd = subLastExecedCmd
                    errmsg = subErrmsg
                    filePath = subFilePath
                else:
                    break

        return numberOfExecuted, lastExecedCmd, errmsg, filePath

    def errors(self):
        criticalErrs = []
        uncriticalErrs = []

        self._checkResponse()
        if self._response:
            for comm in self._jobitems:
                critErrs, uncritErrs = comm.errors()
                criticalErrs.extend(critErrs)
                uncriticalErrs.extend(uncritErrs)

        return criticalErrs, uncriticalErrs

    def projectEnvironment(self):
        """
        :return string or None. The project environment for this job
        """
        return self._projEnv

    def _setupAsSubjob(self):
        cdblogv(logClasses.kLogMsg, 8, "AppJob: setting up as a subjob...")
        self.name = EXECUTE_SUBJOB_COMM_NAME

    def _getResponse(self):
        """
        gets the execution result for this job
        """
        self._checkResponse()
        return self._response

    def _writeJobFileHeader(self, jobFile):
        """
        writes the fix header into the job description file
        """
        cdblogv(logClasses.kLogMsg, 8,
                "AppJob: writing the job file header...")

        jobFile.write("%s=%s\n" % (ENCODING_KW, self._encoding))
        if self._projEnv is not None:
            jobFile.write("%s=%s\n" % (PROJ_ENV_KW, self._projEnv))
        jobFile.write("%s=%s\n" % (NO_OF_OPERATIONS_KW, len(self._jobitems)))
        jobFile.write("%s=" % FILES_KW)

    def _getJobResponseFileName(self):
        return RESPONSE_FNAME

    def _checkResponse(self):
        """
        gets the execution result for this job
        """
        cdblogv(logClasses.kLogMsg, 8, "AppJob: checking response...")

        # the response can be gotten from 3 sources:
        # a) the .response-file (in the case of a subjob)
        # b) the job.result-file
        # c) the responses of the commands

        AppJobItem._checkResponse(self)
        if not self._response:
            if self.jobDir:
                respFilePath = os.path.join(self.jobDir,
                                            self._getJobResponseFileName())
                self._response = self._readResponse(respFilePath)

        if not self._response:
            subResponses = [item._getResponse() for item in self._jobitems]
            if subResponses:
                self._response = AppResponse.fromSubs(subResponses,
                                                      self.isCritical())

    def _writeNotificationFile(self, appl, encoding, notificationPath=None):
        """
        writes the notification file to the fs
        """

        if notificationPath is None:
            return
        cdblogv(logClasses.kLogMsg, 8, "AppJob: writing the notification file"
                " for the application '%s'" % appl)
        if notificationPath:
            cadCommDir = notificationPath
            assertDirectory(cadCommDir,
                            raiseException=True,
                            createMsg=("AppJob: creating the cadcomm "
                                       "directory: '%s'"
                                       % cadCommDir),
                            logLevel=8)
            self._writeNotificationFileDefaultEncoding(appl, notificationPath)
            self._writeNotificationFileCustomEncoding(appl, encoding, notificationPath)

    def _writeNotificationFileDefaultEncoding(self, appl, notificationPath=None):
        """
        Try to write the <cadsystem>.job file containing the job dir path.
        This is for older integrations.
        """
        if notificationPath is None:
            return
        cadCommDir = notificationPath
        jobFileName = os.path.join(cadCommDir, NOTIF_FNAME_PATTERN % appl)
        try:
            with open(jobFileName, "w") as fd:
                fd.write(self.jobDir)
        except UnicodeError:
            cdblogv(logClasses.kLogMsg, 7,
                    "Application call file '%s' cannot be written because the "
                    "job dir path cannot be encoded with the default encoding. "
                    "(This is not a problem with newer integrations."
                    % jobFileName)
            try:
                os.remove(jobFileName)
            except Exception:
                pass
        except EnvironmentError as envE:
            raise ApplCallError(tr("Cannot write the application "
                                   "call file '%1', reason: '%2'"),
                                jobFileName, str(envE))

    def _writeNotificationFileCustomEncoding(self, appl, encoding, notificationPath=None):
        """
        Write the <cadsystem>.job2 file containing the encoding itself and the
        job dir path in the.
        This is for newer integrations.
        """
        if notificationPath is None:
            return
        cadCommDir = notificationPath
        jobFileName = os.path.join(cadCommDir, NOTIF_FNAME_PATTERN2 % appl)
        try:
            with codecs.open(jobFileName, "w", encoding) as fd:
                fd.write("encoding=%s\n" % encoding)
                fd.write(self.jobDir)
        except UnicodeError:
            try:
                os.remove(jobFileName)
            except Exception:
                pass
            raise ApplCallError(
                tr("Cannot write the application call file '%1' because the job"
                   " directory path cannot be encoded with the configured"
                   " encoding '%2'."), jobFileName, encoding)
        except EnvironmentError as envE:
            raise ApplCallError(tr("Cannot write the application "
                                   "call file '%1', reason: '%2'"),
                                jobFileName, str(envE))
