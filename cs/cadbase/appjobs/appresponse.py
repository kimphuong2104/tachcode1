#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2009 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     appresponse.py
# Author:   wen
# Creation: 20.03.09
# Purpose:

"""
Module appresponse.py
"""
from ..wsutils.wslog import cdblogv, logClasses

__docformat__ = "restructuredtext en"


EC_NOERROR = 0
EM_NOERROR = "No error"


class AppResponse(object):

    """
    Represents the response of the application. This is a helper class and
    should not be of relevance in the users of the appjobs module.

    :ivar errcode:         the error code returned from the application
    :ivar errmsg:          the error message returned from the application
    :ivar critical:        boolean indicating if this response is critical.
                           This matters when propagating the error status
                           in hierarchies.
    :ivar filePath:        Full path of the file of the AppCommand
                           where the error occurred
    :ivar _data:           string containing the content of the
                           .result_data-files which may be written as part
                           of the application responce.
    """

    def __init__(self, errcode=None, errmsg=None, data=None, critical=False, filePath=None):
        """
        Initialize self
        """
        self.errcode = errcode
        self.errmsg = errmsg
        self.critical = critical
        self._data = data
        self.filePath = filePath

    def __str__(self):
        """
        Get a printable representation of self.
        """
        attrs = (self.errcode, self.errmsg, self.filePath, self._data, self.critical)
        return "(errcode=%i, errmsg=%s, filePath=%s, data=%s, critical=%i)" % attrs

    @classmethod
    def fromSubs(cls, subresps, critical):
        """
        deviates an AppResponse objects from a set of 'sub responses', i.e.
        responses of the appjobitems which are one level deeper in the
        hierarchy
        """
        cdblogv(logClasses.kLogMsg, 9,
                "AppResponse: deviate from subresponses, "
                "critical: %i" % critical)
        result = AppResponse(EC_NOERROR, EM_NOERROR, critical)

        for subresp in subresps:
            if not subresp:
                result = None
                continue
            if subresp.isFailed() and subresp.isCritical():
                result.errcode = subresp.errcode
                result.errmsg = subresp.errmsg
                result.critical = subresp.critical
                result.filePath = subresp.filePath
                break

        return result

    def isFailed(self):
        return self.errcode != EC_NOERROR

    def isCritical(self):
        return self.critical

    def data(self):
        """
        Returns Result data as a dict.
        """
        return self._data
