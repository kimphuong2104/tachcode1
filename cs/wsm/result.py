#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# Revision: "$Id$"
#

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import six


class Result(object):
    """
    Represents the status of an operation (ok/failed) and contains
    info and error messages.

    Typical usage:

    >>> r = Result()
    >>> r.isOk()
    True
    >>> r.hasMessages()
    False

    >>> r += Info(u'241 foo objects were operated.')
    >>> r.isOk()
    True
    >>> r.hasMessages()
    True

    >>> r += Error(u'Operation could not be completed.')
    >>> r.isOk()
    False
    >>> r.hasMessages()
    True

    >>> len(r)
    2
    >>> firstMsg = r[0]
    >>> firstMsg.resultType == ResultType.Info
    True
    >>> for m in r: print m.text
    241 foo objects were operated.
    Operation could not be completed.
    """

    def __init__(self):
        """
        Construct an Ok-Result without messages.
        """
        self.resultType = ResultType.Ok
        self.resultMessages = []

    def __add__(self, other):
        """
        Combine two results.
        """
        res = Result()
        res.extend(self)
        res.extend(other)
        return res

    def __len__(self):
        """
        Number of messages.
        """
        return len(self.resultMessages)

    def __getitem__(self, item):
        return self.resultMessages[item]

    def extend(self, other):
        """
        Combine two results in-place.
        """
        self.resultType = max(self.resultType, other.resultType)
        self.resultMessages.extend(other.resultMessages)

    def isOk(self):
        """
        Was the operation successful?
        :return bool
        """
        return self.resultType < ResultType.Error

    def hasMessages(self):
        """
        Any messages?
        :return bool
        """
        return len(self.resultMessages) > 0

    def append(self, resultMessage):
        """
        Internal.
        """
        self.resultType = max(self.resultType, resultMessage.resultType)
        self.resultMessages.append(resultMessage)


class Info(Result):
    def __init__(self, message):
        """
        Construct a result with a single Info message.
        :param message: unicode
        """
        Result.__init__(self)
        self.append(ResultMessage(ResultType.Info, message))


class Error(Result):
    def __init__(self, message):
        """
        Construct a result with a single Error message.
        :param message: unicode
        """
        Result.__init__(self)
        self.append(ResultMessage(ResultType.Error, message))


class ResultType(object):
    Ok = 0
    Info = 1
    Error = 2


class ResultMessage(object):
    """
    Represents a single message of a result.

    Attributes are public.
    """

    def __init__(self, resultType, text):
        assert isinstance(text, six.text_type)
        assert resultType == ResultType.Info or resultType == ResultType.Error
        self.resultType = resultType
        self.text = text
