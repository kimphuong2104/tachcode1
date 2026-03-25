# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2015 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module catialicense

This is the documentation for the selicense module.
Extension for Checkin BOM-Extraction license for this system.
"""

from __future__ import absolute_import
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
from cdb import sig

# Exported objects
__all__ = []


@sig.connect("check_bom_extract_license")
def checkCadBOMLicense(doc):
    return False


# Guard importing as main module
if __name__ == "__main__":
    pass
