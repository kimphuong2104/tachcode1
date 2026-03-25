#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2009 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     _wslog.py
# Author:   wen
# Creation: 26.11.09
# Purpose:


"""
Module _wslog.py

This is the documentation for the _wslog.py module.
"""

__docformat__ = "restructuredtext en"


LOGFILE_NAME = "wslog.log"

_cdbcontext = False


class logClasses(object):
    kLogErr = 0
    kLogMsg = 1


class logLevels(object):
    # information about an internal operation which is called very frequently
    TRACE = 9
    # information about an internal operation
    DEBUG = 7
    # information about some high level operation,
    # e.g. something which is called once per action invocation
    INFO = 5
    # some operation succeeded only partially
    WARNING = 3
    # some operation failed
    ERROR = 1
    # the program is in an inconsistent state
    CRITICAL = 0
