#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2009 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     cdbwsmcmdprocessor.py
# Author:   ws
# Creation: 07.12.09
# Purpose:

"""
Module cdbwsmcmdprocessor.py

Processor for file and directory commands
"""
from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import logging

from cs.wsm.pkgs.bolistcommand import BoListCommand
from cs.wsm.pkgs.checkoutcommand import CheckoutCommand
from cs.wsm.pkgs.checkincommand import CheckinCommand
from cs.wsm.pkgs.cmdprocessorbase import CmdProcessorBase, WsmCmdErrCodes
from cs.wsm.pkgs.servertimingwrapper import measuringPoint


class CdbWsmCmdProcessor(CmdProcessorBase):
    """
    Handler class for directory action commands.
    """

    name = u"directoryactions"

    # root must be a WSCOMMANDS object
    def __init__(self, rootElement):
        CmdProcessorBase.__init__(self, rootElement)

    def call(self, resultStream, request):
        logging.info(u"cdbwsmcmdprocessor.call: start")
        command, ret = self._getCommandByAction(self._rootElement)
        if command:
            logging.info(u"cdbwsmcmdprocessor command: %s", command.NAME)
            command.setResultStream(resultStream)
            with measuringPoint("COMMAND %s" % command.NAME):
                command.executeCommand()

            with measuringPoint("CACHING %s" % command.NAME):
                command.setupCaching(request)

            with measuringPoint("REPLICATION %s" % command.NAME):
                command.triggerReplicationIfActive()

            with measuringPoint("CREATE REPLY %s" % command.NAME):
                command.generateReply()

        else:
            logging.error(
                "Error in <WSCOMMANDS>, no valid <WSCOMMANDS_CONTEXTOBJECT> found"
            )
            ret = WsmCmdErrCodes.invalidCommandRequest
        logging.info(u"cdbwsmcmdprocessor.call: end")
        return ret

    def _getBoList(self):
        pass

    def _checkin(self):
        pass

    def _checkout(self):
        pass

    def _getCommandByAction(self, rootElement):
        command = None
        retCode = WsmCmdErrCodes.messageOk
        cmd = rootElement.getFirstChildByName("COMMAND")
        if cmd is None:
            # Use first action, its the same for all elements
            contextObj = rootElement.getFirstChildByName("WSCOMMANDS_CONTEXTOBJECT")
            if contextObj is not None:
                cmd = contextObj.getFirstChildByName("COMMAND")
        if cmd:
            action = cmd.action
            if action == u"getbolist":
                command = BoListCommand(rootElement)
                retCode = command.verifyFastBlob()
            elif action == u"checkout":
                command = CheckoutCommand(rootElement)
            elif action == u"checkin":
                command = CheckinCommand(rootElement)
                retCode = command.verifyFastBlob()
        return command, retCode
