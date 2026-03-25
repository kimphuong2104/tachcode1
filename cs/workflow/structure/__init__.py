#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id$"

import os
from cdb import misc
from cdb import sqlapi


def load_query_pattern(fname):
    """
    :param fname: The filename relative to this file's path.
    :type fname: unicode

    :returns: Contents of the file `fname`.

    :raises RuntimeError: if `fname` tries to escape this file's path.
    :raises: if `fname` does not exist or is not readable.
    """
    base = os.path.abspath(os.path.dirname(__file__))
    fpath = misc.jail_filename(base, fname)

    with open(fpath, "r") as sqlf:
        return sqlf.read()


def get_query_pattern(pattern):
    """
    :param pattern: File name prefix of an existing SQL pattern file.
    :type pattern: str

    :returns: The query_pattern to resolve a project structure.
    :rtype: str

    :raises UnboundLocalError: if not run on a supported dbms
        (currently mssql, oracle, sqlite).
    """
    dbms = sqlapi.SQLdbms()

    if dbms == sqlapi.DBMS_MSSQL:
        from cdb.mssql import CollationDefault
        raw_pattern = load_query_pattern("{}_mssql.sql".format(pattern))
        return raw_pattern.format(
            collation=CollationDefault.get_default_collation(),
        )

    elif dbms == sqlapi.DBMS_SQLITE:
        dbms_name = "sqlite"

    elif dbms == sqlapi.DBMS_ORACLE:
        dbms_name = "oracle"

    elif dbms == sqlapi.DBMS_POSTGRES:
        dbms_name = "postgres"

    return load_query_pattern("{}_{}.sql".format(pattern, dbms_name))
