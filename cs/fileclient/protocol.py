#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import unicode_literals

import json


class FileClientProtocol(object):
    """
    The protocol that gets downloaded by the File Client as a JSON file
    when opening the File Client via 'cdbf://../protocol_file/..' link.
    """

    def __init__(self):
        self.entries = []

    def add_file_entry(self, filename, link, mode, open_file):
        entry = FileClientProtocolFileEntry(filename, link, mode, open_file)
        self.entries.append(entry)

    def to_json(self):
        return json.dumps(self.entries, default=vars)


class FileClientProtocolFileEntry(object):

    def __init__(self, filename, link, mode, open_file):
        """
        :param filename: The external filename
        :type filename: string
        :param link: URL to a cdb_file object (presigned blob URLs are supported)
        :type link: string
        :param mode: The targeted action for the File Client (currently only support for "view")
        :type mode: string
        :param open_file: The external filename
        :type open_file: bool
        """
        self.entry_type = "file"
        self.filename = filename
        self.link = link
        self.mode = mode
        self.open_file = open_file
