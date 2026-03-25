#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import pathlib

from cdb import misc
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
    base = (pathlib.Path(__file__).parent / "ctes").resolve()
    fpath = misc.jail_filename(base, fname)

    with open(fpath, "r", encoding="utf-8") as sqlf:
        return sqlf.read()
