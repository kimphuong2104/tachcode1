#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#


import time

from cdb import elink
from cdb import util
from cdb.objects import Rule
from cdb.sqlapi import NULL

from cdb.platform.mom.entities import Entity

from cs.metrics import qualitycharacteristics as QualityCharacteristics
from cs.metrics.cockpit import qc_cockpits


def rule():
    return Rule.ByKeys("cdbqc: visible quality characteristics")

AO_COLUMNS_NAMES = None


def aoColumnsNames():
    global AO_COLUMNS_NAMES
    if AO_COLUMNS_NAMES is None:
        AO_COLUMNS_NAMES = [
            {"title": util.get_label('cdbqc_elink_cockpit_pos'),
             "id": 0,
             "visible": 1, "excluded": 0, "cclass": "pos"},
            {"title": util.get_label('cdbqc_elink_cockpit_state'),
             "id": 1, "visible": 1, "excluded": 0, "cclass": "state"},
            {"title": util.get_label('cdbqc_elink_cockpit_bobj'),
             "id": 2, "visible": 1, "excluded": 0, "cclass": "bobj"},
            {"title": util.get_label('cdbqc_elink_cockpit_kpi'),
             "id": 3, "visible": 1, "excluded": 0, "cclass": "kpi"},
            {"title": util.get_label('cdbqc_elink_cockpit_grp'),
             "id": 4, "visible": 1, "excluded": 0, "cclass": "grp"},
            {"title": util.get_label('cdbqc_elink_cockpit_unit'),
             "id": 5, "visible": 1, "excluded": 0, "cclass": "unit"},
            {"title": util.get_label('cdbqc_elink_cockpit_tar_val'),
             "id": 6, "visible": 1, "excluded": 0, "cclass": "target"},
            {"title": util.get_label('cdbqc_elink_cockpit_value'),
             "id": 7, "visible": 1, "excluded": 0, "cclass": "val"},
            {"title": util.get_label('cdbqc_elink_cockpit_ops'),
             "id": 8, "visible": 1, "excluded": 0, "cclass": "ops"},
            {"title": "", "id": 9, "visible": 1, "excluded": 1,
             "cclass": "statesort"}
        ]
    return AO_COLUMNS_NAMES

aoColumnsJSVars = {"state_column": "state",
                   "kpi_column": "kpi",
                   "unit_column": "unit",
                   "target_value_column": "target",
                   "act_value_column": "val",
                   "aggr_value_column": None,
                   "op_column": "ops",
                   "hidden_state_column": "statesort",
                   "grp_column": "grp",
                   }


def set_user_settings(searchquery, visibleCols, sortingCol, sortingDir, selectedRows, cellfocus):
    result = 0
    try:
        if type(selectedRows) == str and selectedRows != "":
            selectedRowsString = ",".join([selectedRows])
        elif type(selectedRows) == list:
            selectedRowsString = ",".join(selectedRows)
        else:
            selectedRowsString = "-1"
        result = {
            "searchquery": util.PersonalSettings().setValue("elink.apps.qc.prc_cockpit", "searchquery", "" if (not searchquery or searchquery == util.get_label('cdbqc_elink_cockpit_search')) else searchquery),
            "visibleCols": util.PersonalSettings().setValue("elink.apps.qc.prc_cockpit", "visibleCols", ",".join(visibleCols)),
            "sortingCol": util.PersonalSettings().setValue("elink.apps.qc.prc_cockpit", "sortingCol", sortingCol),
            "sortingDir": util.PersonalSettings().setValue("elink.apps.qc.prc_cockpit", "sortingDir", sortingDir),
            "selectedRows": util.PersonalSettings().setValue("elink.apps.qc.prc_cockpit", "selectedRows", selectedRowsString)
        }
        if cellfocus[0] == 'null' or cellfocus[1] == 'null':
            result["cellfocus"] = util.PersonalSettings().setValue("elink.apps.qc.prc_cockpit", "cellfocus", "-1,-1")
        else:
            result["cellfocus"] = util.PersonalSettings().setValue("elink.apps.qc.prc_cockpit", "cellfocus", ",".join(cellfocus))
    except RuntimeError as e:
        qc_cockpits._log_setting_err(e)
    return result


