#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import sqlapi
from cdb.comparch import protocol


class MigrateEarlyPosition:
    def run(self):
        sqlapi.SQLupdate(
            "cdbpcs_task SET start_is_early = 1, end_is_early = 0 "
            "WHERE milestone IS NULL OR milestone = 0"
        )


class MigrateIssuesCompletionDate:
    "This script migrates the issues and sets the completion date."

    def run(self):
        sqlapi.SQLupdate(
            "cdbpcs_issue SET completion_date = "
            "(SELECT MAX(cdbprot_zeit) AS comp_date FROM cdbpcs_iss_prot "
            "WHERE cdbpcs_iss_prot.cdb_project_id = "
            "cdbpcs_issue.cdb_project_id "
            "AND cdbpcs_iss_prot.issue_id = cdbpcs_issue.issue_id) "
            "WHERE cdbpcs_issue.status IN (180, 200)"
        )


class MigrateProjectAndTaskDates:
    def run(self):
        """
        Note: Obsolete since cs.platform 15.6 because time info is ignored.

        Old description:

        This script outputs all projects and tasks where start_time_fcast and/or
        end_time_fcast include a time part.
        It also removes the time part (i.e. setting it to zero) of the
        attributes start_time_act, end_time_act and constraint_date (task only)
        for any project or task, if the attribute includes a time part.
        """
        pass


class MigrateProjectNotesDefaultTxt:
    def run(self):
        # if if an entry for cs.pcs.widgets.project_notes_default_txt already
        # existed, copy its content to
        # cs.pcs.widgets.project_notes_default_txt_de
        records = sqlapi.RecordSet2(
            "cdb_setting_long_txt",
            "setting_id='cs.pcs.widgets.project_notes_default_txt'",
        )
        if len(records) != 0:
            for record in records:
                sqlapi.SQLupdate(
                    "cdb_setting_long_txt SET text = '{record.text}' "
                    "WHERE setting_id = 'cs.pcs.widgets.project_notes_default_txt_de' "
                    "AND zeile = {record.zeile} "
                    "AND role_id = '{record.role_id}' "
                    "AND setting_id2 = '{record.setting_id2}'".format(record=record)
                )
        else:
            msg = "No prior Project Notes Default Txt found. No Update required."
            print(msg)
            protocol.logMessage(msg)


pre = []
post = [
    MigrateEarlyPosition,
    MigrateIssuesCompletionDate,
    MigrateProjectAndTaskDates,
    MigrateProjectNotesDefaultTxt,
]
