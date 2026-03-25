#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import

from cdb import ddl
from cdb import util
from cdb import sqlapi
from cdb.comparch import protocol


def get_lpad_cond(table_name, target_col, source_col):
    """
    Returns a condition that can be used to initialize `target_col` from
    `source_col` in table `table_name` by using the old value and prepending
    ``0`` chars. We need to prepend 0 because we change the key from int to
    char and the new key should stay sortable.
    """
    clen = util.tables[table_name].column(target_col).length()
    if sqlapi.SQLdbms() == sqlapi.DBMS_SQLITE:
        pre = "0" * clen
        return "substr('%s' || %s, %d, %d)" % (pre, source_col, -clen, clen)
    elif sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
        return "RIGHT(REPLICATE('0', %d) + LTRIM(STR(%s)), %d)" % (clen,
                                                                   source_col,
                                                                   clen)
    else:
        return "LPAD(%s, %d, '0')" % (source_col, clen)


class InitSortableIDForCdbpco_calculation_statiprot(object):
    """
    Initializes the new primary key ``cdbpco_calculation_statiprot.cdbprot_sortable_id``.
    """
    def run(self):
        if not util.column_exists("cdbpco_calculation_statiprot", "cdbprot_zaehler"):
            protocol.logMessage("No need to migrate protocol ==> no cdbprot_zaehler")
            return

        # First we initialize the new key
        new_value = get_lpad_cond("cdbpco_calculation_statiprot",
                                  "cdbprot_sortable_id",
                                  "cdbprot_zaehler")
        sqlapi.SQLupdate("cdbpco_calculation_statiprot SET cdbprot_sortable_id = %s WHERE cdbprot_sortable_id IS NULL OR cdbprot_sortable_id = ''" % new_value)

        # Try to change the PK
        t = ddl.Table("cdbpco_calculation_statiprot")
        t.setPrimaryKey(ddl.PrimaryKey("cdbprot_sortable_id"))
        t.dropAttributes("cdbprot_zaehler")
        sqlapi.SQLdelete("FROM cdb_counter WHERE counter_name = 'cdbpco_calculation_statiprot'")


pre = [InitSortableIDForCdbpco_calculation_statiprot]
post = []
