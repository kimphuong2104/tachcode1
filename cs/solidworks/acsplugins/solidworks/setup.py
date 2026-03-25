# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

# Setup for CIM DATABASE SolidWorks Converter Plugin

# =============================================================================
# Configuration
# =============================================================================

# which conversions provides this plugin
Conversions = {
    "SolidWorks": ["dxf", "dwg", "pdf", "tif", "tiff", "jpg", "edrw", "slddrw", "multi_target"],
    "SolidWorks:DRW": ["dxf", "dwg", "pdf", "tif", "tiff", "jpg", "edrw", "SLDDRW", "multi_target"],
    "SolidWorks:part": ["3dpdf", "pdf", "wrl", "eprt", "igs", "step_ap203", "step_ap214", "stl",
                        "jpg", "multi_target"],
    "SolidWorks:PART": ["3dpdf", "pdf", "wrl", "eprt", "igs", "step_ap203", "step_ap214", "stl",
                        "jpg", "multi_target"],
    "SolidWorks:asm": ["3dpdf", "pdf", "wrl", "easm", "igs", "step_ap203", "step_ap214", "stl",
                       "jpg", "multi_target"],
    "SolidWorks:ASM": ["3dpdf", "pdf", "wrl", "easm", "igs", "step_ap203", "step_ap214", "stl",
                       "jpg", "multi_target"],
    }

TargetMap = {
    "dxf": ["dxf", ],
    "dwg": ["dwg", ],
    "3dpdf" : ["3dpdf", ],
    "pdf": ["pdf", ],
    "tif": ["tif", ],
    "tiff": ["tif", ],
    "jpg": ["jpg", ],
    "edrw": ["edrw", ],
    "easm": ["easm", ],
    "eprt": ["eprt", ],
    "wrl": ["wrl", ],
    "slddrw": ["slddrw", ],
    "SLDDRW": ["SLDDRW", ],
    "igs": ["igs", ],
    "step_ap203": ["step_ap203", ],
    "step_ap214": ["step_ap214", ],
    "stl": ["stl", ]}

# maps the format to an file extension (for internal use)
SuffixMap = {
    "dxf": "dxf",
    "dwg": "dwg",
    "pdf": "pdf",
    "3dpdf" : "pdf",
    "tif": "tif",
    "tiff": "tif",
    "jpg": "jpg",
    "wrl": "wrl",
    "edrw": "edrw",
    "easm": "easm",
    "eprt": "eprt",
    "slddrw": "slddrw",
    "SLDDRW": "SLDDRW",
    "igs": "igs",
    "step_ap203": "stp",
    "step_ap214": "stp",
    "stl": "stl"}

# maps the conversion targets to result filetypes
ResultTypes = {
    "dxf": "DXF",
    "dwg": "acad",
    "pdf": "Acrobat",
    "3dpdf" : "Acrobat",
    "tif": "TIFF",
    "tiff": "TIFF",
    "jpg": "JPG",
    "wrl": "VRML",
    "edrw": "EDRW",
    "easm": "EASM",
    "eprt": "EPRT",
    "slddrw": "SolidWorks",
    "SLDDRW": "SolidWorks:DRW",
    "igs": "IGES",
    "step_ap203": "STEP",
    "step_ap214": "STEP",
    "stl": "STL"
    }

# If True, the job will check accept different files with the same name without
# error (see E019124).
# WARNING: the consequence of doing this is to accept a "random" result (ie. it
# is undefined which file with a given name is used), the checked out files may
# *NOT* reflect the actual reference structure!!!!
ACCEPT_DUPLICATE_FILENAMES = False

# Activates the specified configuration for the model
# This value can also be passed explicitly as parameter[model_config] to the job
# call. In this case, please do not set the environment variable here.
# "Configname"
#SOLIDWORKS_ENV.CADDOK_ACS_PARAM_MODEL_CONFIG = "Default"

# Controls whether a multi-page PDF is to be generated for a multi-page CAD 
# drawing.
# "True" | "False"
#SOLIDWORKS_ENV.CADDOK_ACS_PARAM_MULTISHEET_PDF = "False"

# Controls whether a multi-page DWG/DXF is to be generated for a multi-page CAD 
# drawing.
# "True" | "False"
#SOLIDWORKS_ENV.CADDOK_ACS_PARAM_MULTISHEET_DWG_DXF = "False"

# Controls whether a multi-page TIFF is to be generated for a multi-page CAD 
# drawing.
# "True" | "False"
#SOLIDWORKS_ENV.CADDOK_ACS_PARAM_MULTISHEET_TIF = "False"

# Controls whether a multi-page EDRW is to be generated for a multi-page CAD 
# drawing.
# "True" | "False"
#SOLIDWORKS_ENV.CADDOK_ACS_PARAM_MULTISHEET_EDRW = "False"

