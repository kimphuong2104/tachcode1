#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import unicode_literals

import logging
import datetime
from cdb import sqlapi
from cdb import i18n
from cdb import util
from cdb.typeconversion import to_legacy_date_format_auto
from cs.requirements import RQMSpecObject, RQMSpecification
from cs.requirements.classes import RQMSpecificationStateProtocol
from cdb.dberrors import DBConstraintViolation
from cs.requirements.rqm_utils import strip_tags
from cs.metrics.qualitycharacteristics import ObjectQualityCharacteristic
from cs.audittrail import AuditTrail
from cs.tools.semanticlinks import SemanticLink

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


LOG = logging.getLogger(__name__)


def top_spec_objects_to_specification_aggregation(aggr_ctx):
    weights = 0
    avg = 0

    if len([x for x in aggr_ctx.children_map.values() if x.act_value is not None]) == 0:
        # as long as no evaluated requirement value exist it makes no sense to evaluate anything
        return None

    for r, rqc in aggr_ctx.children_map.items():
        weights += r.weight
        avg += (rqc.act_value if rqc.act_value is not None else 0) * r.weight
    result = avg / weights if weights != 0 else 0.0
    LOG.debug('top_spec_objects_to_specification_aggregation : %s / %s (%s -> %s)', aggr_ctx.object.GetDescription(), aggr_ctx.children_map, aggr_ctx.object.act_value, result)
    return float(result)


def spec_object_to_parent_spec_object_aggregation(aggr_ctx):
    weights = 0
    avg = 0

    if len([x for x in aggr_ctx.children_map.values() if x.act_value is not None]) == 0:
        # as long as no evaluated requirement value exist it makes no sense to evaluate anything
        return None

    for r, rqc in aggr_ctx.children_map.items():
        weights += r.weight
        avg += (rqc.act_value if rqc.act_value is not None else 0) * r.weight
    result = avg / weights if weights != 0 else 0.0
    LOG.debug('spec_object_to_parent_spec_object_aggregation : %s / %s (%s -> %s)', aggr_ctx.object.GetDescription(), aggr_ctx.children_map, aggr_ctx.object.act_value, result)
    return float(result)


def target_value_to_spec_object_aggregation(aggr_ctx):
    weights = 0
    avg = 0

    if len([x for x in aggr_ctx.children_map.values() if x.act_value is not None]) == 0:
        # as long as no evaluated target value exist it makes no sense to evaluate anything
        return None
    for tv, qtv in aggr_ctx.children_map.items():
        tv_weight = tv.weight if tv.weight is not None else 1.0
        weights += tv_weight
        if tv.value_type == 1:
            avg += (qtv.act_value if qtv.act_value is not None else 0) * tv_weight
        else:
            avg += (100 if tv.isFulfilled(qtv.act_value, qtv.target_value) else 0) * tv_weight
    result = avg / weights if weights != 0 else 0.0
    LOG.debug('target_value_to_spec_object_aggregation : %s / %s (%s -> %s)', aggr_ctx.object.GetDescription(), aggr_ctx.children_map, aggr_ctx.object.act_value, result)
    return float(result)


def count_of_leaf_spec_objects_in_specification(qc):
    return len(
        RQMSpecObject.Query("specification_object_id='{specification_object_id}' and "
                            "0=(select count(cdb_object_id) "
                            "from {table_name} r2 "
                            "where parent_object_id={table_name}.cdb_object_id)".format(specification_object_id=qc.cdbf_object_id,
                                                                                        table_name=RQMSpecObject.__maps_to__)))


def count_approved_specifications_per_month(qc):
    end_date = datetime.date.today()
    sqlWhere = "cdbprot_newstate = %d" % RQMSpecification.RELEASED.status
    start_date = end_date - datetime.timedelta(days=(end_date - datetime.timedelta(days=1)).day)
    ed = sqlapi.SQLdbms_date(to_legacy_date_format_auto(end_date))
    sd = sqlapi.SQLdbms_date(to_legacy_date_format_auto(start_date))
    sqlWhere += (" AND (cdbprot_zeit >= %s AND cdbprot_zeit < %s)"
                 % (sd, ed))
    rs = RQMSpecificationStateProtocol.Query(sqlWhere)
    if not rs:
        return 0.0
    return len(rs)


