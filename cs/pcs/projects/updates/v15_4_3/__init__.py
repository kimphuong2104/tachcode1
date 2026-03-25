#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=consider-using-f-string

from cdb import sqlapi, transactions


class AdjustProjectRoleAttributes:
    """
    This script migrates the existing project roles.
    """

    def adjust_project_roles(self, project):
        sql_list = [
            """SELECT subject_id FROM cdbpcs_task
                       WHERE cdb_project_id = '{cdb_project_id}'
                       AND ce_baseline_id='{ce_baseline_id}'
                       AND subject_type = 'PCS Role'
                       AND status IN %s
                    """
            % str((20, 50)),
            """SELECT subject_id FROM cdbpcs_checklst
                       WHERE cdb_project_id = '{cdb_project_id}'
                       AND subject_type = 'PCS Role'
                       AND status = %s
                    """
            % str(20),
            """SELECT subject_id FROM cdbpcs_cl_item
                       WHERE cdb_project_id = '{cdb_project_id}'
                       AND subject_type = 'PCS Role'
                       AND status = %s
                    """
            % str(20),
            """SELECT subject_id FROM cdbpcs_issue
                       WHERE cdb_project_id = '{cdb_project_id}'
                       AND subject_type = 'PCS Role'
                       AND status IN %s
                    """
            % str((30, 50, 70, 100)),
        ]
        sql = " UNION ".join(sql_list)
        assigned_roles = sqlapi.RecordSet2(sql=sql.format(**project))
        assigned_roles_urgent = [x.subject_id for x in assigned_roles]
        sql_list = [
            """SELECT subject_id FROM cdbpcs_task
                       WHERE cdb_project_id = '{cdb_project_id}'
                       AND ce_baseline_id='{ce_baseline_id}'
                       AND subject_type = 'PCS Role'
                       AND status = %s
                    """
            % str(0),
            """SELECT subject_id FROM cdbpcs_checklst
                       WHERE cdb_project_id = '{cdb_project_id}'
                       AND subject_type = 'PCS Role'
                       AND status = %s
                    """
            % str(0),
            """SELECT subject_id FROM cdbpcs_cl_item
                       WHERE cdb_project_id = '{cdb_project_id}'
                       AND subject_type = 'PCS Role'
                       AND status = %s
                    """
            % str(0),
            """SELECT subject_id FROM cdbpcs_issue
                       WHERE cdb_project_id = '{cdb_project_id}'
                       AND subject_type = 'PCS Role'
                       AND status = %s
                    """
            % str(0),
        ]
        sql = " UNION ".join(sql_list)
        assigned_roles = sqlapi.RecordSet2(sql=sql.format(**project))
        assigned_roles_later = [x.subject_id for x in assigned_roles]
        roles = sqlapi.RecordSet2(
            "cdbpcs_prj_role", "cdb_project_id='{cdb_project_id}'".format(**project)
        )
        for role in roles:
            if role.role_id in assigned_roles_urgent:
                if role.team_needed != 2:
                    role.update(team_needed=2)
            elif role.role_id in assigned_roles_later:
                if role.team_needed != 1:
                    role.update(team_needed=1)
            else:
                if role.team_needed != 0:
                    role.update(team_needed=0)

    def run(self):
        with transactions.Transaction():
            for p in sqlapi.RecordSet2("cdbpcs_project", "status < 180"):
                self.adjust_project_roles(p)


pre = []
post = [AdjustProjectRoleAttributes]
