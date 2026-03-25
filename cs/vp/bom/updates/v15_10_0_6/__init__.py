# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import ddl
from cdb import transactions


class RemoveNotNullConstraint(object):

    def run(self):
        """
        Removes the NOT NULL constraints from the columns in the bom_item_occurrence schema that were
        previously used for the primary key but are now unused. This ensures dependents (e.g. cs.bomcreator)
        can insert bom_item_occurrences in updated instances even if the columns were not removed by the
        administrator.
        """
        column_names = [
            'baugruppe',
            'b_index',
            'teilenummer',
            't_index',
            'position',
            'variante',
            'auswahlmenge'
        ]
        with transactions.Transaction():
            table = ddl.Table('bom_item_occurrence')
            for col_name in column_names:
                if not table.hasColumn(col_name):
                    continue

                column: ddl.ColumnBase = table.getColumn(col_name)
                column.notnull = 0
                table.modifyAttributes(column)


pre = []
post = [RemoveNotNullConstraint]
