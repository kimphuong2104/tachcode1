#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2009 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     appcommandresult.py
# Author:   wen
# Creation: 28.08.09
# Purpose:

"""
Module appcommandresult.py

This is the documentation for the appcommandresult.py module.
"""

__docformat__ = "restructuredtext en"


from ..wsutils.resultmessage import Result, ResKind


class AppCommandResult(Result):

    """
    Represents the result of the execution of an appcommand.
    Extends the standard-Result by adding at least of:
    - data: unprocessed data read from the .result_data-files
    """

    def __init__(self):
        Result.__init__(self)
        self._data = None

    @classmethod
    def fromResponse(cls, response):
        """
        creates and returns an AppCommandResult from an AppResponce object

        :Parameters:
            response : AppResponse
                The response object to create an AppCommandResult instance from
        """
        appCommRes = AppCommandResult()
        if response.isFailed():
            msg = response.errmsg or ""
            appCommRes.append(ResKind.kResError, ("appjobs", msg))
        appCommRes._data = response.data()
        return appCommRes

    def data(self):
        """
        returns the optionally included data which the processing application
        can provide via an .result_data-file.

        :rtype: dict(string -> list(string))
        :return: the data contained by this result
        """
        return self._data