def get_user_settings():
    user_settings = {
        "searchquery": util.PersonalSettings().getValueOrDefault("elink.apps.qc.prc_cockpit", "searchquery", ""),
        "visibleCols": util.PersonalSettings().getValueOrDefault("elink.apps.qc.prc_cockpit", "visibleCols", "1,2,3,4,5,6,7,8"),
        "sortingCol": util.PersonalSettings().getValueOrDefault("elink.apps.qc.prc_cockpit", "sortingCol", "0"),
        "sortingDir": util.PersonalSettings().getValueOrDefault("elink.apps.qc.prc_cockpit", "sortingDir", "asc"),
        "selectedRows": util.PersonalSettings().getValueOrDefault("elink.apps.qc.prc_cockpit", "selectedRows", "-1,"),
        "cellfocus": util.PersonalSettings().getValueOrDefault("elink.apps.qc.prc_cockpit", "cellfocus", "-1,-1")
    }
    return user_settings


def _format_grouping_value(qc):
    from cdb.objects import ByID
    groupings = []
    for grouping in qc.Groupings:
        if grouping is not None and grouping.attribute_value is not None and grouping.attribute_value is not NULL:
            obj = ByID(grouping.attribute_value)
            if obj:
                groupings.append(obj.GetDescription())
            else:
                groupings.append(grouping.attribute_value)
    return ",".join(groupings)


def get_render_data():
    qc_table = QualityCharacteristics.ClassQualityCharacteristic.__maps_to__
    qcd_table = QualityCharacteristics.ClassQCDefinition.__maps_to__
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
                qcd.{qcd_condition}
    """.format(qc_table=qc_table,
               qcd_table=qcd_table,
               qcd_condition=objqcdef_ti.condition(['status'],
                                                   [str(QualityCharacteristics.ClassQCDefinition.VALID.status)]))
    qcs = QualityCharacteristics.ClassQualityCharacteristic.SQL(stmt)
    cls_qc_list = [qc for qc in qcs if (rule().match(qc) and qc.CheckAccess("read"))]
    data = []
    for qc in cls_qc_list:
        qc_dict = {}
        check = qc_cockpits.checktarget(qc)
        qc_dict['infourl'] = qc.MakeURL("CDB_ShowObject")
        qc_dict['obj'] = qc
        qc_dict["status"] = check
        bobj = Entity.ByKeys(qc.classname)
        title = bobj.Title[''] if bobj else ""
        qc_dict["bobj"] = title
        qc_def_obj = qc.Definition
        qc_dict["kpi"] = qc_def_obj.Name['']
        qc_dict["description"] = qc_def_obj.GetText("cdbqc_definition_txt")
        qc_dict["grp"] = _format_grouping_value(qc)
        qc_dict["unit"] = qc_def_obj.Unit.Name[''] if qc_def_obj.Unit else ""
        qc_dict["pos"] = qc_def_obj.priority if qc_def_obj else ''
        target_val = qc.target_value if qc.target_value != NULL else ""
        qc_dict["target"] = target_val
        act_val = qc.GetFormattedValue('act_value') if qc.act_value != NULL else ""
        qc_dict["val"] = act_val
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
    result = {"qc_process_columns": aoColumnsNames(),
              "qc_process_data": data,
              "qc_process_settings": qc_cockpits.generate_qc_js_settings(
                  "qc_process", user_settings,
                  aoColumnsNames(), aoColumnsJSVars)}

    return result


class Mainpage(elink.Template):
    '''
    Main HTML-page containing the eLINK Template.
    '''

    __template__ = "qc_process.html"

    '''
    This method defines the content, which is visible in the eLINK panel

    @param context:
        context the method is called out of
    @param **varkw:
        additional parameters (regular a dictionary)
    '''
    def render(self, context, **varkw):
        self.request.charset = "utf-8"
        from cs.metrics.cockpit import QCCockpitTools
        qc_cockpit_tools = QCCockpitTools.get_qc_tools()
        result = {"time": time.ctime()}
        result.update(qc_cockpit_tools)
        return result
