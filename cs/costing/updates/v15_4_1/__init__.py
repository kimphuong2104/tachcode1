#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import

from cdb import util
from cdb import sqlapi
from cdb.comparch import protocol


class InitSortOrderOfClones(object):
    def run(self):
        protocol.logMessage("Initialize Sorting Order with ''")
        sqlapi.SQLupdate(
            "cdbpco_comp2component SET sort_order = 0 "
            "WHERE sort_order IS NULL"
        )
        sqlapi.SQLupdate(
            "cdbpco_component SET sort_order = 0 "
            "WHERE sort_order IS NULL"
        )


pre = []
post = [InitSortOrderOfClones]
