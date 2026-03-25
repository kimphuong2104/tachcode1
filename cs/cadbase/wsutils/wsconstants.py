#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
# $Id$
#
# Copyright (C) 1990 - 2008 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# File:     wsconstants.py
# Author:   wen
# Creation: 13.03.08
# Purpose:

"""
Module wsconstants.py

Holds constants using by and affecting behavior of many modules
"""

__docformat__ = "restructuredtext en"


WSM_DIR = ".wsm"
WSM_DB = ".wsmdb"
PREVIEW_DIR = ".preview"
APPINFO_DIR = ".info"
NUMGEN_DIR = ".numgen"
HIST_DIR = ".wsmhistory"
TMP_DIR = ".tmp"

APPINFO_EXTENSION = ".appinfo"
PDMINFO_EXTENSION = ".pdminfo"
VARIANTCONFIG_EXTENSION = ".variantconfig"
WS_INFO_NAME = "workspace.info"

CDBNAME = "CIM DATABASE"
WSMNAME = "Workspace Manager"
CDBWSMNAME = "CONTACT Workspace Manager"
INST_DIR_NAME = "CDB_WSM"

# WSM view constants for asmView - list or tree
ASMVIEW_LIST = "asmViewList"
ASMVIEW_TREE = "asmViewTree"
FSVIEW = "fsView"

BLOBS_NOT_THERE_HASH = "-"

CONTEXTSENS_LABEL = "HELP_ID"


# ON WINDOWS OS
NOT_ALLOWED_FOLDERNAME_SIGNS = "\\\"*<>/?:|"
NOT_ALLOWED_FILENAMES = ["CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3",
                         "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
                         "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6",
                         "LPT7", "LPT8", "LPT9"]

DEBUG = True
DEFAULT_CAD_ENCODING = "utf-8"
LEGACY_INTEGRATIONS_ENCODING = "cp1252"


class CDB298CONSTANTS(object):
    DEFAULT_CLIENT = "wspmanager@Container"
    LICENSE_CLIENT = "wspmanager"


# actions available on documents in the wsp manager
class ACTIONS(object):
    NOTHING = "NOTHING"

    # commit direction
    NEW = "NEW"  # initial checkin of an wsite to the pdm server
    NEWGROUP = "NEWGROUP"  # Groupcheckin
    NEWINDEXONGROUP = "NEWINDEXONGROUP"  # Group Index on multiple documents
    COMMIT = "COMMIT"  # save the local change to the pdm server
    FORCECOMMIT = "FORCECOMMIT"
    NEWINDEX = "NEWINDEX"  # create a new document version on the pdm server
    COPY = "COPY"  # create a new copy on the pdm server
    SERVERDELETE = "SERVERDELETE"  # delete document on the server (in the commit pane)
    DISCARD = "DISCARD"  # revert by overwriting with the last synced state
    FORCESERVERDELETE = "FORCESERVERDELETE"  # forces deletion of modified data on server

    # update direction
    UPDATE = "UPDATE"  # update from the pdm server
    FORCEUPDATE = "FORCEUPDATE"
    UPDATEINDEX = "UPDATEINDEX"  # update the version from the pdm server
    CHECKOUT = "CHECKOUT"  # checkout the document from the pdm server
    FORCEUPDATEINDEX = "FORCEUPDATEINDEX"  # forces update index action, discards local data
    FORCECHECKOUT = "FORCECHECKOUT"  # forces checkout data from server, discards local data
    FORCELOCALDELETE = "FORCELOCALDELETE"  # forces deletion of locally modified data

    # local actions
    LOCALDELETE = "LOCALDELETE"  # delete document locally (in the update pane)
    RESTORE = "RESTORE"  # revert by overwriting with a state from a saved revision
    RenameActions = [NEWINDEX, COPY]


class LOCKSTATES(object):
    notLocked = 0
    lockedByMyself = 1
    lockedByOtherUser = 2
    lockedInOtherWorkspace = 3
    unknown = 4


class LOCKCHECKMODE(object):
    NOCHECK = 0
    OTHERLOCKS = 1
    OWNLOCK = 2


class WSSTARTMODES(object):
    STARTMODE_EMPTYWS = 0
    STARTMODE_LASTWS = 1
    STARTMODE_CUSTOMWS = 2


class LOADINPDMMODE(object):
    LOADMODE_NEWWS = 0
    LOADMODE_STARTWS = 1


class PDMINFOHASHES(object):
    # format... is about frames
    kFormatHash = "__formathash"


class COLORS(object):
    OkColor = "#468846"
    WarningColor = "#3a87ad"
    ErrorColor = "#b94a48"
    White = "#ffffff"
    Blue = "#5A8CC3"
    Orange = "#E94E26"
    Green = "#468846"
    Red = "#ff0000"


class FILTER(object):
    NONE = 0
    TRANSFERABLE = 1
    NOT_TRANSFERABLE = 2
    EXCLUDED = 3
    LOCKED = 4
    CONFLICTED = 5


class APPTYPES(object):
    DRAW = "drw"
    ASM = "asm"
    OTHER = "other"


class CDBWSCALL(object):
    # never change the int values (part of an external interface)
    SUCCESS = 0
    NOT_FOUND = 1
    NOT_UNIQUE = 2
    CANCELLED_BY_USER = 3
    PDM_CONNECTION_FAILURE = 4
    LICENSE_FAILURE = 5
    NOT_SUPPORTED_BY_PDM_SYSTEM = 6
    FILENAME_CONFLICT = 7
    FILE_NOT_FOUND_IN_WS = 8
    FILE_TRANSFER_FAILED = 9
    WORKSPACE_COULD_NOT_BE_OPENED = 10
    PARAMETER_FILE_MISSING = 11
    PARAMETER_FILE_INVALID = 12
    COULD_NOT_CREATE_LOCAL_DOCS = 13
    COULD_NOT_CREATE_PDM_DOCS = 14
    VERSION_CONFLICT = 15
    OTHER_FAILURE = 100
