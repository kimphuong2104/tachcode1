#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import sqlapi


def main():
    # update cdb_finished by attribute for all completed and finished tasks
    __stmt__ = """
    cdbpcs_task
    SET cdb_finishedby = (
        SELECT b.cdbprot_persnum
        FROM  cdbpcs_tsk_prot b
        INNER JOIN
            (SELECT cdb_project_id, task_id,  max(cdbprot_zeit) as maxdate
            FROM cdbpcs_tsk_prot
            WHERE cdbprot_newstate=200
                AND task_id=cdbpcs_task.task_id
                AND cdb_project_id=cdbpcs_task.cdb_project_id
            GROUP BY cdb_project_id, task_id) a
        ON b.task_id=a.task_id
            AND b.cdb_project_id=a.cdb_project_id
            AND b.cdbprot_zeit=a.maxdate
            AND b.cdbprot_newstate = 200)
    WHERE status in (200, 250)
    """
    sqlapi.SQLupdate(__stmt__)


# Guard importing as main module
if __name__ == "__main__":
    main()
