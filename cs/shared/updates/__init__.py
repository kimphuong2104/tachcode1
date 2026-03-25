#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import
__revision__ = "$Id$"

from cdb import sqlapi
from cdb.comparch import protocol


class MigrateEmailNotification(object):
    __setting__ = "user.email_with_task"
    __vals__ = {
        "setting_id2": "",
        "value": "1",
        "cdb_classname": "cdb_usr_setting",
    }

    def run(self):
        rset = sqlapi.RecordSet2(sql="SELECT personalnummer FROM angestellter "
                                     "WHERE email_with_task>0")
        for rec in iter(rset):
            vals = dict(self.__vals__)
            vals.update({"personalnummer": rec.personalnummer,
                         "setting_id": self.__setting__})
            sqlapi.Record("cdb_usr_setting", **vals).insert()

        protocol.logMessage("Migrated %i users' notification settings from "
                            "angestellter.email_with_task to cdb_usr_setting"
                            % len(rset))


post = [MigrateEmailNotification]


if __name__ == "__main__":
    MigrateEmailNotification().run()
