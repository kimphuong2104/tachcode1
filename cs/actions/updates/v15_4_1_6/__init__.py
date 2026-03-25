#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


__revision__ = "$Id$"

from cdb import dberrors, sqlapi
from cdb.comparch import protocol
from cdb.ddl import Table


class DropViews:

    tbd_views = ["cdb_action_resp_brows"]

    def run(self):

        for tbd_view in self.tbd_views:

            stmt = "table_name from cdb_tables where table_name = '{}'".format(tbd_view)
            try:
                if sqlapi.SQLrows(sqlapi.SQLselect(stmt)) == 1:
                    sqlapi.SQL("drop view {}".format(tbd_view))

            except dberrors.DBError:
                protocol.logWarning(
                    "The view {} could not be removed. "
                    "This is fine if the view does not exist.".format(tbd_view)
                )

            try:
                sqlapi.SQL(
                    "create view {} as {}".format(
                        tbd_view, self.generate_cdb_action_resp_brows()
                    )
                )

            except dberrors.DBError:
                protocol.logWarning(
                    "The view {} could not be created. ".format(tbd_view)
                )

    def generate_cdb_action_resp_brows(self):
        # Disable pylint warning 'line too long' for this function
        # pylint: disable=line-too-long

        if sqlapi.SQLdbms() == sqlapi.DBMS_MSSQL:
            from cdb.mssql import CollationDefault

            collate = " COLLATE %s " % CollationDefault.get_default_collation()
        else:
            collate = ""
        STATIC_PART = (
            "SELECT personalnummer AS subject_id, name AS description_de, name AS description_en"
            ", name AS description_cs, name AS description_es, name AS description_fr"
            ", name AS description_it, name AS description_ja, name AS description_ko"
            ", name AS description_pl, name AS description_pt, name AS description_tr"
            ", name AS description_zh, 'Person' %s AS subject_type"
            ", name AS subject_name_de, name AS subject_name_en, name AS subject_name_cs"
            ", name AS subject_name_es, name AS subject_name_fr, name AS subject_name_it"
            ", name AS subject_name_ja, name AS subject_name_ko, name AS subject_name_pl"
            ", name AS subject_name_pt, name AS subject_name_tr, name AS subject_name_zh"
            ", '' %s AS cdb_project_id, 1 AS order_by"
            " FROM angestellter WHERE active_account='1' and visibility_flag='1' and is_system_account='0'"
            " UNION"
            " SELECT role_id AS subject_id, description AS description_de, description_ml_en AS description_en,"  # noqa: E501
            " description_ml_cs AS description_cs, description_ml_es AS description_es,"
            " description_ml_fr AS description_fr, description_ml_it AS description_it,"
            " description_ml_ja AS description_ja, description_ml_ko AS description_ko,"
            " description_ml_pl AS description_pl, description_ml_pt AS description_pt,"
            " description_ml_tr AS description_tr, description_ml_zh AS description_zh,"
            " 'Common Role' %s AS subject_type, name_de AS subject_name_de, name_en AS subject_name_en,"
            " name_cs AS subject_name_cs, name_es AS subject_name_es, name_fr AS subject_name_fr,"
            " name_it AS subject_name_it, name_ja AS subject_name_ja, name_ko AS subject_name_ko,"
            " name_pl AS subject_name_pl, name_pt AS subject_name_pt, name_tr AS subject_name_tr,"
            " name_zh AS subject_name_zh, '' %s AS cdb_project_id, 2 AS order_by"
            " FROM cdb_global_role where is_org_role = 1"
            % (collate, collate, collate, collate)
        )
        PCS_PART = (
            " UNION"
            " SELECT p.role_id AS subject_id, d.description AS description_de, d.description_ml_en AS description_en"  # noqa: E501
            ", d.description_ml_cs AS description_cs, d.description_ml_es AS description_es"
            ", d.description_ml_fr AS description_fr, d.description_ml_it AS description_it"
            ", d.description_ml_ja AS description_ja, d.description_ml_ko AS description_ko"
            ", d.description_ml_pl AS description_pl, d.description_ml_pt AS description_pt"
            ", d.description_ml_tr AS description_tr, d.description_ml_zh AS description_zh"
            ", 'PCS Role' %s AS subject_type, d.name_ml_de AS subject_name_de, d.name_ml_en AS subject_name_en"  # noqa: E501
            ", d.name_ml_cs AS subject_name_cs, d.name_ml_es AS subject_name_es"
            ", d.name_ml_fr AS subject_name_fr, d.name_ml_it AS subject_name_it"
            ", d.name_ml_ja AS subject_name_ja, d.name_ml_ko AS subject_name_ko"
            ", d.name_ml_pl AS subject_name_pl, d.name_ml_pt AS subject_name_pt"
            ", d.name_ml_tr AS subject_name_tr, d.name_ml_zh AS subject_name_zh"
            ", p.cdb_project_id %s AS cdb_project_id, 3 AS order_by"
            " FROM cdbpcs_prj_role p, cdbpcs_role_def d"
            " WHERE p.role_id = d.name" % (collate, collate)
        )

        t = Table("cdbpcs_prj_role")
        return (STATIC_PART + PCS_PART) if t.exists() else STATIC_PART


pre = []
post = [DropViews]
