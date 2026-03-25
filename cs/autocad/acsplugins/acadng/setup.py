# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

# Setup for CIM DATABASE AutoCAD Converter Plugin


# 1.)
# common section
# This section contains general switches
#

#
# Defines the operating mode of the DCS integration.
#
# Possible values:
# 0: Conversion directly via DCS component (current procedure)
#    For operation in CADJob mode, an appInfo file must also exist for the
#    document. If this is not the case, the conversion is performed via
#    LISP scripts.
#
# 1: Conversion via LISP scripts (old procedure)
#
FORCE_LEGACY = 0

# which conversions provides this plugin
_Targets = ["hpgl", "dxf", "dwg", "enc. postscript",
            "postscript", "pdf", "pdfm", "resolvedwg",
            "multi_target"]

Conversions = {"acad": _Targets,
               "acad:sht": _Targets,
               "acad_mechanical": _Targets
               }

# maps the format to an file extension (for internal use)
Format2Suffix = {
    "hpgl": ".plt",
    "postscript": ".ps",
    "enc. postscript": ".eps",
    "dxf": ".dxf",
    "dwg": ".dwg",
    "pdf": ".pdf",
    "pdfm": ".pdf",
    "resolvedwg": ".dwg"
}

# maps the conversion targets to result filetypes
ResultTypes = {
    "hpgl": "HPGL",
    "dxf": "DXF",
    "dwg": "acad",
    "enc. postscript": "Postscript",
    "postscript": "Postscript",
    "pdf": "Acrobat",
    "pdfm": "Acrobat",
    "resolvedwg": "acad"
}

# maps an target format to a sheet plotting policy. Possible values for
# the policy are:
# a) CONVERT_CURRENT_LAYOUT : the current sheet (aka layout) will be converted
# b) CONVERT_ALL_LAYOUTS    : all layouts (including the modelspace)
#                             will be converted
# c) <layoutnumber>         : the layout with this number will be converted.
#                             numbering scheme: 0 -> modelspace
#                                               1 -> layout 1
#                                               2 -> layout 2
#                                               ...
#                                               n -> layout n
#

# PLEASE DO NOT CHANGE THE FOLLOWING 3 LINES, THE NAMES AND THE VALUES ARE CONSTANT!
CONVERT_CURRENT_LAYOUT = ""
CONVERT_ALL_LAYOUTS = "-1"
CONVERT_LAYOUTS_1_N = "-0"

# Please note! Sheet_Handling for the output formats DXF and DWG
#              must always be parameterized with "CONVERT_ALL_LAYOUTS".
#              All other output formats can be adapted as required.
SHEET_HANDLING_CATALOG = {
    "hpgl": CONVERT_CURRENT_LAYOUT,
    "dxf": CONVERT_ALL_LAYOUTS,
    "dwg": CONVERT_ALL_LAYOUTS,
    "postscript": CONVERT_CURRENT_LAYOUT,
    "enc. postscript": CONVERT_CURRENT_LAYOUT,
    "pdf": CONVERT_CURRENT_LAYOUT,
    "pdfm": CONVERT_ALL_LAYOUTS
}

# If True, the job will check accept different files with the same name without
# error (see E019124).
# WARNING: the consequence of doing this is to accept a "random" result (ie. it
# is undefined which file with a given name is used), the checked out files may
# *NOT* reflect the actual reference structure!!!!
ACCEPT_DUPLICATE_FILENAMES = False

# Defines output format for dxf conversion
#
# Possible values:
# "CURRENT": save dxf in current version
# "NEWEST":  save dxf in newest version (depending on the AutoCAD version used)
# "AC1024":  save dxf in AutoCAD 2010 format
# "AC1027":  save dxf in AutoCAD 2013 format
# "AC1032":  save dxf in AutoCAD 2018 format
#
DXF_FORMAT = "CURRENT"

# defines precision (number of bits 0..16) for dxf conversion
# or -1 for binary dxf
DXF_PRECISION = 16

