#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

# ----------------------- Custom Providers for Reports ------------------------

from __future__ import absolute_import
from cdb import sqlapi
from cdb import misc
from cs.tools import powerreports as PowerReports
from cdb.objects.org import Organization
from cs.costing.calculations import Calculation
from cs.costing.parameters import ResultValue
from cs.costing.parameters import ParameterDefinition
from cs.costing.components import Delivery
from cs.costing.components import Component
from cs.pcs.costs.reports import Sheet
from cs.pcs.costs.reports import Positions
import six


__all__ = ["CalculationInformationProvider",
           "CalculationResultProvider"]


def log(msg):
    misc.cdblogv(misc.kLogMsg, 7, msg)


class CalculationCostingProvider(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_1
    CALL_CARD = PowerReports.CARD_1

    def getData(self, parent_result, source_args, **kwargs):
        r = PowerReports.ReportData(self)
        return r

    def getSchema(self):
        t = PowerReports.XSDType(self.CARD)
        return t

    def getClass(self):
        return Calculation


class CalculationCostingYearly(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_1

    def getData(self, parent_result, source_args, **kwargs):
        results = PowerReports.ReportDataList(self)
        calc = parent_result.getObject()
        prj = calc.Project
        schema_id = calc.schema_object_id
        element_codes = self.getParameter("element_codes", "").split(",")
        def_elements = []
        for code in element_codes:
            if code:
                element_list = ParameterDefinition.KeywordQuery(code=code, schema_object_id=schema_id)
                if element_list:
                    def_elements.append(element_list[0])

        dia_start = int(calc.sop)
        temp_year = dia_start

        u"""
           Für fünf Jahre ab dem Jahr nach dem Projektende, alle Lieferungen, jährlich betrachten die zum Angebot gehören und deren Kalkulationsergebnisse
           aufsummieren
        """
        elements_year = {}
        for i in six.moves.range(0, 6):
            elements_year[temp_year] = {}
            qry = "calc_object_id='%s' and sales_year='%s'" % (calc.cdb_object_id, temp_year)
            deliveries_in_year = Delivery.Query(qry)
            for delivery in deliveries_in_year:
                for element in def_elements:
                    temp_value = ResultValue.KeywordQuery(context_object_id=delivery.cdb_object_id,
                                                          rdef_object_id=element.cdb_object_id)
                    if temp_value:
                        elements_year[temp_year][temp_value[0].result_name_de] = temp_value[0].value
                    else:
                        elements_year[temp_year][element.ml_name_de] = 0.0
            if not deliveries_in_year:
                for element in def_elements:
                    elements_year[temp_year][element.ml_name_de] = 0.0
            temp_year += 1

        for elem in def_elements:
            if elem.ml_name_de not in elements_year[dia_start + 0]:
                continue
            r = PowerReports.ReportData(self)
            r["elements_name_de"] = elem.ml_name_de
            r["elements_name_en"] = elem.ml_name_en
            r["year_0"] = elements_year[dia_start + 0][elem.ml_name_de]
            r["year_1"] = elements_year[dia_start + 1][elem.ml_name_de]
            r["year_2"] = elements_year[dia_start + 2][elem.ml_name_de]
            r["year_3"] = elements_year[dia_start + 3][elem.ml_name_de]
            r["year_4"] = elements_year[dia_start + 4][elem.ml_name_de]
            r["year_5"] = elements_year[dia_start + 5][elem.ml_name_de]
            results += r

        return results

    def getSchema(self):
        t = PowerReports.XSDType(self.CARD)
        t.add_attr("elements_name_de", sqlapi.SQL_CHAR)
        t.add_attr("elements_name_en", sqlapi.SQL_CHAR)
        t.add_attr("year_0", sqlapi.SQL_FLOAT)
        t.add_attr("year_1", sqlapi.SQL_FLOAT)
        t.add_attr("year_2", sqlapi.SQL_FLOAT)
        t.add_attr("year_3", sqlapi.SQL_FLOAT)
        t.add_attr("year_4", sqlapi.SQL_FLOAT)
        t.add_attr("year_5", sqlapi.SQL_FLOAT)
        return t

    def getClass(self):
        return Calculation


class CalculationCostingYearly_Label(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_1
    CALL_CARD = PowerReports.CARD_1

    def getData(self, parent_result, source_args, **kwargs):
        calc = parent_result.getObject()
        dia_start = int(calc.sop)
        r = PowerReports.ReportData(self)
        for i in six.moves.range(0, 6):
            r["years_%s" % i] = dia_start + i
        return r

    def getSchema(self):
        t = PowerReports.XSDType(self.CARD)
        t.add_attr("years_0", sqlapi.SQL_INTEGER)
        t.add_attr("years_1", sqlapi.SQL_INTEGER)
        t.add_attr("years_2", sqlapi.SQL_INTEGER)
        t.add_attr("years_3", sqlapi.SQL_INTEGER)
        t.add_attr("years_4", sqlapi.SQL_INTEGER)
        t.add_attr("years_5", sqlapi.SQL_INTEGER)
        return t

    def getClass(self):
        return Calculation


class CalculationInformationProvider(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_1
    CALL_CARD = PowerReports.CARD_1

    def getData(self, parent_result, source_args, **kwargs):
        calc = parent_result.getObject()
        prj = calc.Project
        product = calc.Product
        r = PowerReports.ReportData(self)
        if calc.category_name_de:
            r["calc_type_de"] = calc.category_name_de
        if calc.category_name_en:
            r["calc_type_en"] = calc.category_name_en
        if calc.costplant_object_id:
            org = Organization.KeywordQuery(cdb_object_id=calc.costplant_object_id)
            if org:
                r["calc_plant"] = org[0].name
        if calc.Currency:
            r["calc_currency"] = calc.Currency.name
        if prj:
            managers = [x.name for x in prj.getProjectManagers()]
            r["calc_manager"] = " / ".join(managers)
            if prj.customer:
                cstm = Organization.ByKeys(prj.customer)
                if cstm:
                    r["calc_customer"] = cstm.name
        if product:
            r["calc_product_name_de"] = product.name_de
            r["calc_product_name_en"] = product.name_en
        return r

    def getSchema(self):
        t = PowerReports.XSDType(self.CARD)
        t.add_attr("calc_currency", sqlapi.SQL_CHAR)
        t.add_attr("calc_customer", sqlapi.SQL_CHAR)
        t.add_attr("calc_type_de", sqlapi.SQL_CHAR)
        t.add_attr("calc_type_en", sqlapi.SQL_CHAR)
        t.add_attr("calc_manager", sqlapi.SQL_CHAR)
        t.add_attr("calc_product_name_de", sqlapi.SQL_CHAR)
        t.add_attr("calc_product_name_en", sqlapi.SQL_CHAR)
        t.add_attr("calc_plant", sqlapi.SQL_CHAR)
        return t


class CalculationsSumProvider(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_1
    CALL_CARD = PowerReports.CARD_1

    def getData(self, parent_result, source_args, **kwargs):
        calc = parent_result.getObject()
        r = PowerReports.ReportData(self)
        if calc.ProjectCostSheets:
            r["projectcosts_sum"] = calc.ProjectCostSheets[0].total_costs
            r["projectcosts_name_de"] = calc.ProjectCostSheets[0].name_de
            r["projectcosts_name_en"] = calc.ProjectCostSheets[0].name_en

        totalcosts_code = self.getParameter("totalcosts_code")
        price_code = self.getParameter("price_code")
        dia_start = int(calc.sop)
        totalcosts_list = calc.CalculationSchema.ResultDefinitions.KeywordQuery(code=totalcosts_code)
        price_list = calc.CalculationSchema.ResultDefinitions.KeywordQuery(code=price_code)
        if price_list and totalcosts_list:
            r["totalcosts_name_de"] = totalcosts_list[0].ml_name_de
            r["totalcosts_name_en"] = totalcosts_list[0].ml_name_en
            r["price_name_de"] = price_list[0].ml_name_de
            r["price_name_en"] = price_list[0].ml_name_en
            temp_year = dia_start
            for i in six.moves.range(0, 6):
                qry = "calc_object_id='%s' and sales_year='%s'" % (calc.cdb_object_id, temp_year)
                deliveries_in_year = Delivery.Query(qry)
                for delivery in deliveries_in_year:
                    costs_value = ResultValue.KeywordQuery(context_object_id=delivery.cdb_object_id,
                                                           rdef_object_id=totalcosts_list[0].cdb_object_id)
                    if costs_value:
                        r["totalcosts_year_%s" % i] = costs_value[0].value
                    price_value = ResultValue.KeywordQuery(context_object_id=delivery.cdb_object_id,
                                                           rdef_object_id=price_list[0].cdb_object_id)
                    if price_value:
                        r["price_year_%s" % i] = price_value[0].value
                temp_year += 1
                if not r.get_attr("totalcosts_year_%s" % i):
                    r["totalcosts_year_%s" % i] = 0.0
                if not r.get_attr("price_year_%s" % i):
                    r["price_year_%s" % i] = 0.0
        return r

    def getSchema(self):
        t = PowerReports.XSDType(self.CARD)
        t.add_attr("projectcosts_sum", sqlapi.SQL_FLOAT)
        t.add_attr("projectcosts_name_de", sqlapi.SQL_CHAR)
        t.add_attr("projectcosts_name_en", sqlapi.SQL_CHAR)
        t.add_attr("totalcosts_name_de", sqlapi.SQL_CHAR)
        t.add_attr("totalcosts_name_en", sqlapi.SQL_CHAR)
        t.add_attr("totalcosts_year_0", sqlapi.SQL_FLOAT)
        t.add_attr("totalcosts_year_1", sqlapi.SQL_FLOAT)
        t.add_attr("totalcosts_year_2", sqlapi.SQL_FLOAT)
        t.add_attr("totalcosts_year_3", sqlapi.SQL_FLOAT)
        t.add_attr("totalcosts_year_4", sqlapi.SQL_FLOAT)
        t.add_attr("totalcosts_year_5", sqlapi.SQL_FLOAT)
        t.add_attr("price_name_de", sqlapi.SQL_CHAR)
        t.add_attr("price_name_en", sqlapi.SQL_CHAR)
        t.add_attr("price_year_0", sqlapi.SQL_FLOAT)
        t.add_attr("price_year_1", sqlapi.SQL_FLOAT)
        t.add_attr("price_year_2", sqlapi.SQL_FLOAT)
        t.add_attr("price_year_3", sqlapi.SQL_FLOAT)
        t.add_attr("price_year_4", sqlapi.SQL_FLOAT)
        t.add_attr("price_year_5", sqlapi.SQL_FLOAT)

        return t


class CalculationProjectCostsProvider(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_1

    def getData(self, parent_result, source_args, **kwargs):
        calc = parent_result.getObject()
        results = PowerReports.ReportDataList(self)
        if calc.ProjectCostSheets:
            sheet = calc.ProjectCostSheets[0]
            for f in sheet.TopFolders:
                data = PowerReports.ReportData(self)
                data["name_de"] = f.name_de
                data["name_en"] = f.name_de
                data["value"] = f.folder_costs
                results += data
        return results

    def getSchema(self):
        t = PowerReports.XSDType(self.CARD)
        t.add_attr("name_de", sqlapi.SQL_CHAR)
        t.add_attr("name_en", sqlapi.SQL_CHAR)
        t.add_attr("value", sqlapi.SQL_FLOAT)
        return t


class CalculationResultProvider(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_1

    # To make the report layout nicer:
    # fill out all of the columns using dummies.
    __SHOW_COLUMNS__ = 6

    def getData(self, parent_result, source_args, **kwargs):
        results = PowerReports.ReportDataList(self)
        calc = parent_result.getObject()

        calc_para = Calculation._get_own_parameter_values(record=calc,
                                                          classname=None,
                                                          calculation=calc,
                                                          ctx=None,
                                                          exch_factor={})
        sqlstr = "select r.value, rd.ml_name_de, rd.ml_name_en, rd.code, r.rdef_object_id "
        sqlstr += "from cdbpco_result_val r, cdbpco_para_def rd "
        sqlstr += "where r.context_object_id='%s'" % calc.cdb_object_id
        sqlstr += " and r.rdef_object_id=rd.cdb_object_id and rd.help_value<>1"
        sqlstr += " order by rd.order_no asc"
        rvals = sqlapi.RecordSet2(sql=sqlstr)
        namelist = []
        if len(rvals) > 0:
            ordermap = {}
            orderno = 0

            # Highlighting & Parameters
            highlighting = self.getParameter("highlighting", "").split(",")
            hiding = self.getParameter("hiding", "").split(",")
            # read relative parameters, get their reference parameter
            relpara = {}
            relparas = self.getParameter("relpara", "").split(",")
            for para in relparas:
                splt = para.split(":")
                if len(splt) == 2:
                    relpara[splt[0]] = calc_para.get("values", {}).get(splt[1], "")
            # cache ResultDefinition
            rdefs = {}

            # the order of results here defines the pivot table column order
            # "total" at first
            from cdb import i18n
            lbl_name = "cdbpco_report_label_total"
            rep_lang = source_args.get("cdbxml_report_lang", i18n.default())
            total_label = ""
            if rep_lang and rep_lang != i18n.default():
                from cdb.platform import gui
                tlbl = gui.Label.ByKeys(lbl_name)
                if tlbl:
                    total_label = tlbl.Text[rep_lang]
            if not total_label:
                from cdb import util
                total_label = util.Labels()["cdbpco_report_label_total"]
            for rval in rvals:
                if rval.code in hiding:
                    # hide this result as required
                    continue
                orderno += 1
                ordermap[rval.rdef_object_id] = orderno
                r = PowerReports.ReportData(self, rval)
                r["context_name"] = total_label
                r["order_no"] = orderno
                r["display_type"] = ""
                r["name"] = rval["ml_name_%s" % rep_lang]
                if rval.code in highlighting:
                    r["display_type"] = "1"
                r["display_para"] = relpara.get(rval.code, "")
                rdefs[rval.rdef_object_id] = \
                    (rval.code, rval["ml_name_%s" % rep_lang],
                     r["display_type"], r["display_para"])
                results.append(r)

            # then Products, DeliveryUnits, Deliveries:
            #   that can be configured by setting report parameters.
            cobjs = []
            if source_args.get("show_result_product", "") == "1":
                cobjs += list(calc.Products)
            if source_args.get("show_result_component", "") == "1":
                cobjs += list(calc.TopComponents)
            if source_args.get("show_result_delivery", "") == "1":
                cobjs += list(calc.Deliveries)
            for cobj in cobjs:
                for rval in cobj.ResultValues:
                    r = PowerReports.ReportData(self, rval)
                    r["order_no"] = ordermap.get(rval.rdef_object_id, "")
                    if r["order_no"] == "":
                        # skip current result(hidden)
                        continue
                    (r["code"], r["name"],
                     r["display_type"], r["display_para"]) = \
                        rdefs.get(rval.rdef_object_id, ("", "", "", ""))
                    r["context_name"] = cobj.name
                    results.append(r)
                    if r["context_name"] not in namelist:
                        namelist.append(r["context_name"])
            # Fill out the columns with dummies
            if len(results) and len(namelist) < self.__SHOW_COLUMNS__:
                for idx in six.moves.range(self.__SHOW_COLUMNS__ - len(namelist)):
                    dummy_result = PowerReports.ReportData(self)
                    dummy_result["context_name"] = "#" * (idx + 1)
                    dummy_result["value"] = ""
                    for (k, v) in results[-1].items():
                        if k not in dummy_result.keys():
                            dummy_result[k] = v
                    results.append(dummy_result)
        return results

    def getSchema(self):
        t = PowerReports.XSDType(self.CARD)
        t.add_attr("order_no", sqlapi.SQL_INTEGER)
        t.add_attr("name", sqlapi.SQL_CHAR)
        t.add_attr("value", sqlapi.SQL_FLOAT)
        t.add_attr("code", sqlapi.SQL_CHAR)
        t.add_attr("context_name", sqlapi.SQL_CHAR)
        t.add_attr("display_type", sqlapi.SQL_INTEGER)
        t.add_attr("display_para", sqlapi.SQL_FLOAT)
        return t


class ProjectCostSheet(Sheet):
    def __init__(self, *args, **kwargs):
        super(ProjectCostSheet, self).__init__(*args, **kwargs)
        self.XSDSchemaItems["calculation_name"] = sqlapi.SQL_CHAR

    def getData(self, parent_result, source_args, **kwargs):
        data = super(ProjectCostSheet, self).getData(parent_result, source_args, **kwargs)
        parent = parent_result.getObject()
        data["calculation_name"] = parent.name
        return data


class ProjectCostPositions(Positions):
    def getPositionData(self, position, level):
        data = PowerReports.ReportData(self)
        data["cdbxml_level"] = level
        data["name_de"] = position.name_de if position.name_de else position.name_en
        data["name_en"] = position.name_en if position.name_en else position.name_de
        if position.CostType:
            data["costtype_name_de"] = position.CostType.name_de
            data["costtype_name_en"] = position.CostType.name_en
        if position.CostCenter:
            data["costcenter_name_de"] = position.CostCenter.name_de
            data["costcenter_name_en"] = position.CostCenter.name_en
        if position.Task:
            data["task_name"] = position.Task.task_name
        if position.costplant_object_id:
            data["costplant_name"] = Organization.KeywordQuery(cdb_object_id=position.costplant_object_id)[0].name
        if position.component_object_id:
            product = Component.ByKeys(cdb_object_id=position.component_object_id)
            if product:
                data["part_name"] = product.name
        data["costs"] = position.costs_proj_curr
        data["effort"] = position.effort
        data["hourly_rate"] = position.hourly_rate
        data["begin"] = position.start_time
        data["end"] = position.end_time
        if position.Currency:
            data["currency_symbol"] = position.Currency.symbol
        if position.Project.Currency:
            data["proj_currency_symbol"] = position.Project.Currency.symbol
        return data
