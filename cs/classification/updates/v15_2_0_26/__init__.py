# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import sqlapi


class UpdateCsPopertyIndex(object):

    def run(self):
        try:
            if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE:
                stmt = "ALTER INDEX cs_class_property_code RENAME TO cs_property_code"
            elif sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
                stmt = "DROP INDEX cs_property.cs_class_property_code"
            else:
                stmt = "DROP INDEX cs_class_property_code"
            sqlapi.SQL(stmt)
        except:
            pass

        try:
            if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL or sqlapi.SQLdbms() == sqlapi.DBMS_SQLITE:
                stmt = "CREATE INDEX cs_property_code ON cs_property (code)"
                sqlapi.SQL(stmt)
        except:
            pass


pre = []
post = [UpdateCsPopertyIndex]
