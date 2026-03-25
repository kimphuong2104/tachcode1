from cdb import sqlapi
from cdb.ddl import Table
from cdb.comparch import protocol


class UpdateDocTemplateRelations(object):
    def run(self):
        tmpl_tables = [
            "cdbpcs_task2doctmpl",
            "cdbpcs_prj2doctmpl",
            "cdbpcs_cl2doctmpl",
            "cdbpcs_cli2doctmpl",
        ]
        for t in tmpl_tables:
            table = Table(t)
            if table.hasColumn("use_selected_index"):
                # Nothing to do here, when updating from cs.pcs < 15.4.1 to >= 15.7.1
                # Initializing is done in cs.pcs.projects_documents.updates.v15_7_1.UpdateDocTemplateColumns
                sqls = f"{t} set use_selected_index=1"
                cnt = sqlapi.SQLupdate(sqls)
                protocol.logMessage(f"{t}: {cnt} record(s) updated.")
            else:
                protocol.logMessage(
                    (
                        f"{t}: does not contain the attribute 'use_selected_index'. "
                        "Feature will be initialized by 15.7.1 update task."
                    )
                )


post = [UpdateDocTemplateRelations]
