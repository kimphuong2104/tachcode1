#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#


__revision__ = "$$"


from cdbwrapc import check_license

from cdb import constants
from cdb import ue

from cdb.ddl import Table

from cdb import i18n


def _get_pydate_format(_format):
    # Workaround for E032998
    import re

    conversions = [
        ("YYYY", "%Y"),
        ("MM", "%m"),
        ("DD", "%d"),
        ("hh", "%H"),
        ("mm", "%M"),
        ("ss", "%S")
    ]

    result = _format
    for wrong, right in conversions:
        result = re.sub(wrong, right, result)
    return result


def get_pydate_format():
    return _get_pydate_format(i18n.get_date_format())


def get_pydatetime_format():
    return _get_pydate_format(i18n.get_datetime_format())


def generate_cdbqc_resp_brows():
    STATIC_PART = ("SELECT personalnummer AS subject_id, name AS description_de, name AS description_en"
                   ", name AS description_cs, name AS description_es, name AS description_fr"
                   ", name AS description_it, name AS description_ja, name AS description_ko"
                   ", name AS description_pl, name AS description_pt, name AS description_tr"
                   ", name AS description_zh, 'Person' AS subject_type"
                   ", name AS subject_name_de, name AS subject_name_en, name AS subject_name_cs"
                   ", name AS subject_name_es, name AS subject_name_fr, name AS subject_name_it"
                   ", name AS subject_name_ja, name AS subject_name_ko, name AS subject_name_pl"
                   ", name AS subject_name_pt, name AS subject_name_tr, name AS subject_name_zh"
                   ", '' AS cdb_project_id, 1 AS order_by"
                   " FROM angestellter WHERE active_account='1' and visibility_flag='1'"
                   " UNION"
                   " SELECT role_id AS subject_id, description AS description_de, description_ml_en AS description_en,"
                   " description_ml_cs AS description_cs, description_ml_es AS description_es,"
                   " description_ml_fr AS description_fr, description_ml_it AS description_it,"
                   " description_ml_ja AS description_ja, description_ml_ko AS description_ko,"
                   " description_ml_pl AS description_pl, description_ml_pt AS description_pt,"
                   " description_ml_tr AS description_tr, description_ml_zh AS description_zh,"
                   " 'Common Role' AS subject_type, name_de AS subject_name_de, name_en AS subject_name_en,"
                   " name_cs AS subject_name_cs, name_es AS subject_name_es, name_fr AS subject_name_fr,"
                   " name_it AS subject_name_it, name_ja AS subject_name_ja, name_ko AS subject_name_ko,"
                   " name_pl AS subject_name_pl, name_pt AS subject_name_pt, name_tr AS subject_name_tr,"
                   " name_zh AS subject_name_zh, '' AS cdb_project_id, 2 AS order_by"
                   " FROM cdb_global_role")
    PCS_PART = (" UNION"
               " SELECT p.role_id AS subject_id, d.description AS description_de, d.description_ml_en AS description_en"
               ", d.description_ml_cs AS description_cs, d.description_ml_es AS description_es"
               ", d.description_ml_fr AS description_fr, d.description_ml_it AS description_it"
               ", d.description_ml_ja AS description_ja, d.description_ml_ko AS description_ko"
               ", d.description_ml_pl AS description_pl, d.description_ml_pt AS description_pt"
               ", d.description_ml_tr AS description_tr, d.description_ml_zh AS description_zh"
               ", 'PCS Role' AS subject_type, d.name_ml_de AS subject_name_de, d.name_ml_en AS subject_name_en"
               ", d.name_ml_cs AS subject_name_cs, d.name_ml_es AS subject_name_es"
               ", d.name_ml_fr AS subject_name_fr, d.name_ml_it AS subject_name_it"
               ", d.name_ml_ja AS subject_name_ja, d.name_ml_ko AS subject_name_ko"
               ", d.name_ml_pl AS subject_name_pl, d.name_ml_pt AS subject_name_pt"
               ", d.name_ml_tr AS subject_name_tr, d.name_ml_zh AS subject_name_zh"
               ", p.cdb_project_id AS cdb_project_id, 3 AS order_by"
               " FROM cdbpcs_prj_role p, cdbpcs_role_def d"
               " WHERE p.role_id = d.name")

    t = Table('cdbpcs_prj_role')
    return (STATIC_PART + PCS_PART) if t.exists() else STATIC_PART
