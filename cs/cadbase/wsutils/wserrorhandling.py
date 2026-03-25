#!/usr/bin/env python
# -*- Python -*-
# $Id$
#
# Copyright (C) 1990 - 2007 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     wserrorhandling.py
# Author:   ws
# Creation: 27.09.07
# Purpose:


import sys
import string
import traceback
import six

from ..wsutils.wslog import cdblogv, logClasses
from ..wsutils.translate import tr

assertType = None
assertEnumValue = None


def _assertType_nocheck(obj, objType):
    pass


def _assertEnumValue_nocheck(value, objType):
    pass


assertType = _assertType_nocheck
assertEnumValue = _assertEnumValue_nocheck
assertIsInstance = None


def _assertIsInstance_nocheck(obj, ofClass):
    pass


assertIsInstance = _assertIsInstance_nocheck


def getTraceBack():
    """
    Return an exception traceback for the current context.

    Use this function to get the full traceback after an exception has
    occurred.
    Normally, all exceptions should get handled by explicitly testing
    for the exception type. This function is used as a callback for
    cases where unknown und unforeseen runtime exceptions occur.
    """
    (exc_type, exc_value, exc_traceback) = sys.exc_info()
    if exc_type is None and exc_value is None and exc_traceback is None:
        excStr = ""
    else:
        excStr = string.join(
            traceback.format_exception(
                exc_type,
                exc_value,
                exc_traceback)
        )
    return excStr


class WsmException(Exception):

    """
    Base class for all exceptions which are defined in the
    workspace manager code. Each workspace manager exception
    carries a user displayable message, which can be composed
    from self._label and self._args. The label should contain
    format string in the form '<text>%1<moretext>%2...' where %<n>
    is the insertion point of the nth parameter from self._args.
    All strings are assumed to be in UTF8.

    Localisation:
    ============
    The messages can be localized by:
    qApplication.translate(label).arg(arg1).arg(arg2) etc.

    To be compatible with the qt label extractor
    the Exception should be instantiated as follows (e.g):

    WsmException(tr("cannot open %1, reason %2"), filename, errno)

    Extending:
    =========
    All data passed into the constructor will be used
    for message composing. If you want give
    the exception additional data, you should do in your own 'setter':
    excp.setErrDetails(errCode, errDetails)

    :ivar _label:
    :ivar _args:
    """

    def __init__(self, label, *args):
        assert isinstance(label, six.text_type)
        self._label = label
        self._args = args

        cdblogv(logClasses.kLogErr, 0, "Exception occurred: '%s'" % self,
                logTraceback=False)
        traceBack = getTraceBack()
        if traceBack:
            cdblogv(logClasses.kLogErr, 0,
                    "call stack: '%s'" % six.text_type(traceBack, errors="ignore"),
                    logTraceback=False)

    def __str__(self):
        def only_printable_7bit_ascii(v):
            for c in v:
                o = ord(c)
                if o > 127 or o < 32:
                    return False
            return True

        def sanitize_arg(v):
            """Make the object 7-Bit ascii printable"""
            if isinstance(v, six.text_type):
                # arg is unicode, so just convert it to a printable
                # expression via repr
                # strip off the u' and ' at start and end
                v = repr(v)[2:-1]
            elif isinstance(v, six.binary_type):
                # simple pass through if this is 7-Bit only
                if only_printable_7bit_ascii(v):
                    pass
                else:
                    # arg is str, but contains chars that are not
                    # representable
                    # in the default encoding (usually 7-bit ascii),
                    # do a roundtrip through repr to fix that
                    v = repr(v)[1:-1]
            else:
                # all others are treated like string
                v = str(v)
                v = v.decode(defaultencoding, 'backslashreplace')
                v = str(v)
            return v

        defaultencoding = sys.getdefaultencoding()
        if self._label is None:
            strRepr = str(None)
        else:
            strRepr = self._label.encode(defaultencoding, 'replace')
            i = 1
            for arg in self._args:
                index = "%%%i" % i
                arg = sanitize_arg(arg)
                strRepr = strRepr.replace(index, str(arg))
                i = i + 1
        return strRepr

    def getLabel(self):
        return self._label

    def getArgs(self):
        return self._args


