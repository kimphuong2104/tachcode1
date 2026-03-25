#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id$"

import os

from cdb import misc, sqlapi
from cdb.lru_cache import lru_cache


@lru_cache(maxsize=20, clear_after_ue=False)
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

    with open(fpath, "r", encoding="utf8") as sqlf:
        return sqlf.read()


def get_query_pattern(pattern, loader=None):
    """
    :param pattern: File name prefix of an existing SQL pattern file.
    :type pattern: str

    :param loader: Function to load an SQL pattern from a filepath.
        Defaults to `load_query_pattern`.
    :type loader: function

    :returns: The query_pattern to resolve a project structure.
    :rtype: str

    :raises UnboundLocalError: if not run on a supported dbms
        (currently mssql, oracle, sqlite, postgres).
    """
    if loader is None:
        loader = load_query_pattern

    dbms = sqlapi.SQLdbms()

    if dbms == sqlapi.DBMS_MSSQL:
        from cdb.mssql import CollationDefault

        raw_pattern = loader(f"{pattern}_mssql.sql")
        return raw_pattern.format(
            collation=CollationDefault.get_default_collation(),
        )

    elif dbms == sqlapi.DBMS_SQLITE:
        dbms_name = "sqlite"

    elif dbms == sqlapi.DBMS_ORACLE:
        dbms_name = "oracle"

    elif dbms == sqlapi.DBMS_POSTGRES:
        dbms_name = "postgres"

    return loader(f"{pattern}_{dbms_name}.sql")
