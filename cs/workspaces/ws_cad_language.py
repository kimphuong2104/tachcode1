#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

from cdb.objects import Object
from cdb.objects import Reference_N
from cdb.objects import Forward
from cdb.objects.cdb_file import CDB_File

fWsCadLanguage = Forward("cs.workspaces.ws_cad_language.WsCadLanguage")


class WsCadLanguage(Object):
    """
    A container for languages files for Workspaces CAD integrations.
    """

    __maps_to__ = "ws_cad_language"
    __classname__ = "ws_cad_language"

    Files = Reference_N(
        CDB_File, CDB_File.cdbf_object_id == fWsCadLanguage.cdb_object_id
    )
