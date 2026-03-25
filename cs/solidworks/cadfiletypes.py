# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH.
# All rights reserved.
# https://www.contact-software.com/

"""
Module cadfiletypes

This module provides the file types that should be opened
in CAD workspaces
"""

from __future__ import absolute_import

from cdb.objects.cdb_filetype import CDB_FileType

__docformat__ = "restructuredtext en"


def solidworks_cadfiletypes():
    f_types = [
        ft.ft_name
        for ft in CDB_FileType.KeywordQuery(cdb_module_id="cs.solidworks")
        if ft.ft_name.startswith("SolidWorks")
    ]
    return f_types
