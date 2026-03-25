#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2009 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     cmdprocessorbase.py
# Author:   jro
# Creation: 07.12.09

"""
Module cmdprocessorbase.py

Base processor for XML input
"""
from __future__ import absolute_import

__docformat__ = "restructuredtext en"


class CmdProcessorBase(object):
    # must be unique for derived classes
    name = u""

    def __init__(self, rootElement):
        self._rootElement = rootElement
        self._licResult = None

    def getRoot(self):
        return self._rootElement

    def setLicReply(self, licResult):
        """
        :param Elementree.Elememt with LicInformation
        """
        self._licResult = licResult

    def call(self, resultStream, request):
        """
        :param resultStream: Stream where this should write the result values

        :param request: A morepath Request. May be None
                        for not web based requests

        Virtual. Use utf-8 output stream for reply.
        Returns return code.
        """
        pass


class WsmCmdErrCodes(object):
    messageOk = 0
    emptyRequest = 1
    messageNotWellFormed = 2
    unknownMessageType = 3
    unknownCommand = 4
    invalidCommandRequest = 5
    unknownProcessingError = 6
    licenseCheckFailed = 7
    fastBlobLicense = 8
    fastBlobOldServer = 9
