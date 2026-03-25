# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import sqlapi
from cdb import ddl
from cdb import transactions
from cdb import util

from cdb.platform import PropertyValue


class UpdateBomItemOccurrence(object):

    def run(self):
        """
        UPDATE bompos_object_id
        """
        req_columns = ["baugruppe", "b_index", "teilenummer", "t_index", "variante", "position", "auswahlmenge",
                       "bompos_object_id"]
        for col in req_columns:
            if not util.column_exists("bom_item_occurrence", col):
                return

        with transactions.Transaction():
            bom_item_select = "SELECT einzelteile.cdb_object_id " \
                              "FROM einzelteile " \
                              "WHERE einzelteile.baugruppe=bom_item_occurrence.baugruppe " \
                              "AND einzelteile.b_index=bom_item_occurrence.b_index " \
                              "AND einzelteile.teilenummer=bom_item_occurrence.teilenummer " \
                              "AND einzelteile.t_index=bom_item_occurrence.t_index " \
                              "AND einzelteile.variante=bom_item_occurrence.variante " \
                              "AND einzelteile.position=bom_item_occurrence.position " \
                              "AND einzelteile.auswahlmenge=bom_item_occurrence.auswahlmenge"

            # check for broken references
            sel_stmt = "count(*) from bom_item_occurrence " \
                       "where not exists (%s) " % bom_item_select
            t = sqlapi.SQLselect(sel_stmt)

            # copy broken references to a backup table and delete them
            if sqlapi.SQLinteger(t, 0, 0) > 0:
                backup_rel = "bom_item_occ_broken_refs_bac"
                try:
                    util.tables[backup_rel]
                except KeyError:
                    orig_table = ddl.Table("bom_item_occurrence")
                    orig_table.reflect()
                    backup_table = ddl.Table(backup_rel, *orig_table.props)
                    backup_table.create()
                insert_stmt = "into %s select * from bom_item_occurrence where not exists (%s)" % \
                              (backup_rel, bom_item_select)
                sqlapi.SQLinsert(insert_stmt)
                del_stmt = "from bom_item_occurrence where not exists (%s)" % bom_item_select
                sqlapi.SQLdelete(del_stmt)

            # fill bompos_object_id
            upd_stmt = "bom_item_occurrence " \
                       "SET bompos_object_id=(%s) " % bom_item_select
            sqlapi.SQLupdate(upd_stmt)


class UpdateIsImprecise(object):

    def run(self):
        """
        UPDATE is_imprecise for bom_item
        """

        sqlapi.SQLupdate("einzelteile SET is_imprecise=0 WHERE is_imprecise is NULL")


class UpdateBomi(object):

    def run(self):
        """
        UPDATE property bomi to precise
        """

        prop_value = PropertyValue.KeywordQuery(
            attr="bomi",
            subject_type="Common Role",
            subject_id="public",
            cdb_module_id="cs.vp.bom"
        )
        prop_value[0].value = "precise"


pre = []
post = [UpdateBomItemOccurrence, UpdateIsImprecise, UpdateBomi]

if __name__ == "__main__":
    UpdateBomItemOccurrence().run()
    UpdateIsImprecise().run()
    UpdateBomi().run()