def avg_description_length(qc):
    descs = []
    textfields = RQMSpecObject.GetTextFieldNames()
    for iso_lang in i18n.Languages():
        description_attr_name = RQMSpecObject.__description_attrname_format__.format(iso=iso_lang)
        if description_attr_name in textfields:
            try:
                for rs in sqlapi.RecordSet2(sql="select distinct cdb_object_id from %s" % description_attr_name):
                    txt = util.text_read(description_attr_name, ["cdb_object_id"], [rs.cdb_object_id])
                    if txt:
                        descs.append(strip_tags(txt))
            except DBConstraintViolation:
                pass
    if descs:
        return sum(map(len, descs)) / len(descs)
    return 0.0


def avg_description_length_of_specification(qc):
    spec = RQMSpecification.ByKeys(qc.cdbf_object_id)
    if spec.Requirements:
        obj_ids = spec.Requirements.cdb_object_id
    else:
        return 0.0
    descs = []
    textfields = RQMSpecObject.GetTextFieldNames()
    for iso_lang in i18n.Languages():
        description_attr_name = RQMSpecObject.__description_attrname_format__.format(iso=iso_lang)
        if description_attr_name in textfields:
            for obj_id in obj_ids:
                txt = util.text_read(description_attr_name, ["cdb_object_id"], [obj_id])
                if txt:
                    descs.append(strip_tags(txt))
    if descs:
        return sum(map(len, descs)) / len(descs)
    return 0.0


def count_fulfilled_requirements_per_month(qc):
    end_date = datetime.date.today()
    sqlWhere = "classname = 'cdbrqm_spec_object' and target_fulfillment = 4"
    start_date = end_date - datetime.timedelta(days=(end_date - datetime.timedelta(days=1)).day)
    ed = sqlapi.SQLdbms_date(to_legacy_date_format_auto(end_date))
    sd = sqlapi.SQLdbms_date(to_legacy_date_format_auto(start_date))
    sqlWhere += (" AND (cdb_mdate >= %s AND cdb_mdate < %s)"
                 % (sd, ed))
    pc = ObjectQualityCharacteristic.Query(sqlWhere)
    if not pc:
        return 0.0
    return len(pc)


def count_changed_requirements_per_month(qc):
    end_date = datetime.date.today()
    sqlWhere = "classname = 'cdbrqm_spec_object' and type = 'modify'"
    start_date = end_date - datetime.timedelta(days=(end_date - datetime.timedelta(days=1)).day)
    ed = sqlapi.SQLdbms_date(to_legacy_date_format_auto(end_date))
    sd = sqlapi.SQLdbms_date(to_legacy_date_format_auto(start_date))
    sqlWhere += (" AND (cdb_cdate >= %s AND cdb_cdate < %s)"
                 % (sd, ed))
    at = AuditTrail.Query(sqlWhere)
    if not at:
        return 0.0
    return len(at)


def count_changed_requirements_of_specification(qc):
    spec = RQMSpecification.ByKeys(qc.cdbf_object_id)
    if spec.Requirements:
        obj_ids = spec.Requirements.cdb_object_id
    else:
        return 0.0
    at = AuditTrail.KeywordQuery(type='modify',
                                 object_id=obj_ids)
    if not at:
        return 0.0
    return len(at)


def count_linked_requirements_of_specification(qc):
    spec = RQMSpecification.ByKeys(qc.cdbf_object_id)
    if spec.Requirements:
        obj_ids = spec.Requirements.cdb_object_id
    else:
        return 0.0
    count = 0
    count += len(SemanticLink.KeywordQuery(subject_object_id=obj_ids))
    return count


def count_reused_requirements(qc):
    links = len(sqlapi.RecordSet2("cdb_semantic_link_v", "linktype_name = 'Copied to' and subject_object_classname = 'cdbrqm_spec_object'"))
    reqs = len(sqlapi.RecordSet2("cdbrqm_spec_object"))
    if reqs > 0:
        return float(links) / float(reqs) * 100
    else:
        return 0.0
