#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#


'''
Created on 08.08.2012

@author: kad, khi
'''
from cdb import elink
from cdb import fls
from cs.metrics import qualitycharacteristics as QualityCharacteristics
from cdb.objects import Rule, NULL
from cs.metrics.cockpit.qc_cockpits import checktarget
from cs.metrics.cockpit.qc_cockpits import check_act_value
from cs.metrics.cockpit.qc_cockpits import _log_setting_err
from cs.metrics.cockpit.qc_cockpits import generate_qc_js_settings
from cdb import util
from cdb.objects.PersonalObjectSettings import PersonalObjectSetting
import time
import json

QGRADE_COMPUTED_NAME = 'berechnet'
QGRADE_AGGREGATED_NAME = 'aggregiert'
QGRADE_MANUAL_NAME = 'manuell'


def aoColumnsNames():
    return [
        {"title": util.get_label('cdbqc_elink_cockpit_pos'), "id": 0, "visible": 1, "excluded": 0, "cclass": "pos"},
        {"title": util.get_label('cdbqc_elink_cockpit_state'), "id": 1, "visible": 1, "excluded": 0, "cclass": "state"},
        {"title": util.get_label('cdbqc_elink_cockpit_kpi'), "id": 2, "visible": 1, "excluded": 0, "cclass": "kpi"},
        {"title": util.get_label('cdbqc_elink_cockpit_unit'), "id": 3, "visible": 1, "excluded": 0, "cclass": "unit"},
        {"title": util.get_label('cdbqc_elink_cockpit_tar_val'), "id": 4, "visible": 1, "excluded": 0, "cclass": "target"},
        {"title": util.get_label('cdbqc_elink_cockpit_value'), "id": 5, "visible": 1, "excluded": 0, "cclass": "val"},
        {"title": util.get_label('cdbqc_elink_cockpit_qgrade'), "id": 6, "visible": 1, "excluded": 0, "cclass": "qgrade"},
        {"title": util.get_label('cdbqc_elink_cockpit_aggr'), "id": 7, "visible": 1, "excluded": 0, "cclass": "aggr"},
        {"title": util.get_label('cdbqc_elink_cockpit_ops'), "id": 8, "visible": 1, "excluded": 0, "cclass": "ops"},
        {"title": "", "id": 9, "visible": 1, "excluded": 1, "cclass": "statesort"}
    ]

aoColumnsJSVars = {"state_column": "state",
                   "kpi_column": "kpi",
                   "unit_column": "unit",
                   "target_value_column": "target",
                   "act_value_column": "val",
                   "aggr_value_column": "aggr",
                   "op_column": "ops",
                   "hidden_state_column": "statesort",
                   "grp_column": None,
                   }


def get_all_but_named_qgrade_names(qgrade_dict, name_de):
    return {key: qgrade.Name['']
            for key, qgrade in qgrade_dict.items()
            if qgrade.name_de != name_de}


def get_qgrade_dict(qgrades):
    return {qgrade.cdb_object_id: qgrade
            for qgrade in qgrades}


def get_named_qgrade(qgrade_dict, name_de):
    for v in qgrade_dict.values():
        if v.name_de == name_de:
            return v

obj_id = None


def rule():
    return Rule.ByKeys("cdbqc: visible quality characteristics")


def set_user_settings(searchquery, visibleCols, sortingCol, sortingDir, selectedRows, cellfocus):
    result = 0
    if visibleCols and sortingCol and sortingDir and selectedRows and cellfocus and obj_id:
        try:
            if type(selectedRows) == str and selectedRows != "":
                selectedRowsString = ",".join([selectedRows])
            elif type(selectedRows) == list:
                selectedRowsString = ",".join(selectedRows)
            else:
                selectedRowsString = "-1"
            PersonalObjectSetting.setValue(obj_id, "elink.apps.qc.obj_cockpit/searchquery", "" if (not searchquery or searchquery == util.get_label('cdbqc_elink_cockpit_search')) else searchquery)
            PersonalObjectSetting.setValue(obj_id, "elink.apps.qc.obj_cockpit/visibleCols", ",".join(visibleCols))
            PersonalObjectSetting.setValue(obj_id, "elink.apps.qc.obj_cockpit/sortingCol", sortingCol)
            PersonalObjectSetting.setValue(obj_id, "elink.apps.qc.obj_cockpit/sortingDir", sortingDir)
            PersonalObjectSetting.setValue(obj_id, "elink.apps.qc.obj_cockpit/selectedRows", selectedRowsString)
            if cellfocus[0] == 'null' or cellfocus[1] == 'null':
                PersonalObjectSetting.setValue(obj_id, "elink.apps.qc.obj_cockpit/cellfocus", "-1,-1")
            else:
                PersonalObjectSetting.setValue(obj_id, "elink.apps.qc.obj_cockpit/cellfocus", ",".join(cellfocus))
            result = 1
        except RuntimeError as e:
            _log_setting_err(e)
    else:
        result = {"visibleCols": visibleCols, "searchquery": searchquery, "sortingCol": sortingCol, "sortingDir": sortingDir, "selectedRows": selectedRows}
    return result


