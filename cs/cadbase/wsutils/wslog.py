#!/usr/bin/env python
# -*- Python -*-
# $Id$
#
# Copyright (C) 1990 - 2007 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     wslog.py
# Author:   ws
# Creation: 22.08.07
# Purpose:

# logClasses and logLevels is reimported by other modules do not
# delete
import logging
import sys
from ..wsutils._wslog import logClasses, logLevels

__docformat__ = "restructuredtext en"


_wsmLogger = None


def _logv_wrapper(msgClass, level, text, logTraceback=None):
    if level == logLevels.CRITICAL:
        logging.critical(text)
    elif level == logLevels.ERROR:
        logging.error(text)
    elif level <= logLevels.WARNING:
        logging.warning(text)
    elif level <= logLevels.INFO:
        logging.info(text)
    else:
        logging.debug(text)


cdblogv = _logv_wrapper


def loggingEnabled(logLevel=None):
    return True


def stderr(msg):
    try:
        sys.stderr.write(msg)
    except EnvironmentError:
        pass
