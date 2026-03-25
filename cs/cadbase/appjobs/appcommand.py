#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2008 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     appcommand.py
# Author:   wen
# Creation: 08.07.08
# Purpose:

"""
Module appcommand.py

This is the documentation for the appcommand.py module.
"""

__docformat__ = "restructuredtext en"


from ..appjobs.appjobitem import AppJobItem
from ..appjobs.appcommandresult import AppCommandResult
from ..wsutils.wslog import cdblogv, logClasses, logLevels, loggingEnabled


class AppCommand(AppJobItem):

    """
    Representation of a single command to be performed by the application.
    """

    def __init__(self, name, fname, contextFiles, parameters, flags, operation,
                 successActions=None, failActions=None, preActions=None):
        """
        Initializes self

        :Parameters:
            name : unicode
                The name of this command. Is evaluated by the integrated
                applications, for the list of possible names see CEDM document
                D012984
            fname : unicode or None
                The main file this command operates on
            contextFiles : list or None
                This command should operate in context of these files
            parameters : list or None
                Parameters of this command. For the list of possible parameters
                see CEDM document D012984
            flags : list or None
                The flags of this item as specified in CEDM document D012984
            operation : AppOperation
                The operations which is to associate with this AppCommand
                instance
            successActions : list or None
                Actions to execute when this command has been processed
                successfully
            failActions : list or None
                Actions to execute when this command has been processed
                erroneously
            preActions : list or None
                Actions to execute before this command is going to be processed
        """
        AppJobItem.__init__(self, name, fname, contextFiles, parameters, flags)

        self._operation = operation
        self._preActions = preActions
        self._successActions = successActions
        self._failActions = failActions

        self.rebuildItem = None
        # absolute path to the new primary file of the item
        # (absolute is needed by buildMeshPathFromFileName)
        self.rebuildPrimFile = None
        # All (new) files belonging to the item with relative Path
        self.rebuildFiles = []

        if loggingEnabled(logLevels.TRACE):
            cdblogv(logClasses.kLogMsg, 9,
                    "AppCommand: %s-command created (file: '%s')" % (self.name, str(fname)))
            if contextFiles:
                ctxFilePaths = ", ".join(contextFiles)
                cdblogv(logClasses.kLogMsg, logLevels.TRACE,
                        "    context files: %s" % ctxFilePaths)
        # flag for a RENAME that changes references only and not the
        # workspaces content because source and target file already exist.
        self.isTransparentRename = False

    def __eq__(self, other):
        """
        overwrites the equality of appcommands
        """
        retVal = (self.name == other.name and self.file == other.file)
        retVal = (retVal and self.parameters == other.parameters and self.file)
        return retVal

    def setSuccessActions(self, actions):
        """
        set a list of actions which have to be executed in the the success
        case, i.e. in the case when this command could have been executed
        successfully

        :Parameters:
            actions : [AppCommandAction]
                The actions to execute in the success case
        """
        self._successActions = actions

    def executePreActions(self):
        """
        executes the pre actions associated with this command.
        """
        success = True
        if self._preActions is not None:
            cdblogv(logClasses.kLogMsg, 9,
                    "AppCommand: executing pre actions for %s" % self.id)
            for action in self._preActions:
                if not action.execute():
                    success = False
                    break
        return success

    def _executePostActions(self):
        """
        executes the post actions associated with this command.
        """
        cdblogv(logClasses.kLogMsg, 9,
                "AppCommand: executing post actions for %s" % self.id)

        self._checkResponse()
        toExecute = []
        if self.isFailed():
            toExecute = self._failActions
        elif self.isSucceeded():
            toExecute = self._successActions

        if toExecute:
            for action in toExecute:
                action.execute()

    def handoffResultEvent(self):
        """
        passes the result event to the associated objects
        """
        if self._operation:
            self._checkResponse()
            if self.isFailed() or self.isRunning():
                self._operation.setFailed()
            elif self.isSucceeded():
                self._operation.setSuccessful()

    def getOperation(self):
        """
        gets the AppOperation
        :returns: AppOperation
        """
        return self._operation

    def getResult(self):
        """
        returns a result object containing errors / warning information and
        (this is appcommand-specific) result data written by the processing
        application
        """
        response = self._getResponse()
        return AppCommandResult.fromResponse(response)