def get_user_settings():
    # if possible use the improved version E038920
    if hasattr(PersonalObjectSetting, 'getObjectValues'):
        ids_and_defaults = [
            ("elink.apps.qc.obj_cockpit/searchquery", ""),
            ("elink.apps.qc.obj_cockpit/visibleCols", "1,2,3,4,5,6,7,8"),
            ("elink.apps.qc.obj_cockpit/sortingCol", "0"),
            ("elink.apps.qc.obj_cockpit/sortingDir", "asc"),
            ("elink.apps.qc.obj_cockpit/selectedRows", "-1,"),
            ("elink.apps.qc.obj_cockpit/cellfocus", "-1,-1")
        ]
        personal_object_settings = PersonalObjectSetting.getObjectValues(obj_id,
                                                                         ids_and_defaults)
        user_settings = {
            "searchquery": personal_object_settings[0],
            "visibleCols": personal_object_settings[1],
            "sortingCol": personal_object_settings[2],
            "sortingDir": personal_object_settings[3],
            "selectedRows": personal_object_settings[4],
            "cellfocus": personal_object_settings[5]
        }
    else:
        user_settings = {
            "searchquery": PersonalObjectSetting.getValue(obj_id, "elink.apps.qc.obj_cockpit/searchquery", ""),
            "visibleCols": PersonalObjectSetting.getValue(obj_id, "elink.apps.qc.obj_cockpit/visibleCols", "1,2,3,4,5,6,7,8"),
            "sortingCol": PersonalObjectSetting.getValue(obj_id, "elink.apps.qc.obj_cockpit/sortingCol", "0"),
            "sortingDir": PersonalObjectSetting.getValue(obj_id, "elink.apps.qc.obj_cockpit/sortingDir", "asc"),
            "selectedRows": PersonalObjectSetting.getValue(obj_id, "elink.apps.qc.obj_cockpit/selectedRows", "-1,"),
            "cellfocus": PersonalObjectSetting.getValue(obj_id, "elink.apps.qc.obj_cockpit/cellfocus", "-1,-1")
        }
    return user_settings


def isValueReadOnly(qc):
    return qc.Definition.computed or isTakeAggrVal(qc)


def save_actual_value(qc_id, act_value, qgrade):
    # allocate license for feature "Metrics: Write Values"
    fls.allocate_license("METRICS_002")

    qc = QualityCharacteristics.ObjectQualityCharacteristic.ByKeys(qc_id)
    qc = qc if qc.CheckAccess("read") else None

    if not qc:
        raise util.ErrorMessage("cdbqc_elink_cockpit_invalid_qc")
    else:
        if rule().match(qc):
            if not isValueReadOnly(qc):
                if act_value != "" and not check_act_value(act_value):
                    raise util.ErrorMessage("cdbqc_elink_cockpit_invalid_act")

                qgrade_obj = QualityCharacteristics.QCGrade.ByKeys(qgrade)
                if not qgrade_obj:
                    raise util.ErrorMessage("cdbqc_elink_cockpit_invalid_qgrade")

                qc.set_actual_value(act_value, guetegrad=qgrade_obj.Name['de'])
            else:
                raise util.ErrorMessage("cdbqc_elink_cockpit_uneditable_val")
        else:
            raise util.ErrorMessage("cdbqc_elink_cockpit_no_access")

    return {"color": checktarget(qc)}


def isTakeAggrVal(qc_obj):
    assos = qc_obj.Definition.Associations.Execute()
    if assos:
        return assos[0].take_aggr_val
    raise util.ErrorMessage("cdbqc_elink_cockpit_no_asso")


