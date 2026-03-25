#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#

import logging
import six
import sys

from cdb.objects.cdb_filetype import CDB_FileType


use_pkg_resources = False
try:
    if sys.version_info >= (3, 8):
        from importlib import metadata as importlib_metadata
    else:
        import importlib_metadata
except ImportError:
    use_pkg_resources = True
    import pkg_resources


_cad_file_types = set()
_office_apps = [
    u"MS-Excel",
    u"MS-Excel:XLSB",
    u"MS-Excel:XLSM",
    u"MS-Excel:XLSX",
    u"MS-Outlook",
    u"MS-PowerPoint",
    u"MS-PowerPoint:PPTM",
    u"MS-PowerPoint:PPTX",
    u"MS-Project",
    u"MS-Word",
    u"MS-Word:DOCM",
    u"MS-Word:DOCX",
    u"MS-Visio",
    u"MS-Visio:VSDX",
]


def _collect_acs_file_types_from_acs_entry_point():
    """
    Collect all file types from module names, that are registered via ACS.

    Might return Office apps.

    :return: A set of file types.
    :rtype: set
    """
    acs_file_types = set()
    module_names = set()
    ACS_PLUGIN_ENTRY_POINT_GROUP = "cs.acs.plugins"
    if use_pkg_resources:
        entry_points = pkg_resources.iter_entry_points(
            group=ACS_PLUGIN_ENTRY_POINT_GROUP
        )
    else:
        entry_points = importlib_metadata.entry_points().get(
            ACS_PLUGIN_ENTRY_POINT_GROUP, []
        )
    for ep in entry_points:
        try:
            ep.load()
            if use_pkg_resources:
                module_names.add(".".join(ep.module_name.split(".")[:2]))
            else:
                module_names.add(".".join(ep.module.split(".")[:2]))
            f_types = CDB_FileType.KeywordQuery(cdb_module_id=module_names)
            filetypes_for_cad = set([ft.ft_name for ft in f_types])
            acs_file_types.update(filetypes_for_cad)
        except Exception as e:
            logging.exception("Loading entry point failed for %s" % ep.name)
    acs_file_types = acs_file_types - set(_office_apps)
    return acs_file_types


def _collect_cad_file_types_from_workspaces_entry_point():
    cad_file_types = set()
    WORKSPACES_CADFILETYPES_ENTRY_POINT_GROUP = "cs.workspaces.cadfiletypes"
    if use_pkg_resources:
        entry_points = pkg_resources.iter_entry_points(
            group=WORKSPACES_CADFILETYPES_ENTRY_POINT_GROUP
        )
    else:
        entry_points = importlib_metadata.entry_points().get(
            WORKSPACES_CADFILETYPES_ENTRY_POINT_GROUP, []
        )
    for ep in entry_points:
        try:
            func = ep.load()
            filetypes_for_cad = func()
            cad_file_types.update(filetypes_for_cad)
        except Exception as e:
            logging.exception("Loading entry point failed for %s" % ep.name)
    return cad_file_types


def collect_cad_file_types():
    global _cad_file_types
    cad_file_types = _collect_acs_file_types_from_acs_entry_point()
    cad_file_types.update(_collect_cad_file_types_from_workspaces_entry_point())

    _cad_file_types = cad_file_types


def get_cad_file_types():
    return _cad_file_types
