#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2010 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     wsmisc.py
# Author:   jro
# Creation: 05.02.10
# Purpose: unused on server check for deletion

"""
Module wsmisc.py

This is the documentation for the wsmisc.py module.
"""
from contextlib import contextmanager
from PyQt4 import QtGui, QtCore

from wsmsettings.settingnames import INTERNAL_SETTINGS
from wsmsettings.settings import Settings, isTrue

__docformat__ = "restructuredtext en"


def sortListByLen(listToSort):
    """
    modifies list in Place
    returns list of keys
    """
    def _cmpLen(seq1, seq2):
        l1 = len(seq1)
        l2 = len(seq2)
        if l1 < l2:
            return -1
        elif l1 == l2:
            return 0
        else:
            return 1

    listToSort.sort(_cmpLen)
    return listToSort


def conditionallyReraiseCurrentException():
    """
    reraise if catching of exceptions is explicitely disabled
    """
    catchExceptions = Settings().getSetting(INTERNAL_SETTINGS.FILENAME,
                                            INTERNAL_SETTINGS.catch_exceptions)
    if not isTrue(catchExceptions):
        raise


@contextmanager
def waitCursor():
    """
    Execute some code with a busy mouse cursor.
    """
    QtGui.qApp.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
    yield
    QtGui.qApp.restoreOverrideCursor()


@contextmanager
def temporarilyDisabledWaitCursor():
    """
    Execute some code with a temporarily normal mouse cursor.
    (E.g. showing a dialog while in a lengthy process.)
    """
    QtGui.qApp.changeOverrideCursor(
        QtGui.QCursor(QtCore.Qt.ArrowCursor))
    yield
    QtGui.qApp.changeOverrideCursor(
        QtGui.QCursor(QtCore.Qt.WaitCursor))
