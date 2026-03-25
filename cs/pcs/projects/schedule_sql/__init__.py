#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id$"

import os

from cdb import misc
from cdb.lru_cache import lru_cache


@lru_cache(maxsize=20, clear_after_ue=False)
def load_query_pattern(fname):
    """
    :param fname: The filename relative to this file's path.
    :type fname: unicode

    :returns: Contents of the file `fname`, `None` if it does not exist.

    :raises RuntimeError: if `fname` tries to escape this file's path.
    :raises: if `fname` does not exist or is not readable.
    """
    base = os.path.abspath(os.path.dirname(__file__))
    fpath = misc.jail_filename(base, fname)

    if not os.path.isfile(fpath):
        return None

    with open(fpath, "r", encoding="utf8") as sqlf:
        return sqlf.read()


def get_query_pattern(pattern):
    """
    :param pattern: File name prefix of an existing SQL pattern file.
    :type pattern: str

    :returns: The query_pattern to resolve a project structure.
    :rtype: str
    """
    result = load_query_pattern(f"{pattern}.sql")
    return result
