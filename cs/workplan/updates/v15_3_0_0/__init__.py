# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


from cdb import sqlapi
from cdb import ddl
from cdb import transactions
from cdb import util


class UpdateBOMItemAssignments(object):
    """
    Changes the assignment of bom items to tasks from old bom_item primary keys
    (teilenummer, t_index, baugruppe, b_index, position, auswahlmenge, variante) to cdb_object_id.
    """

    def run(self):
        req_columns = ["assembly", "assembly_index", "part_id", "part_index", "variant", "bom_pos", "selected_quantity", "bom_item_object_id"]
        for col in req_columns:
            if not util.column_exists("cswp_task2input_parts", col):
                return

        with transactions.Transaction():
            bom_item_select = "SELECT einzelteile.cdb_object_id " \
                              "FROM einzelteile " \
                              "WHERE einzelteile.baugruppe=cswp_task2input_parts.assembly " \
                              "AND einzelteile.b_index=cswp_task2input_parts.assembly_index " \
                              "AND einzelteile.teilenummer=cswp_task2input_parts.part_id " \
                              "AND einzelteile.t_index=cswp_task2input_parts.part_index " \
                              "AND einzelteile.variante=cswp_task2input_parts.variant " \
                              "AND einzelteile.position=cswp_task2input_parts.bom_pos " \
                              "AND einzelteile.auswahlmenge=cswp_task2input_parts.selected_quantity"

            # check for broken references
            sel_stmt = "count(*) from cswp_task2input_parts " \
                   "where not exists (%s) " % bom_item_select
            t = sqlapi.SQLselect(sel_stmt)

            # copy broken references to a backup table and delete them
            if sqlapi.SQLinteger(t, 0, 0) > 0:
                backup_rel = "cswp_task_broken_bom_refs_bac"
                try:
                    util.tables[backup_rel]
                except KeyError:
                    orig_table = ddl.Table("cswp_task2input_parts")
                    orig_table.reflect()
                    backup_table = ddl.Table(backup_rel, *orig_table.props)
                    backup_table.create()
                insert_stmt = "into %s select * from cswp_task2input_parts where not exists (%s)" % \
                              (backup_rel, bom_item_select)
                sqlapi.SQLinsert(insert_stmt)
                del_stmt = "from cswp_task2input_parts where not exists (%s)" % bom_item_select
                sqlapi.SQLdelete(del_stmt)

            # fill bom_item_object_id
            upd_stmt = "cswp_task2input_parts " \
                   "SET bom_item_object_id=(%s) " \
                   "WHERE bom_item_object_id IS NULL" % bom_item_select
            sqlapi.SQLupdate(upd_stmt)



class RemoveNotNullConstraint(object):

    def run(self):
        """
        Removes the NOT NULL constraints from deprecated columns. See also update task UpdateBOMItemAssignments above.
        """
        column_names = [
            'part_id',
            'part_index',
            'assembly',
            'assembly_index',
            'variant',
            'selected_quantity',
            'bom_pos'
        ]
        with transactions.Transaction():
            table = ddl.Table('cswp_task2input_parts')
            for col_name in column_names:
                if not table.hasColumn(col_name):
                    continue

                column = table.getColumn(col_name)
                column.notnull = 0
                table.modifyAttributes(column)


pre = []
post = [UpdateBOMItemAssignments, RemoveNotNullConstraint]
