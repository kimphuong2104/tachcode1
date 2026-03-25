#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from cdb import sqlapi


def cleanup_orphaned_job_params():
     # Postgres Case
    db_type = sqlapi.SQLdbms()
    if db_type == sqlapi.DBMS_POSTGRES:

        query_str = """
            FROM threed_hoops_job_params 
            WHERE NOT EXISTS (
                SELECT * FROM mq_acs 
                WHERE threed_hoops_job_params.job_id::bigint = mq_acs.cdbmq_id
                )
        """
    else:
        query_str = """
            FROM threed_hoops_job_params 
            WHERE NOT EXISTS (
                SELECT * FROM mq_acs 
                WHERE threed_hoops_job_params.job_id = mq_acs.cdbmq_id
                )
        """
    sqlapi.SQLdelete(query_str)