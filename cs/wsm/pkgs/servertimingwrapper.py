#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os

from cdb import util, misc
from contextlib import contextmanager


def isTrue(val):
    return val in {"TRUE", "ON", "YES", "1"}


# read configuration
_wsm_server_log_memory = False
try:
    _wsm_server_log_level = int(util.getSysKey("wsm_server_log_timing"))
    _wsm_server_log_active = True
    try:
        logMem = util.getSysKey("wsm_server_log_memory")
        _wsm_server_log_memory = isTrue(logMem)
    except KeyError:
        pass
except Exception:
    _wsm_server_log_active = False
    _wsm_server_log_level = 0
    _wsm_server_log_memory = False

_cntr = -1


def timingWrapper(func):
    """
    Return a wrapped function/method with logging for start and end point.
    """
    if not _wsm_server_log_active:
        wrappedFunc = func
    else:
        context = getattr(func, "timingContext", None)
        logMemoryUse = (
            _wsm_server_log_memory
            and context is not None
            and not context.startswith("DETAIL")
        )
        if context is None:
            context = "%s-%s" % (func.__module__, str(func).replace(" ", "_"))

        def wrappedFunc(*args, **kwArgs):
            global _cntr
            _cntr += 1
            callNo = _cntr
            logBefore(context, callNo, logMemoryUse)

            ret = func(*args, **kwArgs)

            logAfter(context, callNo, logMemoryUse)
            return ret

    return wrappedFunc


def logBefore(context, callNo, logMemoryUse):
    memoryBefore = "n/a"
    peakBefore = "n/a"
    if logMemoryUse:
        memoryBefore, peakBefore = getMemoryUsage()

    misc.cdblogv(
        misc.kLogMsg,
        _wsm_server_log_level,
        "MEASURING_POINT %s <%s> <start> <wset: %s, peak: %s>"
        % (context, callNo, memoryBefore, peakBefore),
    )


def logAfter(context, callNo, logMemoryUse):
    memoryAfter = "n/a"
    peakAfter = "n/a"
    if logMemoryUse:
        memoryAfter, peakAfter = getMemoryUsage()

    misc.cdblogv(
        misc.kLogMsg,
        _wsm_server_log_level,
        "MEASURING_POINT %s <%s> <end> <wset: %s, peak: %s>"
        % (context, callNo, memoryAfter, peakAfter),
    )


def timingContext(context):
    """
    Adds a custom name for a timingWrapper.
    This decorator must be applied before timingWrapper, i.e. like this:

    @timingWrapper
    @timingContext("text")
    def functionToMeasure():
        ...
    """

    def internalDecorator(func):
        func.timingContext = context
        return func

    return internalDecorator


@contextmanager
def measuringPoint(context):
    """
    Alternative to timingWrapper, when measuring within functions instead of whole functions.
    """
    if not _wsm_server_log_active:
        yield
    else:
        global _cntr
        _cntr += 1
        callNo = _cntr
        logBefore(context, callNo, _wsm_server_log_memory)

        yield

        logAfter(context, callNo, _wsm_server_log_memory)


def getMemoryUsage():
    ret = -1, -1
    try:
        result = w.query(
            "SELECT WorkingSet, WorkingSetPeak"
            " FROM Win32_PerfRawData_PerfProc_Process"
            " WHERE IDProcess=%d" % os.getpid()
        )
        memoryUsg = int(result[0].WorkingSet) / 1024  # in KBs
        memoryPeak = int(result[0].WorkingSetPeak) / 1024  # in KBs
        ret = memoryUsg, memoryPeak
    except Exception:
        misc.cdblogv(misc.kLogErr, 0, "COULD NOT OBTAIN MEMORY USAGE WITH WMI")
    return ret


if _wsm_server_log_memory:
    # fully initialize WMI
    from cs.wsm.pkgs.wmi import WMI

    global w
    w = WMI(".")
    getMemoryUsage()
