#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import ddl, sqlapi
from cdb.comparch import protocol


class UpdateChecklistID(object):
    def run(self):
        try:
            t = ddl.Table("cdbpcs_part2cl")
            col = t.getColumn("checklist_id")
            t.dropPrimaryKey()

            col2 = ddl.Integer(
                colname="checklist_id2",
                notnull=0,
                comment=col.comment,
                default=col.default,
            )
            t.addAttributes(col2)
            sqlapi.SQL("UPDATE cdbpcs_part2cl SET checklist_id2 = checklist_id")
            t.dropAttributes(col)

            col = ddl.Integer(
                colname="checklist_id",
                notnull=0,
                comment=col.comment,
                default=col.default,
            )
            t.addAttributes(col)
            sqlapi.SQL("UPDATE cdbpcs_part2cl SET checklist_id = checklist_id2")
            t.dropAttributes(col2)

            col.notnull = 1
            t.modifyAttributes(col)

            pk = ddl.PrimaryKey(
                "teilenummer", "t_index", "cdb_project_id", "checklist_id"
            )
            t.setPrimaryKey(pk)
        except Exception as e:
            protocol.logWarning(
                msg="Table 'cdbpcs_part2cl' could not be altered.", details_longtext=e
            )
            raise e


pre = [UpdateChecklistID]
post = []
