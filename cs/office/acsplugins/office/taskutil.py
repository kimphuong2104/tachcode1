# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2023 CONTACT Software GmbH.
# All rights reserved.
# https://www.contact-software.com/

"""
Module taskutil

This is the documentation for the taskutil module.
"""

from __future__ import absolute_import

import os
import win32con
import win32api
import win32ts
import win32process
import pywintypes
import logging

__docformat__ = "restructuredtext en"


def getSessionId():
    pid = os.getpid()
    sessionId = win32ts.ProcessIdToSessionId(pid)
    return sessionId


def getPidByProcessByName(processName):
    found = None
    sessionId = getSessionId()
    pids = win32process.EnumProcesses()
    for pid in pids:
        try:
            sameSession = win32ts.ProcessIdToSessionId(pid) == sessionId
        except pywintypes.error:
            sameSession = False
        if sameSession:
            handle = None
            try:
                handle = win32api.OpenProcess(
                    win32con.PROCESS_QUERY_INFORMATION
                    | win32con.PROCESS_VM_READ
                    | win32con.PROCESS_TERMINATE,
                    pywintypes.FALSE,
                    pid,
                )
            except pywintypes.error:
                pass
            if handle is not None:
                try:
                    modlist = win32process.EnumProcessModules(handle)
                    for mid in modlist:
                        name = str(win32process.GetModuleFileNameEx(handle, mid))
                        if processName.lower() == os.path.basename(name.lower()):
                            found = pid
                            break
                except pywintypes.error:
                    pass
                win32api.CloseHandle(handle)
        if found:
            break
    return found


def terminate_process(process_name):
    """
    terminates process by basename
    :return 0 = OK, 1= No Task found, 2 = kill failed
    """
    pid = getPidByProcessByName(process_name)
    retcode = 1
    while pid is not None:
        retcode = 0
        logging.debug("Tyring to close PID %s", pid)
        handle = None
        try:
            handle = win32api.OpenProcess(
                win32con.PROCESS_QUERY_INFORMATION
                | win32con.PROCESS_VM_READ
                | win32con.PROCESS_TERMINATE,
                pywintypes.FALSE,
                pid,
            )
            win32process.TerminateProcess(handle, 99)
        except pywintypes.error:
            logging.exception("Error terminating process %s-%s", pid, handle)
            retcode = 2
        finally:
            if handle is not None:
                win32api.CloseHandle(handle)
        pid = getPidByProcessByName(process_name)
    return retcode