def get_render_data(cdb_object_id):
    qc_table = QualityCharacteristics.ObjectQualityCharacteristic.__maps_to__
    objqc_ti = util.TableInfo(qc_table)
    qcd_table = QualityCharacteristics.ObjectQCDefinition.__maps_to__
    objqcdef_ti = util.TableInfo(qcd_table)
    stmt = """
            SELECT
                qc.*
            FROM
                {qc_table} qc,
                {qcd_table} qcd
            WHERE
                qc.cdbqc_def_object_id = qcd.cdb_object_id
                AND
                qc.{qc_condition}
                AND
                qcd.{qcd_condition}
    """.format(qc_table=qc_table,
               qcd_table=qcd_table,
               qc_condition=objqc_ti.condition(['cdbf_object_id'],
                                               [cdb_object_id]),
               qcd_condition=objqcdef_ti.condition(['status'],
                                                   [str(QualityCharacteristics.ObjectQCDefinition.VALID.status)]))
    qcs = QualityCharacteristics.ObjectQualityCharacteristic.SQL(stmt)
    obj_qc_list = [qc for qc in qcs if (rule().match(qc) and qc.CheckAccess("read"))]
    data = []
    qgrades = QualityCharacteristics.QCGrade.Query(access="read").Execute()
    qgrade_dict = get_qgrade_dict(qgrades)
    qgrade_js_dict = get_all_but_named_qgrade_names(qgrade_dict, name_de=QGRADE_COMPUTED_NAME)
    for qc in obj_qc_list:
        qc_dict = {}
        qc_dict['infourl'] = qc.MakeURL("CDB_ShowObject")
        qc_dict['obj'] = qc
        check = checktarget(qc)
        qc_dict["status"] = check
        qc_def_obj = qc.Definition
        qc_dict["kpi"] = qc_def_obj.Name['']
        qc_dict["description"] = qc_def_obj.GetText("cdbqc_definition_txt")
        qc_dict["grp"] = ""
        qc_dict["unit"] = qc_def_obj.Unit.Name[''] if qc_def_obj.Unit else ""
        qc_dict["pos"] = qc_def_obj.priority if qc_def_obj else ''
        target_val = qc.target_value if qc.target_value != NULL else ""
        qc_dict["target"] = target_val
        act_val = qc.GetFormattedValue('act_value') if qc.act_value != NULL else ""
        qc_dict["val"] = act_val
        qc_dict["apply_aggr"] = isTakeAggrVal(qc)
        qc_dict["computed"] = qc_def_obj.computed
        qc_dict["uneditable"] = 1 if isValueReadOnly(qc) else 0
        qgrade = qc.getGrade()
        if qgrade:
            qc_dict["grade"] = qgrade
        elif qc_dict["apply_aggr"]:
            qc_dict["grade"] = get_named_qgrade(qgrade_dict, QGRADE_AGGREGATED_NAME).Name['']
        elif qc_dict["computed"]:
            qc_dict["grade"] = get_named_qgrade(qgrade_dict, QGRADE_COMPUTED_NAME).Name['']
        else:
            qc_dict["grade"] = ""

        qc_dict["aggr_val"] = qc.GetFormattedValue('aggr_value') if qc.aggr_value != NULL else ""
        qc_dict["obj_id"] = qc.cdb_object_id
        if check == "gruen":
            qc_dict["statesort"] = "1_%s" % util.get_label('cdbqc_elink_cockpit_green')
            qc_dict['color'] = util.get_label('cdbqc_elink_cockpit_green')
            qc_dict['colormsg'] = util.get_label('cdbqc_elink_cockpit_green_qc')
        elif check == "rot":
            qc_dict["statesort"] = "2_%s" % util.get_label('cdbqc_elink_cockpit_red')
            qc_dict['color'] = util.get_label('cdbqc_elink_cockpit_red')
            qc_dict['colormsg'] = util.get_label('cdbqc_elink_cockpit_red_qc')
        else:
            qc_dict["statesort"] = "0_%s" % util.get_label('cdbqc_elink_cockpit_no_state')
        data.append(qc_dict)
    user_settings = get_user_settings()
    result = {"qc_object_columns": aoColumnsNames(),
              "qc_object_data": data,
              "qc_object_settings": generate_qc_js_settings("qc_object",
                                                            user_settings,
                                                            aoColumnsNames(),
                                                            aoColumnsJSVars,
                                                            get_named_qgrade(qgrade_dict, QGRADE_AGGREGATED_NAME).cdb_object_id,
                                                            json.dumps(qgrade_js_dict),
                                                            get_named_qgrade(qgrade_dict, QGRADE_MANUAL_NAME).cdb_object_id)}
    return result


class Mainpage(elink.Template):
    '''
    Main HTML-page containing the eLINK Template.
    '''
    new_page_title = ""

    ''' Name of the template '''
    __template__ = "qc_object.html"

    '''
    This method defines the content, which is visible in the eLINK panel

    @param context:
        context the method is called out of
    @param **varkw:
        additional parameters (regular a dictionary)
    '''
    def render(self, context, **varkw):
        self.request.charset = "utf-8"
        global obj_id
        global reload_cockpit
        from cdb.objects import ByID
        if "cdb_object_id" in varkw:
            obj_id = varkw["cdb_object_id"]
            fobj = ByID(obj_id)
            if fobj:
                new_page_title = fobj.GetDescription() + " - KPI Cockpit"
            else:
                raise util.ErrorMessage("cdbqc_elink_cockpit_invalid_qc")
        else:
            raise util.ErrorMessage("cdbqc_elink_cockpit_invalid_qc")
        from cs.metrics.cockpit import QCCockpitTools
        qc_cockpit_tools = QCCockpitTools.get_qc_tools()
        result = {"cdb_object_id": obj_id, "page_title": new_page_title, "time": time.ctime()}
        result.update(qc_cockpit_tools)
        return result
