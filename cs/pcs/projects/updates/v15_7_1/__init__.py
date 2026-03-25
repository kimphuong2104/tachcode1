#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import ddl, sqlapi
from cdb.comparch import protocol
from cdb.comparch.updutils import install_objects


class UpdateUnsetTaskRelViolationToNewDefault:
    """
    The default value of the violation flag for task reslhips is now 0 and not NULL or '' anymore.
    """

    __update_stmt__ = """
        cdbpcs_taskrel SET violation = 0
        WHERE violation IS NULL
        """

    def run(self):
        sqlapi.SQLupdate(self.__update_stmt__)
        protocol.logMessage(
            "Updated unset task relship violation flags to new default."
        )


WHITELIST_OID = "70a6f58f-d1ca-11ec-8844-8945e77f50ef"


class InsertBriefCaseWhiteList:
    """This script reverts deleted patch of Briefcase Whitelist for cdbpcs_task"""

    def run(self):
        install_objects(
            module_id="cs.pcs.projects",
            objects=[
                (
                    "cdbwf_briefcase_whitelist",
                    {"cdb_object_id": WHITELIST_OID, "classname": "cdbpcs_task"},
                )
            ],
        )


class ResetResourceDemandsAndAssignments:
    """
    Reset the attributes effort_fcast_d and effort_fcast_d for projects amd tasks
    if no demands and assignments are found within the system
    """

    def run(self):
        from cs.pcs.projects import Project, tasks_efforts
        from cs.pcs.projects.tasks import Task

        def number_of_table_entries(table_name):
            query = f"SELECT COUNT(*) AS no FROM {table_name}"
            for record in sqlapi.RecordSet2(sql=query):
                return record["no"]

        count = 0
        for table_name in ["cdbpcs_prj_demand", "cdbpcs_prj_alloc"]:
            if ddl.Table(table_name).exists():
                additional = number_of_table_entries(table_name)
                if additional is None:
                    protocol.logMessage(f"Table '{table_name}' is empty.")
                else:
                    count += additional

        if not bool(count):
            protocol.logMessage(
                "No demands and no assignments found within the system.\n"
                "Removing wrong resource demand and assignment aggregation on projects and tasks."
            )
            projects = Project.Query("effort_fcast_d > 0 OR effort_fcast_a > 0")
            projects.Update(effort_fcast_d=0.0, effort_fcast_a=0.0)
            tasks = Task.Query("effort_fcast_d > 0 OR effort_fcast_a > 0")
            tasks.Update(effort_fcast_d=0.0, effort_fcast_a=0.0)
            for p in projects:
                tasks_efforts.aggregate_changes(p)


pre = []
post = [
    UpdateUnsetTaskRelViolationToNewDefault,
    InsertBriefCaseWhiteList,
    ResetResourceDemandsAndAssignments,
]
