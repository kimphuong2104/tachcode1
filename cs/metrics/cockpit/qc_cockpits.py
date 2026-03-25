#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb.objects import Rule, NULL
from cs.metrics import qualitycharacteristics as QualityCharacteristics
from cs.metrics import targetprocessor
from cs.metrics.qcclasses import QCDefinition

from cdb.lru_cache import lru_cache
from cdb import util
from cdb import fls
from cdb import sqlapi
from cdb.objects.expressions import Expression, Literal
from cdb.cmsg import Cdbcmsg
from cdb.platform.mom import entities
import math
import datetime

__OBJ_QUALITY_CHARACTERISTIC_CLASS__ = "cdbqc_obj_quality_character"
ObjQualityClassDef = None
ObjActValDecimals = None
ObjAggrValDecimals = None
__PRC_QUALITY_CHARACTERISTIC_CLASS__ = "cdbqc_class_quality_character"
PrcQualityClassDef = None
PrcActValDecimals = None
__QC_VISIBLE__ = "cdbqc: visible quality characteristics"
rule = None


def __load_defs():
    global ObjQualityClassDef
    global ObjActValDecimals
    global ObjAggrValDecimals
    global PrcQualityClassDef
    global PrcActValDecimals
    global rule
    if ObjQualityClassDef is None:
        ObjQualityClassDef = entities.CDBClassDef(__OBJ_QUALITY_CHARACTERISTIC_CLASS__)
    if ObjActValDecimals is None:
        ObjActValDecimals = int(ObjQualityClassDef.getAttributeDefinition('act_value').get_post_decimals())
    if ObjAggrValDecimals is None:
        ObjAggrValDecimals = int(ObjQualityClassDef.getAttributeDefinition('aggr_value').get_post_decimals())
    if PrcQualityClassDef is None:
        PrcQualityClassDef = entities.CDBClassDef(__PRC_QUALITY_CHARACTERISTIC_CLASS__)
    if PrcActValDecimals is None:
        PrcActValDecimals = int(PrcQualityClassDef.getAttributeDefinition('act_value').get_post_decimals())
    if rule is None:
        rule = Rule.ByKeys(__QC_VISIBLE__)


def compute(qc_id):
    # allocate license for feature "Metrics: Compute Values"
    fls.allocate_license("METRICS_015")

    __load_defs()
    from cdb.objects import ByID
    qc = ByID(qc_id)
    if qc is not None and rule.match(qc):
        qc.compute()
        return {"act_val": qc.act_value if (qc.act_value != NULL and qc.act_value is not None) else '',
                "tar_val": qc.target_value if (qc.target_value != NULL and qc.target_value is not None) else '',
                "checktarget": checktarget(qc),
                "aggr_val": qc.aggr_value if (qc.aggr_value != NULL and qc.aggr_value is not None) else ''}


def checktarget(qc):
    """
    The target value is analyzed, interpreted and compared to the actual
    value. The result will be returned as color code, which is needed to
    display the status.

    @param qc:
        Quality characteristic object to initialize values to compare
    """
    if qc.target_fulfillment == targetprocessor.TargetStatus.green.value:  # @UndefinedVariable
        check_result = "gruen"
    elif qc.target_fulfillment == targetprocessor.TargetStatus.red.value:  # @UndefinedVariable
        check_result = "rot"
    else:
        check_result = 'warning'

    return check_result


def check_act_value(act_value):
    try:
        fval = float(act_value)
        if not math.isnan(fval) and not math.isinf(fval):
            return True
        else:
            return False
    except ValueError:
        return False
    except TypeError:
        return False


def save_target_value(qc_id, target_value):
    # allocate license for feature "Metrics: Write Values"
    fls.allocate_license("METRICS_002")

    qc = QualityCharacteristics.QualityCharacteristic.ByKeys(qc_id)
    qc = qc if qc.CheckAccess("read") else None

    if not qc:
        raise util.ErrorMessage("cdbqc_elink_cockpit_invalid_qc")
    else:
        if rule.match(qc):
            try:
                qc.target_value = target_value
            except targetprocessor.InvalidTargetValue:
                raise util.ErrorMessage("cdbqc_elink_cockpit_invalid_target")
        else:
            raise util.ErrorMessage("cdbqc_elink_cockpit_no_access")

    return {"color": checktarget(qc)}


