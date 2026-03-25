#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
"""
Module __init__

This is the documentation for the __init__ module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
from cdb.sqlapi import NULL
from cs.metrics.qualitycharacteristics import QCDefinition


class SetObjektart(object):
    """ Fix for E026810:
        Set the attribute cdb_objektart for the existing QCDefinitions.
        For the new ones the attribute is set in the creation mask.
    """

    def run(self):
        condition = (QCDefinition.cdb_objektart == '') | (QCDefinition.cdb_objektart == NULL)
        qcdefs = QCDefinition.Query(condition)

        qcdefs.Update(cdb_objektart="cdbqc_definition")

pre = []
post = [SetObjektart]


if __name__ == "__main__":
    SetObjektart().run()
