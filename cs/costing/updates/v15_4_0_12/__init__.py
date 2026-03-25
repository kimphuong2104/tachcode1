#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import

from cdb import util
from cdb import sqlapi
from cdb.comparch import protocol


class UpddateMachineDB(object):
    def run(self):
        protocol.logMessage("Updating MachineDB IDs....")
        rs = sqlapi.RecordSet2("cdbpco_machine_db", "m_id IS NULL")
        for r in rs:
            r.update(m_id=util.nextval('cdbpco_machine_db'))


pre = []
post = [UpddateMachineDB]
