#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import sqlapi
from cdb.comparch import protocol


class UpdateStatusTexts(object):
    __renamed__ = [
        {"status": 10, "olc": "cdbwf_task", "table": "cdbwf_task"},
        {"status": 35, "olc": "cdbwf_task", "table": "cdbwf_task"},
        {"status": 10, "olc": "cdbwf_aggregate", "table": "cdbwf_task"},
        {"status": 35, "olc": "cdbwf_aggregate", "table": "cdbwf_task"},
        {"status": 30, "olc": "cdbwf_process", "table": "cdbwf_process"},
    ]

    def run(self):
        for vals in self.__renamed__:
            self._update_status(vals)

    def _update_status(self, vals):
        config = sqlapi.RecordSet2("objektstati",
                                   "objektart='{olc}' AND "
                                   "statusnummer={status}".format(**vals))
        vals["name"] = config[0].statusbezeich

        rows = sqlapi.SQLupdate("{table} SET cdb_status_txt='{name}' "
                                "WHERE status={status} AND "
                                "cdb_status_txt!='{name}' AND "
                                "cdb_objektart='{olc}'".format(**vals))

        protocol.logMessage(
            "updated {rows} rows in {vals[olc]} to {vals[name]}".format(
                rows=rows, vals=vals))


pre = []
post = [UpdateStatusTexts]
