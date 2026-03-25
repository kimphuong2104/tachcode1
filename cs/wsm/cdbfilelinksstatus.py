#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import

from cdb.objects import Object


class Cdb_file_links_status(Object):
    """
    Contains information about specific CAD links contained in a file.
    """

    __maps_to__ = "cdb_file_links_status"
