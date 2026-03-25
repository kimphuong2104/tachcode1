#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import sqlapi
from cdb.comparch import protocol


class FindOrphanedDocTemplateReferences:
    """
    Reports any "dead" document template links.
    These may indicate that a referenced document was erroneously deleted.
    Fixes have to be applied manually by
    either recreating the document or deleting the reference.
    """

    __tables__ = [
        "cdbpcs_cl2doctmpl",
        "cdbpcs_cli2doctmpl",
        "cdbpcs_prj2doctmpl",
        "cdbpcs_task2doctmpl",
    ]

    def run(self):
        for table in self.__tables__:
            dead_refs = sqlapi.RecordSet2(
                sql=f"""
                    SELECT DISTINCT z_nummer, z_index
                    FROM {table}
                    WHERE NOT EXISTS (
                        SELECT 1 FROM zeichnung
                        WHERE zeichnung.z_nummer={table}.z_nummer
                            AND zeichnung.z_index={table}.z_index
                    )
                """
            )
            for ref in dead_refs:
                protocol.logWarning(
                    "referenced document does not exist: "
                    f"z_nummer = '{ref.z_nummer}' AND "
                    f"z_index = '{ref.z_index}' "
                    f"({table})"
                )


class RemoveMilestoneProposals:
    __stmt__ = """
    FROM pcs_task_proposals
    WHERE EXISTS (
        SELECT 1 FROM cdbpcs_task
        WHERE cdbpcs_task.milestone=1
        AND cdbpcs_task.cdb_project_id=pcs_task_proposals.cdb_project_id
        AND cdbpcs_task.task_id=pcs_task_proposals.task_id
        AND cdbpcs_task.ce_baseline_id=pcs_task_proposals.ce_baseline_id
    )"""

    def run(self):
        sqlapi.SQLdelete(self.__stmt__)


pre = []
post = [FindOrphanedDocTemplateReferences, RemoveMilestoneProposals]
