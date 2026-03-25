#!/usr/bin/env python
# -*- mode: python; coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
Module __init__

This is the documentation for the __init__ module.
"""

from __future__ import absolute_import
from cdb import sqlapi
from cs.tools import semanticlinks


class SetFontDefaultValues(object):
    """ Updates columns 'font_size' and 'font_name' if already available in
        database and NULL values are available in columns.
    """

    def run(self):
        attrs = [("font_size", 9),
                 ("font_name", "'Sans-Serif'")]

        db_type = sqlapi.SQLdbms()
        if db_type == sqlapi.DBMS_MSSQL:
            sql_stmt = ""
            for attr, default in attrs:
                available = semanticlinks.LinkGraphConfig.HasField(attr)
                if available:
                    sql_stmt = ("UPDATE cdb_link_graph_cfg "
                                "SET {attr}={default} "
                                "WHERE {attr} IS NULL").format(attr=attr,
                                                               default=default)
                    sqlapi.SQL(sql_stmt)


pre = []
post = [SetFontDefaultValues]

# Guard importing as main module
if __name__ == "__main__":
    SetFontDefaultValues().run()
