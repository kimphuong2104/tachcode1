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
from cdb import cdbuuid
from cdb.sqlapi import NULL
from cs.metrics.qualitycharacteristics import GroupingValue


class SetObjectID(object):
    """ Fix for E024473:
        Set the cdb_object_id for the existing grouping values.
    """

    def run(self):
        condition = (GroupingValue.cdb_object_id == '') | (GroupingValue.cdb_object_id == NULL)
        gvs = GroupingValue.Query(condition)

        for gv in gvs:
            gv.cdb_object_id = cdbuuid.create_uuid()

pre = []
post = [SetObjectID]


if __name__ == "__main__":
    SetObjectID().run()
