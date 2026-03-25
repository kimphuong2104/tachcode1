#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import

from cdb.objects import Object


class Cdb_file_wsm(Object):
    """
    Contains Workspaces-specific information about cdb_file entries
    """

    __maps_to__ = "cdb_file_wsm"
