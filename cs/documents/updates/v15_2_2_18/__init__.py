#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


from cdb.platform.tools import CDBObjectIDFixer


class AddDatabaseIndexForZeichnungCdb_object_id(object):
    """
    Update task to add a database index for zeichnung.cdb_object_id.
    """

    def run(self):  # pylint: disable=no-self-use
        CDBObjectIDFixer(None).repair_index("zeichnung")


pre = []
post = [AddDatabaseIndexForZeichnungCdb_object_id]
