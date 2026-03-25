#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import pathlib

from cdb import CADDOK, cdbuuid, imex, sqlapi
from cdb.comparch import protocol
from cdb.ddl import Table
from cs.pcs.resources import db_tools


def export_data(name, control_lines):
    export_file = pathlib.Path(
        CADDOK.TMPDIR,
        f"resources15.5.0-{name}-{cdbuuid.create_uuid()}.exp"
    ).resolve()

    try:
        imex.export(
            ignore_errors=False,
            control_file=None,
            control_lines=control_lines,
            output_file=export_file,
        )
    except Exception as e:
        protocol.logError(
            "Backup failed:\n\n"
            f"{e}"
            "\n\naborting"
        )
        raise

    return export_file


class RemovePredefinedFields(object):
    def run(self):
        oldFields = [
            {
                "table": "cdbpcs_resource",
                "fields": ["name", "capacity", "calendar_profile_id"],
            },
            {"table": "cdbpcs_pool_assignment", "fields": ["capacity"]},
        ]

        export_file = export_data("predefined-fields", [
            "* FROM {}".format(oldFields[0]["table"]),
            "* FROM {}".format(oldFields[1]["table"]),
        ])
        protocol.logMessage(
            "Exported the tables"
            f" {oldFields[0]['table']}, {oldFields[1]['table']}"
            f" to {export_file}"
        )

        for oldField in oldFields:
            table = Table(oldField["table"])
            for field in oldField["fields"]:
                if table.hasColumn(field):
                    table.dropAttributes(field)
                    protocol.logMessage(
                        "'{0}' dropped from {1}".format(field, oldField["table"])
                    )


class UpdateClassName:
    def run(self):
        combined = set()
        standalone = set()
        self.oor = db_tools.OneOfReduced("cdbpcs_resource_schedule_v")

        schedules_sql = """
        SELECT
            r.cdb_object_id, tr.time_schedule_oid
        FROM
            cdbpcs_resource_schedule r
        LEFT JOIN
            cdbpcs_time2res_schedule tr
        ON r.cdb_object_id = tr.resource_schedule_oid
        """

        for schedule in sqlapi.RecordSet2(sql=schedules_sql):
            uuid = schedule['cdb_object_id']
            if schedule['time_schedule_oid']:
                combined.add(uuid)
            else:
                standalone.add(uuid)

        self.updateCombined(combined)
        self.updateStandalone(standalone)

    def updateCombined(self, combined):
        in_clause = self.oor.get_expression('cdb_object_id', combined)
        sqlapi.SQLupdate(
            f"""
                cdbpcs_resource_schedule
            SET
                cdb_classname = 'cdbpcs_resource_schedule_time'
            WHERE
                {in_clause}
            """
        )

    def updateStandalone(self, standalone):
        in_clause = self.oor.get_expression('cdb_object_id', standalone)
        sqlapi.SQLupdate(
            f"""
                cdbpcs_resource_schedule
            SET
                cdb_classname = 'cdbpcs_resource_schedule'
            WHERE
                {in_clause}
            """
        )


class RemoveWebLibraryDependency:
    def run(self):
        table = "csweb_library_dependencies"
        library_name = "cs-pcs-projects-web"
        dependency = "cs-pcs-resources-web"
        sqlapi.SQLdelete(
            f"FROM {table} WHERE library_name =  '{library_name}'"
            f"AND library_name_dependency = '{dependency}'"
        )


class RemoveUnsupportedScheduleElements:
    def run(self):
        standalone, query_standalone, query_combined = self.load_schedules()
        self.migrate_standalone_schedules(standalone, query_standalone)
        self.migrate_combined_schedules(query_combined)

    POOL_REF_CLASSES = {"cdb_org": "cdb_organization"}
    SCHEDULES = """
        SELECT
            rs.cdb_object_id,
            rp.pool_oid,
            o.relation,
            ts.time_schedule_oid

        FROM cdbpcs_resource_schedule rs

        LEFT JOIN cdbpcs_pool2res_schedule rp
            ON rs.cdb_object_id = rp.resource_schedule_oid

        LEFT JOIN cdb_object o
            ON rp.pool_oid = o.id

        LEFT JOIN cdbpcs_time2res_schedule ts
            ON rs.cdb_object_id = ts.resource_schedule_oid
    """

    def load_schedules(self):
        standalone = {}
        combined = set()
        visited = set()

        for schedule in sqlapi.RecordSet2(sql=self.SCHEDULES):
            uuid = schedule["cdb_object_id"]

            if uuid in visited:
                protocol.logError(
                    f"ignoring invalid resource schedule '{uuid}':"
                    f" multiple assignments"
                )
                if uuid in standalone:
                    del standalone[uuid]
                if uuid in combined:
                    combined.remove(uuid)
                continue

            visited.add(uuid)

            pool_oid = schedule["pool_oid"]
            relation = schedule['relation']
            ts_oid = schedule["time_schedule_oid"]

            if bool(pool_oid) == bool(ts_oid):
                protocol.logError(
                    f"ignoring invalid resource schedule '{uuid}':"
                    f"\n    {relation} '{pool_oid}'"
                    f"\n    cdbpcs_time_schedule '{ts_oid}'"
                )
                continue

            if pool_oid:
                classname = self.POOL_REF_CLASSES.get(relation, relation)
                standalone[uuid] = (schedule["pool_oid"], classname)
            elif ts_oid:
                combined.add(uuid)

        oor = db_tools.OneOfReduced(table_name="cdbpcs_rs_content")
        query_standalone = oor.get_expression(
            column_name="view_oid",
            values=standalone.keys(),
        )
        query_combined = oor.get_expression(
            column_name="view_oid",
            values=combined,
        )
        return standalone, query_standalone, query_combined

    def migrate_standalone_schedules(self, standalone, query_standalone):
        """
        Make sure standalone schedules are consistent:

        1. clears all elements assigned to standalone schedules
        2. adds the one context object element per standalone schedule (resource pool or organization)

        Note that invalid schedules (assigned to more than one context object) are ignored.
        """
        sqlapi.SQLdelete(f"FROM cdbpcs_rs_content WHERE {query_standalone}")
        for view_oid, (content_oid, classname) in standalone.items():
            sqlapi.Record(
                "cdbpcs_rs_content",
                position=10,
                view_oid=view_oid,
                content_oid=content_oid,
                cdb_content_classname=classname,
            ).insert()

    def migrate_combined_schedules(self, query_combined):
        """
        Make sure combined schedules only contain supported elements by
        removing all elements assigned to combined schedules of types
        that are now unsupported (everything but resource pools and resources).

        Note that invalid schedules (assigned to more than one context object) are ignored.
        """
        sqlapi.SQLdelete(
            f"FROM cdbpcs_rs_content "
            f"WHERE {query_combined} "
            f"AND cdb_content_classname NOT IN ('cdbpcs_pool_assignment', 'cdbpcs_resource_pool')"
        )


pre = [RemovePredefinedFields, UpdateClassName]
post = [RemoveWebLibraryDependency, RemoveUnsupportedScheduleElements]
