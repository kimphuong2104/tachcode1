#!/usr/bin/env python
# $Id$
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
import json

from cdb import sqlapi, util

REPORT_QUEUE_JOB_ARG_TABLE = "cdbxml_report_queue_arg"


def get_job_args(job_id):
    """
    Get job arguments from the "cdbxml_report_queue_arg" table.

    :param job_id: int. mq.Job.id()
    :return: dict. job arguments
    """
    args_str = util.text_read(REPORT_QUEUE_JOB_ARG_TABLE, ["job_id"], [job_id])
    return json.loads(args_str) if args_str else {}


def set_job_args(job_id, args=None):
    """
    Set job arguments in the "cdbxml_report_queue_arg" table.
    Delete the entry if "args" is None or not set.

    :param job_id: int. mq.Job.id()
    :param args: dict. job arguments
    """
    if args is not None:
        args_str = json.dumps(args)
    else:
        # text_write empty string deletes the entry automatically
        args_str = ""
    util.text_write(REPORT_QUEUE_JOB_ARG_TABLE, ["job_id"], [job_id], args_str)


def cleanup_orphaned_job_params():
    """
    clean up "cdbxml_report_queue_arg" table
    for jobs that no longer exists in the MessageQueue
    """
    db_type = sqlapi.SQLdbms()
    # sqlapi.DBMS_ORACLE, sqlapi.DBMS_MSSQL, sqlapi.DBMS_POSTGRES, sqlapi.DBMS_SQLITE

    if db_type == sqlapi.DBMS_POSTGRES:
        query_str = """
                    FROM {table}
                    WHERE NOT EXISTS (
                        SELECT * FROM mq_acs
                        WHERE CAST({table}.job_id as BIGINT) = mq_acs.cdbmq_id
                        )
                    """
    else:
        query_str = """
                    FROM {table}
                    WHERE NOT EXISTS (
                        SELECT * FROM mq_acs
                        WHERE {table}.job_id = mq_acs.cdbmq_id
                        )
                    """

    query = query_str.format(table=REPORT_QUEUE_JOB_ARG_TABLE)
    sqlapi.SQLdelete(query)
