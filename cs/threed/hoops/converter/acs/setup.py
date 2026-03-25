#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
HOOPS Converter plug-in setup for the ACS/DCS
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


Conversions = {
    "Catia:model": ["threed_batch", "threed_viewing"],
    "Catia:session": ["threed_batch", "threed_viewing"],
    "CatiaV5:Part": ["threed_batch", "threed_viewing"],
    "CatiaV5:Prod": ["threed_batch", "threed_viewing"],
    "CatiaV5:Shape": ["threed_batch", "threed_viewing"],
    "CatiaV5:cgr": ["threed_batch", "threed_viewing"],
    "CatiaV5:3dxml": ["threed_batch", "threed_viewing"],
    "IFC": ["threed_batch", "threed_viewing"],
    "IGES": ["threed_batch", "threed_viewing"],
    "inventor:asm": ["threed_batch", "threed_viewing"],
    "inventor:prt": ["threed_batch", "threed_viewing"],
    "JT": ["threed_batch", "threed_viewing"],
    "Parasolid": ["threed_batch", "threed_viewing"],
    "ProE:Asmbly": ["threed_batch", "threed_viewing"],
    "ProE:AsmblyInst": ["threed_batch", "threed_viewing"],
    "ProE:GenAsmbly": ["threed_batch", "threed_viewing"],
    "ProE:Part": ["threed_batch", "threed_viewing"],
    "ProE:GenPart": ["threed_batch", "threed_viewing"],
    "ProE:PartInst": ["threed_batch", "threed_viewing"],
    "Unigraphics": ["threed_batch", "threed_viewing"],
    "Unigraphics:prt": ["threed_batch", "threed_viewing"],
    "SolidEdge:asm": ["threed_batch", "threed_viewing"],
    "SolidEdge:part": ["threed_batch", "threed_viewing"],
    "SolidEdge:psm": ["threed_batch", "threed_viewing"],
    "SolidEdge:pwd": ["threed_batch", "threed_viewing"],
    "SolidWorks:asm": ["threed_batch", "threed_viewing"],
    "SolidWorks:part": ["threed_batch", "threed_viewing"],
    "STEP": ["threed_batch", "threed_viewing"],
    "VRML": ["threed_batch", "threed_viewing"],
    "PRC": ["threed_batch", "threed_viewing"],
    "3DS": ["threed_batch", "threed_viewing"],
}

# This map denotes the regular expression for finding part
# files of the specific source types. For file types with the value "" the
# converter plugin won't traverse their structure information, if available, and
# treat them as monolithic models.
# A keyword 'SCAN' can be used as a value to disable the matching of part
# files by regular expressions and enable a second stage to conversion,
# where the parts are converted from the list taken from the xml file generated
# in the first stage.
PartMap = {
    "Catia:model": "",
    "Catia:session": "",
    "CatiaV5:Part": "",
    "CatiaV5:Prod": "^.*\\.(CATPart|cgr|CATShape|model)$",
    "CatiaV5:Shape": "",
    "CatiaV5:cgr": "",
    "IFC": "",
    "IGES": "",
    "inventor:asm": "^.*\\.ipt$",
    "inventor:prt": "",
    "JT": "",
    "Parasolid": "",
    "ProE:Asmbly": "^.*\\.(prt|xpr)(\\.\\d+)?$",
    "ProE:AsmblyInst": "",
    "ProE:GenAsmbly": "",
    "ProE:Part": "",
    "ProE:GenPart": "",
    "ProE:PartInst": "",
    "Unigraphics": "SCAN",
    "Unigraphics:prt": "SCAN",
    "SolidEdge:asm": "^.*\\.(par|psm)$",
    "SolidEdge:part": "",
    "SolidEdge:psm": "",
    "SolidEdge:pwd": "",
    "SolidWorks:asm": "^.*\\.sldprt$",
    "SolidWorks:part": "",
    "STEP": "",
    "VRML": "",
    "PRC": "",
    "3DS": "",
}


ConverterImportParams = {
    "read_only_active_filter": True,
    "tessellation_lod": "medium",
    "import_hidden_objects": True,
    "load_all_sw_configurations": True,
}


# this is a hook called before generating a 3dpdf
# you can overwrite the function in your plugin configuration
# to add additional field attributes (e.g. coming from an engineering change)
# or modify those coming from the database
def pdf_additional_attributes(models, attrs):
    pass


# If True, the job will check accept different files with the same name without
# error (see E019124).
# WARNING: the consequence of doing this is to accept a "random" result (ie. it
# is undefined which file with a given name is used), the checked out files may
# *NOT* reflect the actual reference structure!!!!
ACCEPT_DUPLICATE_FILENAMES = False

ConverterCmdArgs = []

# Timeout (in seconds) after which a conversion job is killed
Timeout = 43200  # 12 Hours

# If a conversion started while an identical one is already in status 'processing',
# wait this many seconds to retry this job
IdenticalJobRetryDelay = 5

# For linux environments that do not have a display server running,
# the converter needs to be called with xvfb-run.
# If the automatic detection for the display server fails for some reason,
# the execution with xvfb can be forced via this setting.
ForceXvfb = False

# If set to True, the conversion server generates Creo Parametric accelerator 
# files (xpr/xas) to improve the support of family tables.
# Note: The conversion server needs a valid Creo Licence for this feature to work.
ProeGenerateAcceleratorFiles = False

# If set to True, the conversion job fails after a failure during the
# generation of Creo Parametric accelerator files. Has no effect if 
# ProeGenerateAcceleratorFiles is set to False.
ProeAcceleratorFilesMandatory = True