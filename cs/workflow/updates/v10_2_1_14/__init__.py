#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from cdb import sqlapi

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class InitializeObjectLifecycle(object):
    "Initialize cdbwf_process.cdb_objektart (mostly relevant for templates)"
    def run(self):
        sqlapi.SQLupdate(
            "cdbwf_process SET cdb_objektart='cdbwf_process_template' "
            "WHERE is_template=1 AND "
            "(cdb_objektart IS NULL OR cdb_objektart='')")
        sqlapi.SQLupdate(
            "cdbwf_process SET cdb_objektart='cdbwf_process' "
            "WHERE is_template=0 "
            "AND (cdb_objektart IS NULL OR cdb_objektart='')")


pre = []
post = [InitializeObjectLifecycle]


# Guard importing as main module
if __name__ == "__main__":
    InitializeObjectLifecycle().run()