def _log_setting_err(e):
    from cdb import misc
    misc.cdblogv(misc.kLogErr, 7, "Error by saving personal setting: %s" % e)


def generate_qc_js_settings(qc_app_name, user_settings, aoColumnsNames, aoColumnsJSVars, aggregated=None, qgrade_js_dict=None, manual=None):
    __load_defs()
    cellfocus = generate_cellfocus(user_settings)
    output_vars = (qc_app_name, cellfocus[0], cellfocus[1],
                   util.get_label('cdbqc_elink_cockpit_search'),
                   generate_selectedRows(user_settings),
                   "2_%s" % util.get_label('cdbqc_elink_cockpit_red'),
                   "1_%s" % util.get_label('cdbqc_elink_cockpit_green'),
                   "0_%s" % util.get_label('cdbqc_elink_cockpit_no_state'),
                   generate_aoColumnDefs_bVisibles(user_settings, aoColumnsNames),
                   util.get_label('cdbqc_elink_cockpit_show_hide'),
                   util.get_label('cdbqc_elink_cockpit_no_data'),
                   generate_aaSorting(user_settings),
                   util.get_label('cdbqc_elink_cockpit_click_to_edit'),
                   generate_jsColumnIdVars(aoColumnsJSVars, aoColumnsNames),
                   qgrade_js_dict if qgrade_js_dict else 'null',
                   ("'%s'" % aggregated) if aggregated else 'null',
                   ("'%s'" % manual) if manual else 'null',
                   util.get_label('cdbqc_elink_cockpit_action_name'),
                   util.get_label('cdbqc_elink_cockpit_action_cost'),
                   util.get_label('cdbqc_elink_cockpit_action_state'),
                   util.get_label('cdbqc_elink_cockpit_action_resp'),
                   util.get_label('cdbqc_elink_cockpit_action_dead'),
                   util.get_label('cdbqc_elink_cockpit_action_effect'),
                   Cdbcmsg('cdbqc_action2qc', 'CDB_Create', True).get_url(),
                   Cdbcmsg('cdbqc_action2qc', 'CDB_ShowObject', True).get_url(),
                   util.get_label('cdbqc_elink_cockpit_green_qc'),
                   util.get_label('cdbqc_elink_cockpit_red_qc'),
                   PrcActValDecimals,
                   ObjAggrValDecimals,
                   ObjActValDecimals)

    output = """'qc_cockpit_app':'%s',
    'initial_cell_focus': [%d, %d],
    'initial_searchfield_value':'%s',
    'initial_selected_rows': %s,
    'initial_labels_red':'%s',
    'initial_labels_green':'%s',
    'initial_labels_warning':'%s',
    'initial_aoColumnDefs_bVisibles':%s,
    'initial_toggleHiddenColumns':'%s',
    'initial_no_data': '%s',
    'initial_aaSorting':%s,
    'initial_labels_click_to_edit':'%s',
    %s
    'qgrade_js_dict': %s,
    'aggregated': %s,
    'manual':%s,
    'tt_name':'%s',
    'tt_cost':'%s',
    'tt_state':'%s',
    'tt_resp':'%s',
    'tt_dead':'%s',
    'tt_eff':'%s',
    'action_assignment_url':'%s',
    'action_url':'%s',
    'qc_green':'%s',
    'qc_red':'%s',
    'prc_act_val_decimals':%d,
    'obj_aggr_val_decimals':%d,
    'obj_act_val_decimals':%d""" % output_vars
    return output


def generate_jsColumnIdVars(aoColumnsJSVars, aoColumnsNames):
    output = ""
    for var in aoColumnsJSVars:
        if aoColumnsJSVars[var] is None:
            output += '"%s":-1,' % (var)
        else:
            for column in aoColumnsNames:
                if aoColumnsJSVars[var] == column['cclass']:
                    output += '"%s":%d,' % (var, column['id'])
    return output


def generate_aoColumnDefs_bVisibles(user_settings, aoColumnsNames):
    import json
    bVisibleArray = []
    for column in aoColumnsNames:
        if "{}".format(column['id']) not in user_settings["visibleCols"]:
            column_data = {
                "bVisible": False, 
                "aTargets": [column['id']]
            }
            if column.get('excluded'):
                column_data.update({'bSearchable': False})
            bVisibleArray.append(column_data)
    return json.dumps(bVisibleArray)