# 2.)
# CADJOBS section contains CADJobs specific switches
#

# IMPORTANT: For proper operation of the integration, copy the
# ACADJobExec.jsonconf file to the $(CADDOK_HOME)/etc/jobexec
# subdirectory of the instance!

# defines plotter (depends from target) for CADJobs mode
PLOTTER = {
    "pdf": "CDB DWG To PDF.pc3",
    "pdfm": "CDB DWG To PDF.pc3",
    "hpgl": "CDB DWG To PLT.pc3",
    "postscript": "CDB DWG To PS2",
    "enc. postscript": "CDB DWG To EPS.pc3"
}

# list of allowed paper formats for each plotter target format
# Note: Each paper format must be available for the specified plotter
FORMAT_LIST = {
    "pdf": ["A0-Quer", "A0-Hoch", "A1-Quer", "A1-Hoch", "A2-Quer", "A2-Hoch",
            "A3-Quer", "A3-Hoch", "A4-Quer", "A4-Hoch", "A5-Quer", "A5-Hoch"],

    "pdfm": ["A0-Quer", "A0-Hoch", "A1-Quer", "A1-Hoch", "A2-Quer", "A2-Hoch",
             "A3-Quer", "A3-Hoch", "A4-Quer", "A4-Hoch", "A5-Quer", "A5-Hoch"],

    "hpgl": ["A0-Quer", "A0-Hoch", "A1-Quer", "A1-Hoch", "A2-Quer", "A2-Hoch",
             "A3-Quer", "A3-Hoch", "A4-Quer", "A4-Hoch", "A5-Quer", "A5-Hoch"],

    "postscript": ["A0-Quer", "A0-Hoch", "A1-Quer", "A1-Hoch", "A2-Quer",
                   "A2-Hoch", "A3-Quer", "A3-Hoch", "A4-Quer", "A4-Hoch",
                   "A5-Quer", "A5-Hoch"],

    "enc. postscript": ["A0-Quer", "A0-Hoch", "A1-Quer", "A1-Hoch", "A2-Quer"
                        "A2-Hoch", "A3-Quer", "A3-Hoch", "A4-Quer", "A4-Hoch",
                        "A5-Quer", "A5-Hoch"]
}

# Contains the name of the table column from zeichnung_v, which contains
# the block name (default is Z_FORMAT).
# CDB_ATTR_BLOCKNAME is ignored if CONST_BLOCKNAME is specified
#
CDB_ATTR_BLOCKNAME = "Z_FORMAT"

# Use this constant value as block name instead of CDB_ATTR_BLOCKNAME
# (default is "")
#
CONST_BLOCKNAME = ""

# Specify the number of units by which the actual sheet may
# deviate from the targeted paper size.
#
DELTA = 5

# Specify the plot style (named or color) to be used
# Example: acad.ctb
PLOT_STYLE = ""

# Possibility to extend the base file name with affix
NAME_AFFIX = ""

# Define result file name for RESOLVEDWG target
# Default = "" -> result file name = <basename>-merged.dwg
MERGE_FILENAME = ""

# 3.)
# LEGACY section contains Legacy specific switches

# cad system to use
# ACAD_EXE = "C:\\Program Files\\Autodesk\\AutoCAD 2018\\acad.exe"

# start options for acad process like profile, language, product
# ACAD_EXE_OPTIONS = ["/p", "CDB_ACAD_DCS"]
# ACAD_EXE_OPTIONS = ["/p", "<<VANILLA>>", "/product", "ACADM", "/language", "de-DE"]

# Maximum time per conversion in seconds
# ACAD_TIMEOUT = 600

# save/dont save the drawing back to the evault
#
# The default value for SAVE_DWG_FILE was changed to zero
# because DWG was added as target format.
# SAVE_DWG_FILE = 0

# Specifies the settings file for migrating from classic AutoCAD drawings
# MIGRATE_VINTAGE_FRAME_SETTINGS = "<PATH>\\acad_frame.cadsetting"
