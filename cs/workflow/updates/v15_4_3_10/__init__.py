#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=broad-except

from cdb.comparch import protocol
from cdb import sqlapi


class RemoveReservedByTerms(object):

    def run(self):
        deleted = sqlapi.SQLdelete(
                    "FROM cdb_pyterm"
                    " WHERE attribute = 'reserved_by'"
                    " AND fqpyname ="
                    "'cs.workflow.schemacomponents.SchemaComponent'")
        protocol.logMessage(
            "{} cdb_pyterm entries deleted for 'reserved_by'".format(deleted))

pre = []
post = [RemoveReservedByTerms]
