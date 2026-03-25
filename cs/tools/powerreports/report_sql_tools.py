#!/usr/bin/env python
# $Id$
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import auth, sqlapi, util


def get_grant_condition():
    persno = auth.persno
    persno_roles = util.get_roles("GlobalContext", "", persno)
    roles = ", ".join(["'%s'" % r for r in persno_roles])
    return """ AND EXISTS (
SELECT 1
FROM
cdbxml_report_grant report_grant
WHERE
report_grant.name = rep.name AND
report_grant.report_title = rep.title AND
((report_grant.subject_type = 'Common Role' AND report_grant.subject_id in ({roles}))
OR
(report_grant.subject_type = 'Person' AND report_grant.subject_id = '{persno}'))
)
""".format(
        roles=roles, persno=persno
    )


def get_report_records(report_id):
    query = """SELECT DISTINCT
rep.cdb_object_id cdbxml_report_id,
rep.dialog,
rep.cdbxml_report_action,
rep.cdbxml_report_format,
tmpl.iso_code,
tmpl.cdb_object_id tmpl_cdb_object_id,
f.cdb_object_id file_cdb_object_id,
rep.title,
f.cdbf_primary
FROM
cdbxml_report rep,
cdbxml_report_tmpl tmpl,
cdb_file f
WHERE
rep.title = tmpl.report_title AND
rep.name = tmpl.name AND
tmpl.cdb_object_id = f.cdbf_object_id AND
(f.cdbf_derived_from IS NULL OR f.cdbf_derived_from = '') AND
rep.cdb_object_id = '{report_id}'
""".format(
        report_id=report_id
    )

    query += get_grant_condition()
    query += " ORDER BY rep.title, tmpl.iso_code, f.cdbf_primary DESC"
    return sqlapi.RecordSet2(sql=query)


def get_report_langs(report_id):
    query = """SELECT DISTINCT
tmpl.iso_code
FROM
cdbxml_report rep,
cdbxml_report_tmpl tmpl,
cdb_file f
WHERE
rep.title = tmpl.report_title AND
rep.name = tmpl.name AND
tmpl.cdb_object_id = f.cdbf_object_id AND
rep.cdb_object_id = '{report_id}'
""".format(
        report_id=report_id
    )

    query += " ORDER BY tmpl.iso_code DESC"
    return sqlapi.RecordSet2(sql=query)


def get_template_file_ids(report_id, iso_code):
    query = """SELECT DISTINCT
tmpl.cdb_object_id tmpl_cdb_object_id,
f.cdb_object_id cdb_file_cdb_object_id,
tmpl.iso_code,
f.cdbf_primary
FROM
cdbxml_report rep,
cdbxml_report_tmpl tmpl,
cdb_file f
WHERE
tmpl.cdb_object_id = f.cdbf_object_id AND
rep.title = tmpl.report_title AND
rep.name = tmpl.name AND
(f.cdbf_derived_from IS NULL OR f.cdbf_derived_from = '') AND
rep.cdb_object_id = '{report_id}' AND tmpl.iso_code = '{iso_code}'
""".format(
        report_id=report_id, iso_code=iso_code
    )

    query += " ORDER BY tmpl.iso_code, f.cdbf_primary DESC"
    return sqlapi.RecordSet2(sql=query)


def get_template_records(context_fqpynames, card):
    from cs.tools.powerreports import CARD_N

    query = """SELECT DISTINCT
rep.title report_title,
rep.cdb_object_id cdbxml_report_id,
tmpl.iso_code,
tmpl.title tmpl_title
FROM
cdbxml_source src,
cdbxml_report rep,
cdbxml_report_tmpl tmpl,
cdb_file f
WHERE
rep.name = src.name AND
tmpl.name = src.name AND
rep.title = tmpl.report_title AND
tmpl.cdb_object_id = f.cdbf_object_id
"""
    if context_fqpynames:
        context_list = ", ".join(["'%s'" % x for x in context_fqpynames])
        context_expr = "src.context in (%s)" % context_list
    else:
        context_expr = "src.context = ''"
    query += " AND " + context_expr

    if card == CARD_N:
        query += " AND src.context_card = '%s'" % CARD_N

    query += get_grant_condition()
    query += " ORDER BY rep.title, tmpl.iso_code DESC"
    return sqlapi.RecordSet2(sql=query)
