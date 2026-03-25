#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


from cdb import sqlapi

from cs.pcs.projects import kProjectManagerRole


class MigrateProjectManager:
    def run(self):
        stmt = """
            cdbpcs_project SET project_manager = (
                CASE
                    WHEN cdbpcs_project.initial_manager IN (
                        SELECT subject_id FROM cdbpcs_subject WHERE
                            role_id = '{role_id}' AND
                            subject_type = 'Person' AND
                            cdb_project_id = cdbpcs_project.cdb_project_id
                        )
                    THEN cdbpcs_project.initial_manager
                    ELSE
                        CASE
                            WHEN 1 = (
                                SELECT count(*) FROM cdbpcs_subject WHERE
                                    role_id = '{role_id}' AND
                                    subject_type = 'Person' AND
                                    cdb_project_id = cdbpcs_project.cdb_project_id
                            )
                            THEN
                                (SELECT subject_id FROM cdbpcs_subject WHERE
                                    role_id = '{role_id}' AND
                                    subject_type = 'Person' AND
                                    cdb_project_id = cdbpcs_project.cdb_project_id)
                            ELSE ''
                        END
                END
            )
        """.format(
            role_id=kProjectManagerRole
        )
        sqlapi.SQLupdate(stmt)


pre = []
post = [MigrateProjectManager]