class NotImplementedException(WsmException):
    pass


class ExpectedUniqueChildException(WsmException):
    pass


class ArgumentError(WsmException):
    pass


class AccessViolationError(WsmException):
    pass


class WsFsException(WsmException):

    """
    Base class for file system exceptions.
    """
    pass


class FsDirCreateError(WsFsException):

    """
    Exception raised if creation of a directory fails.
    """
    pass


class FsDirDeleteError(WsFsException):

    """
    Exception raised if deletion of a directory fails.
    """
    pass


class DirectoryNotEmpty(WsmException):

    def __init__(self, dirname):
        WsmException.__init__(self, tr("Can't delete directory '%1'."
                                       " Directory is not empty."),
                              dirname)


class AlreadyIsWorkspaceError(WsFsException):
    pass


class WsTypeError(WsmException):
    pass


class PdmBackendError(WsmException):

    """
    Base of all errors risen from the pdm server interface
    """
    pass


class ProxyNotFoundError(WsmException):

    """
    Exception raised if needed proxy was not found in revision
    """
    pass


class PdmServerError(PdmBackendError):

    """
    Represents an error returned by an server call
    (in the case of 2.9.4: talkapi errors)

    :ivar errCode:
    :ivar errDetails:
    """

    def __init__(self, label, *args):
        PdmBackendError.__init__(self, label, *args)
        self.errCode = None
        self.errDetails = None

    def setDetails(self, errCode, errMsg):
        self.errCode = errCode
        self.errDetails = errMsg


class PdmAdapterError(PdmBackendError):

    """
    Represents an error condition in the pdm adapter code
    """
    pass


class PdmAlreadyConnected(PdmAdapterError):

    """
    Thrown when connect() ing already connected backend
    """
    pass


class OperationRefused(WsmException):

    """
    Thrown when a operation is currently not available
    """
    pass


class PdmNotConnected(PdmAdapterError):

    """
    Thrown when somebody tries to use a not connected backend
    """
    pass


class NoIndexSelected(PdmAdapterError):

    """
    Thrown when getIndexProxy is called and
    no index is selected for the BObject.
    """

    def __init__(self):
        PdmAdapterError.__init__(self, "no index selected")


class ConnectionToDifferentServerError(WsmException):
    pass


class ConnectionToDifferentPdmSystemError(WsmException):
    pass


class ConnectionToDifferentUserError(WsmException):
    pass


class MissingCsCADPackagesError(WsmException):
    pass


class MandatoryLicenseError(WsmException):
    """
    Cannot connect because a mandatory license is missing on the server.
    """
    pass


class VersionMismatchError(WsmException):
    """
    Thrown when version requirements are not met.

    Throw this if server, WSM packages or cs.workspaces do not fullfill the
    requirements.
    """
    pass


class PdmConnectionBroken(PdmAdapterError):

    """
    Thrown if a broken connection was detected resp.
    the last disconnect failed.
    """
    pass


class ClearWsError(WsmException):

    """
    Thrown if clearing of a workspace failed.
    """
    pass


class CancelAllException(WsmException):

    """
    Throw if a long iterative operation should be cancelled
    """
    pass


class WorkspaceDeletedError(WsmException):

    """
    Thrown if workspace root folder was deleted
    """
    pass


class LinkAlreadyExistsError(WsmException):

    def __init__(self, linkId, srcBo):
        super(self.__class__, self).__init__(
            tr("Link with id: %1 is already existing in %2"),
            linkId, srcBo.getName())


class UserCancelException(Exception):

    """
    Throw if user cancelled an operation
    """
    pass


class AppinfoParseError(WsmException):

    """
    Represents a parse error while parsing an appinfo file
    """
    pass
