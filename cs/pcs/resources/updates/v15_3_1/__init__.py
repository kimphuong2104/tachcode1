#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import sqlapi, transactions, util
from cdb.comparch import protocol

demand_tables = [
    "cdbpcs_prj_demand",
    "cdbpcs_prj_alloc",
    "cdbpcs_res_schedule",
    "cdbpcs_res_sched_pw",
    "cdbpcs_res_sched_pm",
    "cdbpcs_res_sched_pq",
    "cdbpcs_res_sched_ph",
]


assign_tables = [
    "cdbpcs_prj_alloc",
    "cdbpcs_res_schedule",
    "cdbpcs_res_sched_pw",
    "cdbpcs_res_sched_pm",
    "cdbpcs_res_sched_pq",
    "cdbpcs_res_sched_ph",
]


class CheckResourcesPrimaryKeys(object):
    """Check primary keys for table cdbpcs_prj_demand and cdbpcs_prj_alloc.
    Task ID is no longer part of the primary key."""

    def run(self):
        self.checkDemands()
        self.checkAssignments()

    def checkDemands(self):
        sql = """SELECT cdb_project_id, task_id, cdb_demand_id
                  FROM cdbpcs_prj_demand
                  WHERE cdb_demand_id IN (SELECT x.cdb_demand_id
                                          FROM (SELECT cdb_demand_id, count(cdb_demand_id) AS cnt
                                                FROM cdbpcs_prj_demand
                                                GROUP BY cdb_demand_id) x
                                          WHERE x.cnt > 1)"""

        print("Following demand ids are not unique:")
        for rec in sqlapi.RecordSet2(sql=sql):
            print("cdb_demand_id = '{cdb_demand_id}'".format(**rec))

    def checkAssignments(self):
        sql = """SELECT cdb_project_id, task_id, cdb_alloc_id
                  FROM cdbpcs_prj_alloc
                  WHERE cdb_alloc_id IN (SELECT x.cdb_alloc_id
                                         FROM (SELECT cdb_alloc_id, count(cdb_alloc_id) AS cnt
                                               FROM cdbpcs_prj_alloc
                                               GROUP BY cdb_alloc_id) x
                                         WHERE x.cnt > 1)"""

        print("Following assignment ids are not unique:")
        for rec in sqlapi.RecordSet2(sql=sql):
            print("cdb_alloc_id = '{cdb_alloc_id}'".format(**rec))


class AdjustResourcesPrimaryKeys(object):
    """Adjust primary keys for table cdbpcs_prj_demand and cdbpcs_prj_alloc.
    Task ID is no longer part of the primary key."""

    def run(self):
        with transactions.Transaction():
            self.adjustDemands()
            self.adjustAssignments()

    def adjustDemands(self):
        sql = """SELECT cdb_project_id, task_id, cdb_demand_id
                  FROM cdbpcs_prj_demand
                  WHERE cdb_demand_id IN (SELECT x.cdb_demand_id
                                          FROM (SELECT cdb_demand_id, count(cdb_demand_id) AS cnt
                                                FROM cdbpcs_prj_demand
                                                GROUP BY cdb_demand_id) x
                                          WHERE x.cnt > 1)"""
        d = set()
        for rec in sqlapi.RecordSet2(sql=sql):
            new_id = "D" + ("%s" % util.nextval("cdbpcs_prj_demand")).zfill(9)
            d.add((rec, new_id))
            for tab in demand_tables:
                sqlapi.SQLupdate(
                    """{tab} SET cdb_demand_id = '{new_id}'
                                     WHERE cdb_project_id = '{cdb_project_id}'
                                     AND task_id = '{task_id}'
                                     AND cdb_demand_id = '{cdb_demand_id}'
                                     """.format(
                        tab=tab, new_id=new_id, **rec
                    )
                )

        for rec, new_id in d:
            for tab in demand_tables:
                sqlapi.SQLupdate(
                    """cdbpcs_prj_alloc SET cdb_demand_id = '{new_id}'
                                     WHERE cdb_project_id = '{cdb_project_id}'
                                     AND cdb_demand_id = '{cdb_demand_id}'
                                     """.format(
                        new_id=new_id, **rec
                    )
                )

    def adjustAssignments(self):
        sql = """SELECT cdb_project_id, task_id, cdb_alloc_id
                  FROM cdbpcs_prj_alloc
                  WHERE cdb_alloc_id IN (SELECT x.cdb_alloc_id
                                         FROM (SELECT cdb_alloc_id, count(cdb_alloc_id) AS cnt
                                               FROM cdbpcs_prj_alloc
                                               GROUP BY cdb_alloc_id) x
                                         WHERE x.cnt > 1)"""
        for rec in sqlapi.RecordSet2(sql=sql):
            new_id = "A" + ("%s" % util.nextval("cdbpcs_prj_alloc")).zfill(9)
            for tab in assign_tables:
                sqlapi.SQLupdate(
                    """{tab} SET cdb_alloc_id = '{new_id}'
                                     WHERE cdb_project_id = '{cdb_project_id}'
                                     AND task_id = '{task_id}'
                                     AND cdb_alloc_id = '{cdb_alloc_id}'
                                     """.format(
                        tab=tab, new_id=new_id, **rec
                    )
                )


