#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

"""
Custom data providers

Import will fail if optional dependency cs.powerreports is not installed
"""
from cdb import sqlapi
from cdb import util
from cs.tools import powerreports as PowerReports
from cs.workflow.processes import Process
from cs.workflow.protocols import Protocol
from cs.workflow.protocols import MSGAPPROVED

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class WorkflowReport(PowerReports.CustomDataProvider):
    # Cardinality of the result, here a list of n entries
    CARD = PowerReports.CARD_N
    # Cardinality of the input, here a single Process Obj
    CALL_CARD = PowerReports.CARD_1

    def getProtocolDescriptionAndRemark(self, protocol_desc):
            description = protocol_desc.strip()
            remark = ""
            modifyLabel = util.get_label(
                "cdbwf_component_modify"
                ).split(":")[0]
            addLabel = util.get_label(
                "cdbwf_component_add"
                ).split(":")[0]
            deleteLabel = util.get_label(
                "cdbwf_component_delete"
                ).split(":")[0]
            copyLabel = util.get_label(
                "cdbwf_component_copy"
                ).split(":")[0]
            labels = [modifyLabel, addLabel, deleteLabel, copyLabel]

            aggregationLabel = util.get_label("cdbwf_aggregate_protocol").format("", "", "").split("]")[0].strip()
            for label in labels:
                if label in protocol_desc:
                    if aggregationLabel not in protocol_desc:
                        # If the protocol description is add/mod/delete/copy entry,
                        # split it into description containing only the
                        # action type, like "created"
                        # and a remark containing the changes
                        description = label
                        remark = protocol_desc.replace(description + ": ", "")
                    else:
                        description = protocol_desc.split(":")[0]
                        remark = protocol_desc.replace(description + ": ", "")
                    # Exit loop after correct label was found
                    break
            return description, remark

    def getData(self, parent_result, source_args, **kwargs):
        # return a list of PowerReportObjs
        result = PowerReports.ReportDataList(self)
        p = parent_result.getObject()
        allTasks = p.AllTasks
        for protocol in p.Protocols:
            res = PowerReports.ReportData(self, protocol)
            res["protocol_description"], res["protocol_remark"] = (
                self.getProtocolDescriptionAndRemark(protocol["description"])
            )
            res["protocol_timestamp"] = protocol["timestamp"]
            res["protocol_responsible"] = protocol["mapped_pers_name"]
            for task in allTasks:
                if task["task_id"] == protocol["task_id"]:
                    res["task_deadline"] = task["deadline"]
                    res["task_title"] = task["title"]
                    res["task_responsible"] = task["mapped_subject_name"]
                    taskConstraints = []
                    for constraint in task.Constraints:
                        constrain_desc = constraint["rule_name"]
                        taskConstraints.append(constrain_desc)
                    res["task_constraints"] = "\n".join(taskConstraints)
                else:
                    res["task_deadline"] = None
                    res["task_title"] = ""
                    res["task_responsible"] = ""
                    res["task_constraints"] = ""
            result += res

        return result

    def getSchema(self):
        # get Process data schema
        t = PowerReports.XSDType(self.CARD, Process)
        t.add_attr("task_deadline", sqlapi.SQL_CHAR)
        t.add_attr("task_responsible", sqlapi.SQL_CHAR)
        t.add_attr("task_title", sqlapi.SQL_CHAR)
        t.add_attr("protocol_remark", sqlapi.SQL_CHAR)
        t.add_attr("task_contraints", sqlapi.SQL_CHAR)
        t.add_attr("protocol_timestamp", sqlapi.SQL_CHAR)
        t.add_attr("protocol_description", sqlapi.SQL_CHAR)
        t.add_attr("protocol_responsible", sqlapi.SQL_CHAR)
        return t

    def getClass(self):
        return Process


class WorkflowTemplate(PowerReports.CustomDataProvider):
    # Cardinality of the result, here a single Process Obj
    CARD = PowerReports.CARD_1
    # Cardinality of the input, here a single Process Obj
    CALL_CARD = PowerReports.CARD_1

    def getTemplateIdAndCopyTimeStamp(self, process):
        templateLabel = util.get_label(
            "cdbwf_process_from_template"
            ).format("")
        template_id = ""
        protocol_timestamp = ""
        if process.Protocols:
            for protocol in process.Protocols:
                # Find out, if the workflow comes from a template
                if templateLabel in protocol["description"]:
                    # get Id of template and the timestamp of the
                    # moment the process was copied
                    # from the template
                    template_id = protocol["description"].replace(
                        templateLabel, ""
                    )
                    protocol_timestamp = protocol["timestamp"]
                    return template_id, protocol_timestamp
        # if process either is not generated from a template or
        # has no protocol entries, return the default values
        return template_id, protocol_timestamp

    def getTemplateReleaseDate(self, template_id, protocol_timestamp):
        template_release_date = ""
        # get most recent protocol entries of the template
        # that were protocolled before the process was copied
        template_Releases = Protocol.Query(
            (Protocol.cdb_process_id == template_id) &
            (Protocol.msgtype == MSGAPPROVED) &
            (Protocol.timestamp <= protocol_timestamp),
            order_by="cdbprot_sortable_id DESC"
        )
        if template_Releases:
            template_release_date = template_Releases[0]["timestamp"]

        # for older templates, there may be no protocol entry
        # for the status change to "Approved";
        # in that case leave the release date empty
        # therefore no else-branch
        return template_release_date

    def getData(self, parent_result, source_args, **kwargs):
        p = parent_result.getObject()
        template_id = ""

        template_id, protocol_timestamp = self.getTemplateIdAndCopyTimeStamp(p)

        if template_id:
            template_release_date = self.getTemplateReleaseDate(template_id, protocol_timestamp)
            templateProcess = Process.KeywordQuery(
                cdb_process_id=template_id
                )[0]
            result = PowerReports.ReportData(self, templateProcess)
            result["template_release_date"] = template_release_date
            result["template_hyperlink"] = PowerReports.MakeReportURL(
                templateProcess,
                "CDB_ShowObject",
                template_id
                )
            return result
        else:
            # if no template was found, set the default values
            result = PowerReports.ReportData(self)
            result["template_release_date"] = ""
            result["template_hyperlink"] = ""
            return result

    def getSchema(self):
        # get Process data schema
        t = PowerReports.XSDType(self.CARD, Process)
        t.add_attr("template_release_date", sqlapi.SQL_CHAR)
        t.add_attr("template_hyperlink", sqlapi.SQL_CHAR)
        return t

    def getClass(self):
        return Process
