#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2008 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     resultmessage.py
# Author:   jro
# Creation: 30.05.08
# Purpose:

"""
Module resultmessage.py

This is the documentation for the resultmessage.py module.

Ergebnisse aus Funktionen mit mehreren Objekten an die GUI zurueckliefern
"""

__docformat__ = "restructuredtext en"

import re
import six
from ..wsutils.translate import DEFAULTARG
from ..wsutils.wslog import cdblogv, logClasses
from ..wsutils.wserrorhandling import assertType, WsmException


class ResKind(object):
    kResOk = 0
    kResCancel = 1
    kResInfo = 2
    kResError = 3


class ResultMsg(object):

    def __init__(self, resType, msg, args, customData=None):
        """
        :param resType: ResKind
        :param msg: translation tuple (see Result.append)
        :param args: tuple of replacement arguments in msg
        :param customData: additional info for this message;
                           type depends on context
        """
        self._resType = resType
        self._msg = msg
        self._args = args
        self._customData = customData
        self._alternatives = set()

    def __repr__(self):
        """
        Return a printable representation of self for debug purposes.
        """
        if self._msg is None:
            return six.text_type(None)

        strRepr = self._msg[1]
        i = 1
        for arg in self._args:
            index = "%%%i" % i
            strRepr = strRepr.replace(index, six.text_type(arg))
            i = i + 1
        return strRepr

    def identity(self):
        """
        :return: str string that uniquely identifies this message
        """
        if self._customData is not None:
            try:
                return self._customData.identity()
            except AttributeError:
                pass
        return repr(self)

    def isTopLevel(self):
        """
        By default, a message is not regarded as top level.
        Only special messages with custom data can be top-level
        (-> Wizard steps).

        :return: bool
        """
        if self._customData is not None:
            try:
                return self._customData.isTopLevel
            except AttributeError:
                pass
        return False

    def getMsgType(self):
        return self._resType

    def getMsgTxt(self):
        return self._msg

    def setCustomData(self, customData):
        self._customData = customData

    def getCustomData(self):
        return self._customData

    def addAlternative(self, alternative):
        """
        :param alternative: ResultMsg
        """
        self._alternatives.add(alternative.identity())
        alternative._alternatives.add(self.identity())

    def isAlternativeOf(self, other):
        """
        :param other ResultMsg
        :returns bool
        """
        return self.identity() in other._alternatives

    def translate(self):
        """
        :return String or Qstring with arguments replaced
        """
        return self.translateCDB()

    def translateCDB(self):
        _context, message = self._msg
        return self.translateArgsCDB(message)

    def translateArgs(self, message=None):
        return self.translateArgsCDB(message)

    def _replaceArg(self, message, arg):
        """
        Replace QtLike the argument %min(n) by arg
        :param message: string
        :param arg:     string
        """
        replacements = re.findall(r"%(\d+)", message)

        if replacements:
            minnumber = min([int(x) for x in replacements])
            ret_message = message.replace("%%%d" % minnumber, arg)
        else:
            ret_message = message
        return ret_message

    def translateArgsCDB(self, message=None):
        """
        """
        if message is None:
            message = self._msg[1]
        for arg in self._args:
            if isinstance(arg, WsmException):
                arg = six.text_type(arg)
            try:
                if type(arg) == tuple and len(arg) == 2:
                    # try translating the argument itself
                    arg = arg[1]
                message = self._replaceArg(message, arg)
            except TypeError as te:
                cdblogv(logClasses.kLogErr, 0,
                        "ResultMsg.translateArgsCDB: applying argument "
                        "'%s' failed: %s" % (str(arg), te))
                # insert dummy placeholder to keep sequence of arguments
                message = self._replaceArg(message, DEFAULTARG)
        return message


