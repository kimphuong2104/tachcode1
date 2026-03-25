#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Module __init__.py

Update scripts of cs.pcs 15.5.0
"""

# Exported objects
__all__ = []

from cdb import sqlapi, transactions
from cdb.constants import kOperationNew
from cdb.objects.operations import operation
from cdb.typeconversion import to_legacy_date_format_auto
from cs.activitystream.objects import UserPosting

AUTOMATIC_TAG = "--- automatically migrated from comments ---"


class MigrateIssueComments:
    """
    This script migrates the existing comments of issues
    to its activitystream.
    """

    @classmethod
    def get_remove_automatic_comments(cls):
        t = sqlapi.SQLselect(
            "DISTINCT cdb_object_id FROM cdbblog_posting_txt "
            f"WHERE zeile = 0 AND text LIKE '{AUTOMATIC_TAG}%'"
        )
        oids = []
        for i in range(sqlapi.SQLrows(t)):
            oids.append(sqlapi.SQLstring(t, 0, i))
        postings = UserPosting.KeywordQuery(cdb_object_id=oids)
        postings.Delete()
        sqlapi.SQL(
            "DELETE FROM cdbblog_posting_txt WHERE cdb_object_id NOT IN "
            "(SELECT cdb_object_id FROM cdbblog_posting)"
        )

    def get_automatic_comments(self, issue_id, cdb_project_id, oid):
        rows = sqlapi.RecordSet2(
            sql="SELECT DISTINCT a.cdb_cpersno, a.cdb_cdate, "
            "b.remark_id, b.zeile, b.text "
            "FROM cdbpcs_iss_rem a, cdbpcs_issr_txt b "
            f"WHERE b.issue_id = {issue_id} AND b.cdb_project_id = '{cdb_project_id}' "
            "AND a.issue_id=b.issue_id "
            "AND a.cdb_project_id = b.cdb_project_id "
            "AND a.remark_id = b.remark_id "
            "ORDER BY b.remark_id ASC, b.zeile ASC"
        )
        text_dict = {}
        kwargs_dict = {}
        all_text = []
        remark_ids = []
        text_tag = f"{AUTOMATIC_TAG}\n"
        for row in rows:
            text = row["text"].replace("\\n", "\n")
            remark_id = row["remark_id"]
            if text:
                if remark_id not in remark_ids:
                    kwargs = {}
                    comment_persno = row["cdb_cpersno"]
                    comment_date = f"{to_legacy_date_format_auto(row['cdb_cdate'])}"
                    kwargs.update(
                        cdb_cpersno=comment_persno,
                        cdb_cdate=comment_date,
                        cdb_mpersno=comment_persno,
                        cdb_mdate=comment_date,
                        last_comment_date=comment_date,
                        context_object_id=oid,
                    )
                    kwargs_dict[remark_id] = kwargs
                    text_dict[remark_id] = text_tag + text
                    remark_ids.append(remark_id)
                else:
                    text_dict[remark_id] += text
        for remark_id in remark_ids:
            all_text.append((kwargs_dict[remark_id], text_dict[remark_id]))
        return all_text

    def get_issues(self):
        issues = []
        t = sqlapi.SQLselect(
            "DISTINCT issue_id, cdb_project_id, cdb_object_id FROM cdbpcs_issue"
        )
        for i in range(sqlapi.SQLrows(t)):
            issues.append(
                (
                    sqlapi.SQLstring(t, 0, i),
                    sqlapi.SQLstring(t, 1, i),
                    sqlapi.SQLstring(t, 2, i),
                )
            )
        return issues

    def run(self):
        with transactions.Transaction():
            MigrateIssueComments.get_remove_automatic_comments()
            for issue_id, prj_id, oid in self.get_issues():
                for kwargs, txt in self.get_automatic_comments(issue_id, prj_id, oid):
                    posting = operation(kOperationNew, UserPosting, **kwargs)
                    posting.Update(**kwargs)
                    posting.SetText("cdbblog_posting_txt", txt)


class RemoveNetworkMapValues:
    """This script removes all values for the network map calculation.
    Those values are set to NULL for all tasks.
    """

    def run(self):
        with transactions.Transaction():
            sql = """cdbpcs_task SET
                total_float = NULL,
                free_float = NULL,
                early_start = NULL,
                early_finish = NULL,
                late_start = NULL,
                late_finish = NULL
            """
            sqlapi.SQLupdate(sql)


pre = []
post = [RemoveNetworkMapValues]