# Controls affix name for result file name
# string for affix
# SOLIDEDGE_ENV.CADDOK_ACS_PARAM_NAME_AFFIX = "_ger"

################################# Tiff section #################################

# 0: Display as on the screen
# 1: Display like printer
#SOLIDWORKS_ENV.CADDOK_ACS_TIFF_MEDIUM = "1"

# [RGB|SW]
# RGB: Color,
# SW: Monochrome
#SOLIDWORKS_ENV.CADDOK_ACS_TIFF_FARBMODUS = "SW"

# Desired compression ("0": none, "1": Packbits, "2": Gruppe4Fax)
#SOLIDWORKS_ENV.CADDOK_ACS_TIFF_KOMPRESSION = "1"

# TIFF_DPI_[FORMAT] = Desired resolution of TIFF files
# Valid formats ["A0", "A1", "A2", "A3", "A4", "A4V"]
#SOLIDWORKS_ENV.CADDOK_ACS_TIFF_DPI_A0 = "72"
#SOLIDWORKS_ENV.CADDOK_ACS_TIFF_DPI_A1 = "72"
#SOLIDWORKS_ENV.CADDOK_ACS_TIFF_DPI_A2 = "72"
#SOLIDWORKS_ENV.CADDOK_ACS_TIFF_DPI_A3 = "72"
#SOLIDWORKS_ENV.CADDOK_ACS_TIFF_DPI_A4 = "72"
#SOLIDWORKS_ENV.CADDOK_ACS_TIFF_DPI_A4V = "72"

# TIFF_SKALIERUNG_[FORMAT] = Desired scaling factor for tiffs
# Valid formats ["A0", "A1", "A2", "A3", "A4", "A4V"]
#SOLIDWORKS_ENV.CADDOK_ACS_TIFF_SKALIERUNG_A0 = "100"
#SOLIDWORKS_ENV.CADDOK_ACS_TIFF_SKALIERUNG_A1 = "100"
#SOLIDWORKS_ENV.CADDOK_ACS_TIFF_SKALIERUNG_A2 = "100"
#SOLIDWORKS_ENV.CADDOK_ACS_TIFF_SKALIERUNG_A3 = "100"
#SOLIDWORKS_ENV.CADDOK_ACS_TIFF_SKALIERUNG_A4 = "100"
#SOLIDWORKS_ENV.CADDOK_ACS_TIFF_SKALIERUNG_A4V = "100"

################################# DXF/DWG section #############################

# Target format for DXF/DWG
# "r12", "r13", "r14", "r2000", "r2004", "r2007", "r2010", "r2013"
#SOLIDWORKS_ENV.CADDOK_ACS_DXF_DWG_VERSION = "r2013"

# Font used for DXF/DWG
# "STANDARD" | "TRUETYPE"
#SOLIDWORKS_ENV.CADDOK_ACS_DXF_DWG_FONTS = "STANDARD"

# Line types used for DXF/DWG
# "STANDARD" | "SOLIDWORKSSTYLES"
#SOLIDWORKS_ENV.CADDOK_ACS_DXF_DWG_LINESTYLES = "STANDARD"

# Scaling on/off
# "0" | "1"
#SOLIDWORKS_ENV.CADDOK_ACS_DXF_DWG_SCALE = "0"


####################### Detached Drawings section  #############################

# The drawings will be converted as detached drawings.
# "True" | "False"
# "True": The drawings will be converted as detached drawings.
#        In this case the drawings are checked out without references.
# "False":  The drawings are converted as normal drawings.
#SOLIDWORKS_ENV.CADDOK_ACS_DETACHED_DRAWING = "False"
################################################################################


################################# Layer control ################################

# Turns layer control on/off
# "True" | "False"
#SOLIDWORKS_ENV.CADDOK_ACS_PARAM_CONTROL_LAYOUT = "False"

# Specifies the layer names (comma-separated list) that should be displayed.
# All others will be explicitly suppressed.
# Only relevant if SOLIDWORKS_ENV.CADDOK_ACS_PARAM_CONTROL_LAYOUT = "True"
#SOLIDWORKS_ENV.CADDOK_ACS_PARAM_SHOW_LAYERS = ""

# Specifies the layer names (comma-separated list) that should be suppressed.
# Only relevant if SOLIDWORKS_ENV.CADDOK_ACS_PARAM_CONTROL_LAYOUT = "True"
#SOLIDWORKS_ENV.CADDOK_ACS_PARAM_SUPPRESS_LAYERS = ""

# Specifies the layer names (comma-separated list) that should be not 
# suppressed.
# Only relevant if SOLIDWORKS_ENV.CADDOK_ACS_PARAM_CONTROL_LAYOUT = "True"
#SOLIDWORKS_ENV.CADDOK_ACS_PARAM_UNSUPPRESS_LAYERS = ""
