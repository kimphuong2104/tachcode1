#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class UpdateConstraintTypes:
    """Corrects the cdbpcs_task.constraint_type values (e.g. from 'ASAP' to '0')"""

    def run(self):
        from cdb import sqlapi

        sqlapi.SQLupdate(
            "cdbpcs_task SET constraint_type = '0' WHERE constraint_type = 'ASAP'"
        )
        sqlapi.SQLupdate(
            "cdbpcs_task SET constraint_type = '1' WHERE constraint_type = 'ALAP'"
        )
        sqlapi.SQLupdate(
            "cdbpcs_task SET constraint_type = '2' WHERE constraint_type = 'MSO'"
        )
        sqlapi.SQLupdate(
            "cdbpcs_task SET constraint_type = '3' WHERE constraint_type = 'MFO'"
        )
        sqlapi.SQLupdate(
            "cdbpcs_task SET constraint_type = '4' WHERE constraint_type = 'SNET'"
        )
        sqlapi.SQLupdate(
            "cdbpcs_task SET constraint_type = '5' WHERE constraint_type = 'SNLT'"
        )
        sqlapi.SQLupdate(
            "cdbpcs_task SET constraint_type = '6' WHERE constraint_type = 'FNET'"
        )
        sqlapi.SQLupdate(
            "cdbpcs_task SET constraint_type = '7' WHERE constraint_type = 'FNLT'"
        )
        if (
            sqlapi.SQLdbms() == sqlapi.DBMS_SQLITE
            or sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL
            or sqlapi.SQLdbms() == sqlapi.DBMS_POSTGRES
        ):
            sqlapi.SQLupdate(
                "cdbpcs_task SET constraint_type = '0' WHERE constraint_type IS NULL OR constraint_type = ''"
            )
        elif sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
            sqlapi.SQLupdate(
                """cdbpcs_task SET constraint_type = '0' WHERE constraint_type
                    IS NULL OR constraint_type = CHR(1)"""
            )


pre = []
post = [UpdateConstraintTypes]

if __name__ == "__main__":
    UpdateConstraintTypes().run()
