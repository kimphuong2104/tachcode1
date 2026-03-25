from cdb import cdbuuid
from cdb.sqlapi import NULL

from cs.pcs.checklists import ChecklistItem


class SetObjectID:
    def run(self):
        condition = (ChecklistItem.cdb_object_id == "") | (
            ChecklistItem.cdb_object_id == NULL
        )
        cis = ChecklistItem.Query(condition)

        for ci in cis:
            ci.cdb_object_id = cdbuuid.create_uuid()


pre = []
post = [SetObjectID]