class AdjustDatabaseTableIndex(object):

    database_table = "cdbpcs_res_schedule"

    index_to_drop = [
        ("cdbpcs_res_sched_ph_asgn", "cdbpcs_res_sched_ph", "cdb_alloc_id"),
        ("cdbpcs_res_sched_ph_dem", "cdbpcs_res_sched_ph", "cdb_demand_id"),
        ("cdbpcs_res_sched_pm_asgn", "cdbpcs_res_sched_pm", "cdb_alloc_id"),
        ("cdbpcs_res_sched_pm_dem", "cdbpcs_res_sched_pm", "cdb_demand_id"),
        ("cdbpcs_res_sched_pq_asgn", "cdbpcs_res_sched_pq", "cdb_alloc_id"),
        ("cdbpcs_res_sched_pq_dem", "cdbpcs_res_sched_pq", "cdb_demand_id"),
        ("cdbpcs_res_sched_pw_asgn", "cdbpcs_res_sched_pw", "cdb_alloc_id"),
        ("cdbpcs_res_sched_pw_dem", "cdbpcs_res_sched_pw", "cdb_demand_id"),
    ]

    def run(self):

        for index_name, _, _ in self.index_to_drop:
            try:
                sqlapi.SQL("DROP INDEX {}.{}".format(self.database_table, index_name))
            except Exception as exc:  # pylint: disable=W0703
                msg = "{}.{}: The index could not be deleted. This is fine if it does not exist.".format(
                    self.database_table, index_name
                )
                protocol.logWarning(msg, exc)

        for index_name, table, attr in self.index_to_drop:
            try:
                sql = "CREATE INDEX {index_name} ON {table} (cdb_project_id, task_id, {attr})".format(
                    index_name=index_name, table=table, attr=attr
                )
                sqlapi.SQL(sql)
            except Exception as exc:  # pylint: disable=W0703
                msg = "{}.{}: The index could not be created. This is fine if it already exists.".format(
                    table, index_name
                )
                protocol.logWarning(msg, exc)


class RemoveUnusedResourceDemands(object):
    """Remove resource demands that do not have any allocation to an organization,
    a person, a pool or a resource and therefore should not exist."""

    def run(self):
        with transactions.Transaction():
            protocol.logMessage(
                "Search and remove resources demands without any"
                " connection to resources..."
            )
            demands = sqlapi.RecordSet2(
                "cdbpcs_prj_demand",
                "org_id IS NULL AND subject_id IS NULL"
                " AND pool_oid IS NULL AND resource_oid IS NULL"
                " AND assignment_oid IS NULL",
            )

            for demand in demands:
                msg = "Demand ({cdb_project_id} / {cdb_demand_id} / {task_id}) removed".format(
                    **demand
                )
                protocol.logMessage(msg)

            sqlapi.SQLdelete(
                "FROM cdbpcs_prj_demand"
                " WHERE org_id IS NULL AND subject_id IS NULL"
                " AND pool_oid IS NULL AND resource_oid IS NULL"
                " AND assignment_oid IS NULL"
            )
            protocol.logMessage("Removal of unconnected demands completed.")


class RemoveUnusedResourceAssignments(object):
    """Remove resource assignments that do not have any allocation to an organization,
    a person, a pool or a resource and therefore should not exist."""

    def run(self):
        with transactions.Transaction():
            protocol.logMessage(
                "Search and remove resources assignments without any"
                " connection to resources..."
                ""
            )
            assigns = sqlapi.RecordSet2(
                "cdbpcs_prj_alloc",
                "org_id IS NULL AND persno IS NULL"
                " AND pool_oid IS NULL AND resource_oid IS NULL"
                " AND assignment_oid IS NULL",
            )

            for assign in assigns:
                msg = "Assignments ({cdb_project_id} / {cdb_alloc_id} / {task_id}) removed".format(
                    **assign
                )
                protocol.logMessage(msg)

            sqlapi.SQLdelete(
                "FROM cdbpcs_prj_alloc"
                " WHERE org_id IS NULL AND persno IS NULL"
                " AND pool_oid IS NULL AND resource_oid IS NULL"
                " AND assignment_oid IS NULL"
            )
            protocol.logMessage("Removal of unconnected assignments completed.")


pre = [
    AdjustDatabaseTableIndex,
    RemoveUnusedResourceDemands,
    RemoveUnusedResourceAssignments,
]
post = []
