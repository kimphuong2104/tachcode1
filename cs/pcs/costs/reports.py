# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/


import six

from cdb import i18n, sqlapi
from cdb.objects.org import Organization
from cs.currency import Currency
from cs.pcs.costs.definitions import CostSignificance
from cs.pcs.costs.sheets import CostPosition, CostSheet, CostSheetFolderPosition
from cs.tools import powerreports as PowerReports

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


def get_filtered_language_fields(rel, base_name):
    # default filter to de, en for higher performance, can be customized
    field_names = i18n.iso_columns(rel, base_name)
    return [field_names.get(lang) for lang in list(field_names) if lang in ["de", "en"]]


class Sheet(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_1
    CALL_CARD = PowerReports.CARD_1

    XSDSchemaItems = {
        "costsignificance_name_de": sqlapi.SQL_CHAR,
        "costsignificance_name_en": sqlapi.SQL_CHAR,
        "currency_name": sqlapi.SQL_CHAR,
        "project_name": sqlapi.SQL_CHAR,
        "project_description": sqlapi.SQL_CHAR,
        "total_effort": sqlapi.SQL_FLOAT,
        "total_costs": sqlapi.SQL_FLOAT,
    }

    def __init__(self, *args, **kwargs):
        super(Sheet, self).__init__(*args, **kwargs)
        joined_status_name_ml_fields = get_filtered_language_fields(
            CostSheet.__maps_to__ + "_v", "joined_status_name_"
        )
        for field_name in joined_status_name_ml_fields:
            self.XSDSchemaItems[field_name] = sqlapi.SQL_CHAR

    def getSchema(self):
        schema = PowerReports.XSDType(self.CARD, "cdbpcs_cost_sheet")
        for attr, sqlType in list(six.iteritems(self.XSDSchemaItems)):
            schema.add_attr(attr, sqlType)
        return schema

    def getData(self, parent_result, source_args, **kwargs):
        parent = parent_result.getObject()
        costsignificance_id = self.getParameter("significance_id")
        parenthasproject = self.getParameter("parent_has_project")

        if not costsignificance_id:
            costsignificance_id = parent.costsignificance_object_id
            costsignificance = CostSignificance.ByKeys(costsignificance_id)
        else:
            costsignificance = CostSignificance.KeywordQuery(id=costsignificance_id)[0]
            project = parent
        if parenthasproject:
            project = parent.Project

        sheets = CostSheet.KeywordQuery(
            cdb_project_id=parent.cdb_project_id,
            costsignificance_object_id=costsignificance.cdb_object_id,
            cdb_obsolete=0,
        ).Execute()
        if sheets:
            sheet = sheets[0]
            data = PowerReports.ReportData(self, sheet)
            currency = Currency.ByKeys(project.currency_object_id)
            if currency:
                data["currency_name"] = currency.name
            data["project_name"] = project.project_name
            data["project_description"] = project.GetDescription()
            data["costsignificance_name_de"] = costsignificance.name_de
            data["costsignificance_name_en"] = costsignificance.name_en
            data["joined_status_name_de"] = sheet.joined_status_name_de
            data["joined_status_name_en"] = sheet.joined_status_name_en
            rs = sqlapi.RecordSet2(
                "cdbpcs_cost_sheet_v", f"cdb_object_id = '{sheet.cdb_object_id}'"
            )
            if len(rs):
                data["total_effort"] = rs[0].total_effort
                data["total_costs"] = rs[0].total_costs
        else:
            data = PowerReports.ReportData(self)
        return data


class Positions(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_1

    XSDSchemaItems = {
        "cdbxml_level": sqlapi.SQL_INTEGER,
        "costtype_name_de": sqlapi.SQL_CHAR,
        "costtype_name_en": sqlapi.SQL_CHAR,
        "costcenter_name_de": sqlapi.SQL_CHAR,
        "costcenter_name_en": sqlapi.SQL_CHAR,
        "costplant_name": sqlapi.SQL_CHAR,
        "task_name": sqlapi.SQL_CHAR,
        "part_name": sqlapi.SQL_CHAR,
        "costs": sqlapi.SQL_FLOAT,
        "effort": sqlapi.SQL_FLOAT,
        "hourly_rate": sqlapi.SQL_FLOAT,
        "begin": sqlapi.SQL_DATE,
        "end": sqlapi.SQL_DATE,
        "currency_symbol": sqlapi.SQL_CHAR,
        "proj_currency_symbol": sqlapi.SQL_CHAR,
    }

    def __init__(self, *args, **kwargs):
        super(Positions, self).__init__(*args, **kwargs)
        name_ml_fields = get_filtered_language_fields(CostPosition.__maps_to__, "name_")
        for field_name in name_ml_fields:
            self.XSDSchemaItems[field_name] = sqlapi.SQL_CHAR

    def getSchema(self):
        schema = PowerReports.XSDType(self.CARD)
        for attr, sqlType in list(six.iteritems(self.XSDSchemaItems)):
            schema.add_attr(attr, sqlType)
        return schema

    # TODO: PERFORMANCE !!!
    def getData(self, parent_result, source_args, **kwargs):
        result = PowerReports.ReportDataList(self)
        sheet = parent_result.getObject()
        if sheet:
            level = 0
            already_visited = []
            for folder in sheet.TopFolders:
                self.traverseFolders(folder, level, result, already_visited)
            for pos in CostPosition.KeywordQuery(
                costsheet_object_id=sheet.cdb_object_id
            ):
                if pos.cdb_obsolete == 0 and pos.cdb_object_id not in already_visited:
                    data = self.getPositionData(pos, 0)
                    result += data
        return result

    def traverseFolders(self, folder, level, result, already_visited):
        data = PowerReports.ReportData(self)
        data["cdbxml_level"] = level
        data["name_de"] = folder.name_de if folder.name_de else folder.name_en
        data["name_en"] = folder.name_en if folder.name_en else folder.name_de
        data["costtype_name_de"] = "Ordner"
        data["costtype_name_en"] = "Folder"
        data["costs"] = folder.folder_costs
        data["effort"] = folder.folder_effort
        if folder.folder_costs:
            data["proj_currency_symbol"] = folder.CostSheet.Project.Currency.symbol
        result += data
        for f in folder.SubFolders:
            self.traverseFolders(f, level + 1, result, already_visited)
        csfps = CostSheetFolderPosition.KeywordQuery(
            costsheet_folder_object_id=folder.cdb_object_id
        )
        for csfp in csfps:
            if csfp.CostPosition and csfp.CostPosition.cdb_obsolete == 0:
                pos = csfp.CostPosition
                data = self.getPositionData(pos, level + 1)
                already_visited.append(pos.cdb_object_id)
                result += data

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
            data["costplant_name"] = Organization.KeywordQuery(
                cdb_object_id=position.costplant_object_id
            )[0].name
        data["costs"] = position.costs_proj_curr
        if position.Currency:
            data["currency_symbol"] = position.Currency.symbol
        if position.Project.Currency:
            data["proj_currency_symbol"] = position.Project.Currency.symbol
        data["effort"] = position.effort
        data["hourly_rate"] = position.hourly_rate
        data["begin"] = position.start_time
        data["end"] = position.end_time
        return data


class CostTrends(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_1

    XSDSchemaItems = {
        "monthyear": sqlapi.SQL_CHAR,
        "costs": sqlapi.SQL_FLOAT,
        "effort": sqlapi.SQL_FLOAT,
    }

    def getSchema(self):
        schema = PowerReports.XSDType(self.CARD)
        for attr, sqlType in list(six.iteritems(self.XSDSchemaItems)):
            schema.add_attr(attr, sqlType)
        return schema

    def getData(self, parent_result, source_args, **kwargs):
        result = PowerReports.ReportDataList(self)
        sheet = parent_result.getObject()
        if sheet:
            allpositions = None
            for s in sheet.Project.ValidCostSheets:
                if not allpositions:
                    allpositions = s.Positions
                else:
                    allpositions += s.Positions
            start_month = 0
            end_month = 0
            start_year = 0
            end_year = 0
            # get start/end month/year
            if len([x for x in allpositions if x.start_time is None]) != len(
                allpositions
            ):
                start = min(
                    x.start_time for x in allpositions if x.start_time is not None
                )
                start_year = start.year
                start_month = start.month
            if len([x for x in allpositions if x.end_time is None]) != len(
                allpositions
            ):
                end = max(x.end_time for x in allpositions if x.end_time is not None)
                end_year = end.year
                end_month = end.month
            if start_month and start_year and end_month and end_year:
                costs = 0.00
                effort = 0.00
                for year in six.moves.range(start_year, end_year + 1):
                    start_month_in_year = 1
                    end_month_in_year = 12
                    if start_year == year:
                        start_month_in_year = start_month
                    if end_year == year:
                        end_month_in_year = end_month
                    for month in six.moves.range(
                        start_month_in_year, end_month_in_year + 1
                    ):
                        data = PowerReports.ReportData(self)
                        data["monthyear"] = "%s.%s" % (month, year)
                        db = sqlapi.SQLdbms()
                        if db == sqlapi.DBMS_SQLITE:
                            qry = "cast(strftime('%m',start_time) as integer) = {} and cast(strftime('%Y',start_time) as integer) = {}"
                        elif db in (sqlapi.DBMS_ORACLE, sqlapi.DBMS_POSTGRES):
                            qry = "extract(month from start_time) = {} and extract(year from start_time) = {}"
                        else:
                            qry = "MONTH(start_time) = {} and YEAR(start_time) = {}"
                        for position in sheet.Positions.Query(qry.format(month, year)):
                            costs += (
                                position.costs_proj_curr
                                if position.costs_proj_curr
                                else 0.0
                            )
                            effort += position.effort if position.effort else 0.0
                        data["costs"] = costs
                        data["effort"] = effort
                        result += data
        return result


class CostTrendsTimeframe(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_1

    XSDSchemaItems = {"monthyear": sqlapi.SQL_CHAR}

    def getSchema(self):
        schema = PowerReports.XSDType(self.CARD)
        for attr, sqlType in list(six.iteritems(self.XSDSchemaItems)):
            schema.add_attr(attr, sqlType)
        return schema

    def getData(self, parent_result, source_args, **kwargs):
        result = PowerReports.ReportDataList(self)
        project = parent_result.getObject()

        allpositions = None
        for s in project.ValidCostSheets:
            if not allpositions:
                allpositions = s.Positions
            else:
                allpositions += s.Positions
        start_month = 0
        end_month = 0
        start_year = 0
        end_year = 0
        if len([x for x in allpositions if x.start_time is None]) != len(allpositions):
            start = min(x.start_time for x in allpositions if x.start_time is not None)
            start_year = start.year
            start_month = start.month
        if len([x for x in allpositions if x.end_time is None]) != len(allpositions):
            end = max(x.end_time for x in allpositions if x.end_time is not None)
            end_year = end.year
            end_month = end.month
        if start_month and start_year and end_month and end_year:
            for year in six.moves.range(start_year, end_year + 1):
                start_month_in_year = 1
                end_month_in_year = 12
                if start_year == year:
                    start_month_in_year = start_month
                if end_year == year:
                    end_month_in_year = end_month
                for month in six.moves.range(
                    start_month_in_year, end_month_in_year + 1
                ):
                    data = PowerReports.ReportData(self)
                    data["monthyear"] = "%s.%s" % (month, year)
                    result += data
        return result
