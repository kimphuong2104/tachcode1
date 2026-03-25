#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import logging

from cdb import sqlapi
from cdb.objects import ByID
from cs.platform.web.root.main import _get_dummy_request
from cs.tools import powerreports as PowerReports

from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task
from cs.pcs.timeschedule.new_time_chart.helper import TimeScheduleHelper
from cs.pcs.timeschedule.web.models import DataModel


def index_multilang_fields(objects_class, field_name):
    field = getattr(objects_class, field_name, None)
    if not field:
        logging.error("field does not exist: %s %s", objects_class, field_name)
        return None
    if not hasattr(field, "getLanguageFields"):
        logging.error("is not a multilang field: %s %s", objects_class, field_name)
        return None
    indexed_fields = {
        key: field.name for key, field in field.getLanguageFields().items()
    }
    return indexed_fields


class ExportGantt(PowerReports.CustomDataProvider):
    CARD = PowerReports.CARD_N
    CALL_CARD = PowerReports.CARD_1

    prj_status_lang_fields = index_multilang_fields(Project, "joined_status_name")
    task_status_lang_fields = index_multilang_fields(Task, "joined_status_name")
    task_responsible_lang_fields = index_multilang_fields(Task, "mapped_subject_name")

    def getStatusText(self, obj, lang=""):
        if hasattr(self, "mapped_project_manager"):  # Project
            return obj[self.prj_status_lang_fields.get(lang, "joined_status_name")]
        else:
            return obj[self.task_status_lang_fields.get(lang, "joined_status_name")]

    def getResponsible(self, obj, lang=""):
        if hasattr(obj, "mapped_project_manager"):  # Project
            return obj["mapped_project_manager"]
        else:
            return obj[
                self.task_responsible_lang_fields.get(lang, "mapped_subject_name")
            ]

    # pylint: disable=too-many-locals,too-many-statements
    def getData(self, parent_result, source_args, **kwargs):
        lang = source_args.get("cdbxml_report_lang")

        def _flatten_schedule_content(obj, lvl, timeobjects):
            key = list(obj)[0]
            timeobjects.append((lvl, key))
            children = obj[key]["children"]
            if children:
                for child in children:
                    _flatten_schedule_content(child, lvl + 1, timeobjects)
            return timeobjects

        def flatten_schedule_contents(to_list):
            timeobjects = []
            for obj in to_list:
                timeobjects = _flatten_schedule_content(obj, 0, timeobjects)
            return timeobjects

        def get_expanded_ids(time_schedule_id):
            dm = DataModel(time_schedule_id)
            # indices of collapsed rows from zero.
            collapsed = dm.get_user_settings(
                time_schedule_id,
            ).get("collapsedRows", {})
            request = _get_dummy_request()
            data = dm.get_data(request)
            # invert and convert to ids as the following expects expanded_ids
            expanded_ids = []
            rows = data["rows"]
            for row in rows:
                row_id = row["id"]
                if row_id not in collapsed:
                    # these are occurrence ids ("uuid@pinned")
                    # but we're using the legacy timeschedule helper
                    # which uses simple uuids only
                    expanded_ids.append(row_id.split("@")[0])
            return expanded_ids

        time_schedule_id = parent_result.getObject().cdb_object_id
        expanded_ids = get_expanded_ids(time_schedule_id)
        to_list = TimeScheduleHelper.get_changed_data(
            time_schedule_id=time_schedule_id, expanded_ids=expanded_ids
        )["scheduleContents"]
        object_list = flatten_schedule_contents(to_list)
        timeobjects = []  # p.TimeScheduleContents
        for object_id in object_list:
            timeobjects.append((object_id[0], ByID(object_id[1])))

        result = PowerReports.ReportDataList(self)
        for singleobject in timeobjects:
            dataRD = PowerReports.ReportData(self)
            socontent = singleobject[1]  # ByID(soid)

            level = singleobject[0]
            prefix = ""  # buildpre(level, spacestring)

            start = socontent.getStartTimeFcast()
            end = socontent.getEndTimeFcast()
            if not start and end:
                start = end
            elif not end and start:
                end = start

            dataRD["cdbxml_level"] = level
            dataRD["start-time"] = start
            dataRD["end-time"] = end
            dataRD["titel"] = PowerReports.MakeReportURL(
                socontent, text_to_display=prefix + socontent.getName()
            )
            dataRD["psp-code"] = socontent.get_psp_code()

            soProject = Project.ByKeys(
                cdb_project_id=socontent.getProjectID(),
                ce_baseline_id=socontent.getBaselineID(),
            )

            dataRD["project_hyperlink"] = PowerReports.MakeReportURL(
                soProject, text_to_display="cdb_project_id"
            )
            if socontent.getAttributeValue(
                "cdb_objektart"
            ) == "cdbpcs_task" and socontent.getAttributeValue("milestone"):
                dataRD["art"] = "cdbpcs_milestone"
            else:
                dataRD["art"] = socontent.getAttributeValue("cdb_objektart")

            dataRD["time-status"] = socontent.getAttributeValue("status_time_fcast")

            dataRD["status_number"] = socontent.status
            dataRD["status_txt"] = self.getStatusText(socontent, lang)
            dataRD["responsible"] = self.getResponsible(socontent, lang)

            if isinstance(socontent.getCompletion(), (float, int)):
                dataRD["percent_complete"] = socontent.getCompletion() / 100.0
            # The traffic light color which shows the status
            light_string = socontent.getAttributeValue("rating")
            light = ""
            if light_string == "rot":
                light = 3
            elif light_string == "gelb":
                light = 2
            elif light_string == "gruen":
                light = 1
            dataRD["man_light"] = light
            # get the pre- and successorrelations
            if len(socontent.getPredecessorRelations()) != 0:
                violation = False
                for each in socontent.getPredecessorRelations():
                    if each.violation:
                        violation = True
                    if violation:
                        dataRD["parents-ok"] = 2
                    else:
                        dataRD["parents-ok"] = 0
            if len(socontent.getSuccessorRelations()) != 0:
                violation = False
                for each in socontent.getSuccessorRelations():
                    if each.violation:
                        violation = True
                if violation:
                    dataRD["children-ok"] = 2
                else:
                    dataRD["children-ok"] = 0
            result += dataRD
        return result

    def getSchema(self):
        t = PowerReports.XSDType(self.CARD, "cdbpcs_time_schedule")
        t.add_attr("art", sqlapi.SQL_CHAR)
        t.add_attr("titel", sqlapi.SQL_CHAR)
        t.add_attr("psp-code", sqlapi.SQL_CHAR)
        t.add_attr("start-time", sqlapi.SQL_DATE)
        t.add_attr("end-time", sqlapi.SQL_DATE)
        t.add_attr("time-status", sqlapi.SQL_INTEGER)
        t.add_attr("parents-ok", sqlapi.SQL_INTEGER)
        t.add_attr("children-ok", sqlapi.SQL_INTEGER)
        t.add_attr("project_hyperlink", sqlapi.SQL_CHAR)
        t.add_attr("status_txt", sqlapi.SQL_CHAR)
        t.add_attr("percent_complete", sqlapi.SQL_FLOAT)
        t.add_attr("man_light", sqlapi.SQL_INTEGER)
        t.add_attr("cdbxml_level", sqlapi.SQL_INTEGER)
        t.add_attr("status_number", sqlapi.SQL_INTEGER)
        t.add_attr("responsible", sqlapi.SQL_CHAR)
        return t

    def getArgumentDefinitions(self):
        return {
            "start": sqlapi.SQL_DATE,
            "end": sqlapi.SQL_DATE,
            "range_code": sqlapi.SQL_CHAR,
        }
