#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Provider to add a column with the count of attached files to a table
"""

from __future__ import absolute_import
__revision__ = "$Id$"

from collections import Counter

from cdb import util
from cdb.typeconversion import to_untyped_c_api
from cdb.objects.cdb_file import CDB_File
from cdb.platform.gui import PythonColumnProvider


class FileCounter(PythonColumnProvider):

    @staticmethod
    def getColumnDefinitions(classname, query_args):
        return [{'column_id': 'num_files',
                 'label': util.get_label('csweb_has_files'),
                 'data_type': 'integer'}]

    @staticmethod
    def getColumnData(classname, table_data):
        object_ids = [data['cdb_object_id'] for data in table_data]
        files = CDB_File.Query(CDB_File.cdbf_object_id.one_of(*object_ids), access='read')
        counts = Counter([f.cdbf_object_id for f in files])
        return [
            {"num_files": to_untyped_c_api(counts[data['cdb_object_id']])}
            for data in table_data
        ]

    @staticmethod
    def getRequiredColumns(classname, available_columns):
        return ['cdb_object_id']
