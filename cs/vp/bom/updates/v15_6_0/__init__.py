# !/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


from cdb import sqlapi

from cdbwrapc import TableInfo


class SetBomType(object):
    """
    Fills in the new column `type_object_id` where the `is_mbom` flag is already set
    """
    def run(self):
        t = TableInfo("teile_stamm")

        if t.exists("is_mbom"):
            # the old column `is_mbom` might not exist in systems that are being updated from a very old version
            # to 15.6.0
            rset = sqlapi.RecordSet2("cdbvp_bom_type", "code='mBOM'")
            assert len(rset) == 1, "Record for BOM type not found"
            type_id = rset[0].cdb_object_id
            sqlapi.SQLupdate("teile_stamm set type_object_id='%s' where is_mbom=1" % type_id)


pre = []
post = [SetBomType]


if __name__ == "__main__":
    SetBomType().run()