class Result(object):

    def __init__(self, resType=ResKind.kResOk, msg=None, *args):
        """
        Creates a Result object with initial message

        IMPORTANT:
            - Never use unicode strings in translate method for msg argument
            - Always use Qt replaceables in translate method for msg argument

        Usage example:
            errDetail = "Error detail"
            Result(ResKind.kResError, translate("mymodule", "Error in mymodule: %1"), errDetail)

        :Parameters:
            resType : ResKind constant
                The result message type
            msg : tuple of string, string
                Context and message for translation, e.g. from wsutils translate() method.
            args : object
                Replaceable objects for use in message text
        """
        self._resType = resType
        self._msgs = []
        self._resultValues = {}
        if msg is not None:
            resMsg = ResultMsg(resType, msg, args)
            self._msgs.append(resMsg)

    def __repr__(self):
        """
        Return a printable representation of self for debug purposes.
        """
        strRepr = "\n".join([six.text_type(msg) for msg in self._msgs])
        return strRepr

    def append(self, resType, msg=None, *args, **kwargs):
        """
        Appends a message of type resType to the list of results.
        If msg is None only the global resType is set.
        If msg is valid a ResultMsg object is appended to the internal list

        IMPORTANT:
            - Never use unicode strings in translate method for msg argument
            - Always use Qt replaceables in translate method for msg argument

        :Parameters:
            resType : ResKind constant
                The result message type
            msg: 2-Tuple of String
                Strings for translation as returned by translate.translate (translation
                context and message)
            customData: (keyword-only argument)
                arbitrary data associated with this message
            args: unicode strings or WsmExceptions
                Replacements for the msg-string placeholders (%1,..%n) or WsmExceptions
        """
        self._resType = self._mergeResultTypes(self._resType, resType)

        if msg is not None:
            assertType(msg, tuple)
            customData = kwargs.get('customData')
            resMsg = ResultMsg(resType, msg, args, customData)
            self._msgs.append(resMsg)

    def appendMsg(self, msg):
        """
        Append ResultMsg to Result

        Parameters:
            msg: ResultMsg
        """
        resType = msg.getMsgType()
        self._resType = self._mergeResultTypes(self._resType, resType)
        self._msgs.append(msg)

    def prependMsg(self, msg):
        resType = msg.getMsgType()
        self._resType = self._mergeResultTypes(self._resType, resType)
        self._msgs.insert(0, msg)

    def extend(self, result):
        """
        Extends the msg list of an existing Result with values from result
        :Parameters:
            result: Result
        """
        msgTypes = [result._resType]

        # resultValues aus der uebergabe ubernehmen
        for key, value in result._resultValues.items():
            if key in self._resultValues:
                # falls value liste oder dict
                if hasattr(self._resultValues[key], "extend"):
                    self._resultValues[key].extend(value)
                else:
                    # sonst ueberschreiben
                    self._resultValues[key] = value
            else:
                # deep copy if list
                value = list(value) if isinstance(value, list) else value
                self._resultValues[key] = value

        for msg in result.getResultMsgs():
            msgTypes.append(msg.getMsgType())

            # und die Meldung noch anfuegen
            self._msgs.append(msg)

        for resType in msgTypes:
            self._resType = self._mergeResultTypes(self._resType, resType)

    def isOk(self):
        """
        Returns True if only kResOk msgs are available (there should only be one)

        :returns: Boolean
        """
        return self._resType == ResKind.kResOk or self._resType == ResKind.kResInfo

    def isCancel(self):
        """
        Returns True if one msg is of kind kResCancel and no msg of kind kResError  is available

        :returns: Boolean
        """
        return self._resType == ResKind.kResCancel

    def getNumMessages(self):
        """
        Returns the whole number (info, warnings and errors) of elements that are stored

        :returns: int
        """
        return len(self._msgs)

    def hasError(self):
        """
        Returns True if one msg is of type kResError

        :returns: Boolean
        """
        return self._resType == ResKind.kResError

    def hasInfo(self):
        """
        Returns True if only messages of type kResInfo are available
        :returns: Boolean
        """
        return self._resType == ResKind.kResInfo

    def isEmpty(self):
        """
        :returns: Boolean
        """
        return self.getNumMessages() == 0

    def getResultMsgs(self):
        """
        :returns: List of ResultMsg
        """
        return self._msgs

    def getResultValues(self):
        """
        :returns: dict with Function results (better than tuples with result as first argument
        """
        return self._resultValues

    def setResultValue(self, key, val):
        """
        set a result value
        The values are not copy when extend is used
        """
        self._resultValues[key] = val

    def getResultValue(self, key):
        """
        Returns a result value.

        :Parameters:
            key : Object
                Arbitrary object used as value key.

        :returns: Object. A set value or None
        """
        return self._resultValues.get(key, None)

    def sortMessages(self, key):
        """
        Sort the messages of this Result in place.

        :param key: function (ResultMsg -> sort value)
        """
        self._msgs.sort(key=key)

    def copy(self):
        """
        Creates a copy of this result such that is has an independent
        list of ResultMsg. The messages themselves are not copied.
        :return: Result
        """
        res = Result(self._resType)
        for msg in self.getResultMsgs():
            res.appendMsg(msg)
        return res

    def _mergeResultTypes(self, old, new):
        res = old
        if new == ResKind.kResError:
            res = new
        elif new == ResKind.kResInfo:
            if old != ResKind.kResError and old != ResKind.kResCancel:
                res = new
        elif new == ResKind.kResCancel:
            if old != ResKind.kResError:
                res = new
        return res
