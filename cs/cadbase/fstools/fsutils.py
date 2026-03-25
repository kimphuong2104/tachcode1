#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2008 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     fsutils.py
# Author:   ws
# Creation: 20.03.08
# Purpose:

"""
Module fsutils.py

This is the documentation for the fsutils.py module.
"""

__docformat__ = "restructuredtext en"

import codecs
import os
import stat
import time
import six

from ..wsutils.translate import tr
from ..wsutils.wserrorhandling import FsDirDeleteError, FsDirCreateError
from ..wsutils.wslog import logClasses, cdblogv


def rmMinusRf(path):
    """
    Recursively remove directory path.

    :Parameters:
    path : string
        file system path
    """
    _rmDirInternal(path, True)


def rmDirectoryContent(path):
    _rmDirInternal(path, False)


def _rmDirInternal(path, rmTopLevelDir):
    """
    Recursively delete the contents of path.

    :Parameters:
        rmTopLevelDir : boolean
            if set to True, also remove path itself
    """
    path = six.text_type(path)
    if not os.path.isdir(path):
        raise FsDirDeleteError(tr("'%1' is not a valid path"), six.text_type(path))

    handlingFiles = False   # context flag for exception handling
    try:
        for root, dirs, files in os.walk(path, topdown=False):
            handlingFiles = True
            for name in files:
                fullPath = os.path.join(root, name)
                osRemoveWriteProtectionAware(fullPath)
            handlingFiles = False
            for name in dirs:
                fullPath = os.path.join(root, name)
                os.rmdir(fullPath)
        fullPath = path
        if rmTopLevelDir:
            os.rmdir(fullPath)
    except EnvironmentError:
        if handlingFiles:
            exc = FsDirDeleteError(tr("Unable to delete file '%1'"),
                                   six.text_type(fullPath))
        else:
            exc = FsDirDeleteError(tr("Unable to delete directory '%1'"),
                                   six.text_type(fullPath))
        raise exc


def osRemoveWriteProtectionAware(path):
    try:
        os.remove(path)
    except EnvironmentError as e:
        if not os.access(path, os.W_OK):
            os.chmod(path, stat.S_IWUSR)
            os.remove(path)
        else:
            raise e


def readLinesFromFile(fName, encoding):
    """
    Read all lines from file fName

    :Parameters:
        fName : string
            filename of the file to be read including path
        encoding : string
            encoding to use
    :returns:
        pair (exists, lines)
            exists : boolean
                True if the file could be opened for reading
            lines : the lines read from the file
    """
    f = None
    exists = False
    lines = []
    try:
        f = codecs.open(fName, "r", encoding)
        exists = True
        rawLines = f.readlines()
        lines = [line.strip() for line in rawLines]
    except EnvironmentError:
        f = None
    finally:
        if f is not None:
            f.close()
    return exists, lines


def assertDirectory(dirPath,
                    raiseException=False,
                    createMsg=None,
                    logChannel=logClasses.kLogMsg,
                    logLevel=5):
    """
    Assert that directory dirPath does exist.

    Check if the directory does exist. If not, try to create the directory.
    If raiseException is set, the function raises an FsDirCreateError.
    If createMsg is set,

    :Parameters:
        dirPath : string
            file system path
        raiseException : boolean
            if set to True, an FsDirCreateError exception is raised
    """
    result = False
    if os.path.isdir(dirPath):
        result = True
    elif os.path.isfile(dirPath):
        cdblogv(logClasses.kLogErr, 0,
                "Unable to create directory '%s' because it "
                "is the name of an existing file" % dirPath)
    else:
        try:
            if createMsg is not None:
                cdblogv(logChannel, logLevel,
                        createMsg)
            os.makedirs(dirPath)
            result = True
        except EnvironmentError:
            cdblogv(logClasses.kLogErr, 0,
                    "Unable to create directory '%s'." % dirPath)
    if raiseException:
        if result is False:
            raise FsDirCreateError(tr("Cannot create directory '%1'"), dirPath)
    return result


_fsEncoding = None
_fsEncodingFound = False


def safeOpen(filePath, flags, encoding):
    """
    Safely opens a file, using multiple retries

    raises Exception on error
    """
    openedFile = None
    maxRetries = 10
    for retry in range(maxRetries):
        try:
            openedFile = codecs.open(filePath, flags, encoding)
            break
        except EnvironmentError as e:
            cdblogv(logClasses.kLogErr, 0,
                    "can't open file perhaps locked by virus scanner(%s). Retry "
                    "%d from %d" % (six.text_type(e), retry + 1, maxRetries)
                    )
            if (retry + 1) == maxRetries:
                raise e
            else:
                time.sleep(0.3)
    return openedFile
