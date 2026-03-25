#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

# pylint: disable=bad-continuation


from cdb import ddl, sqlapi


class UpdateDocStatiProtDeletedFlag(object):
    """
    Initialize ``cdb_z_statiprot.cdbprot_removed``
    """

    def run(self):  # pylint: disable=no-self-use
        t = ddl.Table("cdb_z_statiprot")
        if (
            t.exists()
            and t.hasColumn("cdbprot_neustat")
            and t.hasColumn("cdbprot_removed")
        ):
            sqlapi.SQLupdate(
                "cdb_z_statiprot set cdbprot_removed = 1 "
                "WHERE cdbprot_neustat = 'removed' AND cdbprot_removed IS NULL"
            )
            sqlapi.SQLupdate(
                "cdb_z_statiprot set cdbprot_removed = 0 WHERE cdbprot_removed IS NULL"
            )


pre = []
post = [UpdateDocStatiProtDeletedFlag]
