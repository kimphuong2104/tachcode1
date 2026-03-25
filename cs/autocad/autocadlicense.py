# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module autoacadlicense

This is the documentation for the selicense module.
Extension for Checkin BOM-Extraction license for this system.
"""

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
from cdb import fls
from cdb import sig

# Exported objects
__all__ = []

BOM_LIC = "AUTOCAD_002"
BOMLICSYSTEMS = set(["acad"])


@sig.connect("check_bom_extract_license")
def checkCadBOMLicense(doc):
    # return None  # not responsible
    # return True  # license granted
    # return False # license denied
    ret = None
    erzeug_system = doc.erzeug_system
    if erzeug_system:
        main_system = erzeug_system.split(":")[0]
        if main_system in BOMLICSYSTEMS:
            ret = fls.get_license(BOM_LIC)
    return ret