def generate_aaSorting(user_settings):
    import json
    return json.dumps([[user_settings['sortingCol'], user_settings['sortingDir']]])


def generate_selectedRows(user_settings):
    import json
    selectedRowsArray = []
    for row in user_settings['selectedRows'].split(','):
        if row:
            selectedRowsArray.append(int(row))
    return json.dumps(selectedRowsArray)


def generate_cellfocus(user_settings):
    cellfocusArray = []
    for row in user_settings['cellfocus'].split(','):
        try:
            row_int = int(row)
        except ValueError:
            row_int = 0
        cellfocusArray.append(row_int)
    return cellfocusArray


@lru_cache(maxsize=10)
def get_caches():
    qgrade_cache = {q.cdb_object_id: q.Name[''] for q in QualityCharacteristics.QCGrade.Query()}
    qdef_unit_cache = {u.cdb_object_id: u.Name[''] for u in QualityCharacteristics.QCUnit.Query()}
    qdef_cache = {
        q.cdb_object_id: {
            'name': q.Name[''],
            'unit': qdef_unit_cache.get(q.unit_object_id),
            'time_window_from': q.time_window_from
        } for q in QCDefinition.Query()
    }
    return qgrade_cache, qdef_cache


def _get_qc_objects(qc_ids, qc_cockpit_app):
    if qc_cockpit_app == "qc_object":
        qc_cls = QualityCharacteristics.ObjectQualityCharacteristic
    elif qc_cockpit_app == "qc_process":
        qc_cls = QualityCharacteristics.ClassQualityCharacteristic
    else:
        raise util.ErrorMessage("cdbqc_elink_cockpit_unknown_app")
    non_empty_qc_ids = [x for x in qc_ids if x]
    qc_objs = qc_cls.KeywordQuery(
        cdb_object_id=non_empty_qc_ids
    ).Query(condition="1=1", access="read")
    return qc_objs


def gethistorydata(qc_ids, qc_cockpit_app, time_window_from=None):
    __load_defs()
    data = {}
    qgrade_cache, qdef_cache = get_caches()
    for qc_obj in _get_qc_objects(qc_ids, qc_cockpit_app):
        qc_id = qc_obj.cdb_object_id
        data[qc_id] = {}
        data[qc_id]['gdata'] = []
        if rule.match(qc_obj):
            qdef = qdef_cache.get(qc_obj.cdbqc_def_object_id)
            if time_window_from is None:
                time_window_from = qdef.get('time_window_from')
            else:
                if not isinstance(time_window_from, datetime.datetime):
                    from cs.platform.web.rest.generic import convert
                    time_window_from = convert.load_datetime(time_window_from)
            data[qc_id]['qcd_name'] = qdef.get('name')
            if qdef.get('unit'):
                data[qc_id]['qcd_unit_name'] = qdef.get('unit')

            # prepare conditions
            conditions = []
            kpi_condition = Expression(
                '=',
                QualityCharacteristics.History.cdbqc_object_id,
                Literal(
                    QualityCharacteristics.History.cdbqc_object_id,
                    qc_id
                )
            ).to_string()
            conditions.append(kpi_condition)

            if time_window_from is not None:
                time_window_condition = Expression(
                    '>=',
                    QualityCharacteristics.History.cdb_cdate,
                    Literal(
                        QualityCharacteristics.History.cdb_cdate,
                        time_window_from
                    )
                ).to_string()
                conditions.append(time_window_condition)

            history_entries = sqlapi.RecordSet2(
                table=QualityCharacteristics.History.__maps_to__,
                condition=" AND ".join(conditions),
                addtl="ORDER BY cdb_cdate"
            )
            for history_entry in history_entries:
                if history_entry.value != NULL:
                    isodate = history_entry.cdb_cdate.isoformat()
                    data[qc_id]['gdata'].append([
                        isodate,
                        history_entry.value,
                        qgrade_cache.get(
                            history_entry.cdbqc_qgrade_object_id,
                            ''
                        )
                    ])
        else:
            raise util.ErrorMessage("cdbqc_elink_cockpit_no_access")
    return data
