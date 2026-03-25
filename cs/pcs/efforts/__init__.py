#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__all__ = ["TimeSheet", "WithEffortReport"]

import datetime
import os
import time
from functools import reduce

from cdb import CADDOK, auth, sqlapi, typeconversion, ue, util
from cdb.objects import Forward, LocalizedField, Object, Reference_1, Reference_N
from cdb.objects.org import Person

APP_MOUNT_PATH = "myefforts"

# Forward declarations
fTimeSheet = Forward("cs.pcs.efforts.TimeSheet")
fActivityType = Forward("cs.pcs.efforts.ActivityType")
Task = Forward("cs.pcs.projects.tasks.Task")
Project = Forward("cs.pcs.projects.Project")
fStopwatch = Forward("cs.pcs.efforts.stopwatch.Stopwatch")
CatalogProjectTaskProposals = Forward(
    "cs.pcs.projects.catalogs.CatalogProjectTaskProposals"
)

BOOKABLE_TASK_RULE = "cdbpcs: TimeSheet: Bookable Tasks (All/All)"
BOOKABLE_PROJECT_RULE = "cdbpcs: TimeSheet: Bookable Projects (All)"

EFFORTS_TASK_CATALOG = "cdbpcs_tasks_for_efforts"

ATTR_WITH_DEFAULT_VALS = [
    "category",
    "description",
    "location",
    "billable",
    "activity_type_object_id",
]


def filter_hook_vals(vals):
    """
    :param vals: values of dialog hook
    :type vals: dictionary

    :returns: all vals entries, which keys started with "cdbpcs_effort.",
        but now without this prefix.
    :rtype: dict
    """
    processed_vals = {}
    for val in vals:
        if "cdbpcs_time_sheet." in val:
            new_val = val.split(".")[1]
            processed_vals.update({new_val: vals[val]})
    return processed_vals


class TimeSheet(Object):
    __maps_to__ = "cdbpcs_time_sheet"
    __classname__ = "cdbpcs_effort"

    Project = Reference_1(Project, fTimeSheet.cdb_project_id)
    Task = Reference_1(Task, fTimeSheet.cdb_project_id, fTimeSheet.task_id)
    ActivityType = Reference_1(fActivityType, fTimeSheet.activity_type_object_id)
    Stopwatches = Reference_N(
        fStopwatch,
        fStopwatch.effort_id == fTimeSheet.effort_id,
        order_by="start_time desc",
    )

    DAY_HOURS = 0
    DEFAULT_GROUP_BY_FIELDS = ["day"]
    HOURS_FIELD = "hours"

    def checkTask(self, ctx):
        if not self.Task:
            raise ue.Exception("pcs_err_task_id", self.task_id, self.cdb_project_id)
        # subtask check? Use the object rules in checkTaskState
        #        # Aufwände dürfen nicht auf Sammelaufgaben und Meilensteinen gebucht werden
        #        if len(self.Task.Subtasks) or self.Task.milestone:
        #            raise ue.Exception("pcs_err_effort3")
        if self.Task.milestone:
            # TODO: to correct "pcs_err_effort3": remove task group check
            raise ue.Exception("pcs_err_effort3")

    def on_create_pre_mask(self, ctx):
        # setting default values based on task and project
        self.setDefaults()

        # setting person id and name to currently logged user id
        person = Person.ByKeys(personalnummer=auth.persno)
        self.person_id = person.personalnummer
        self.person = person.name

    def setDefaults(self):
        # Defaults anhand des letzten Eintrages zur selben Aufgabe setzen
        values = TimeSheet.getValsForDefaultAttr(self.cdb_project_id, self.task_id)
        for attr, val in values.items():
            if not self[attr]:
                self[attr] = val

    @classmethod
    def getValsForDefaultAttr(cls, cdb_project_id, task_id):
        recordSet = sqlapi.RecordSet2(
            sql="SELECT max(effort_id) as max_effort_id from cdbpcs_time_sheet "
            f"where cdb_project_id='{cdb_project_id}'"
            f" and task_id='{task_id}' and cdb_cpersno = '{auth.persno}'"
        )

        last_ts_id = None
        result = {}

        for record in recordSet:
            last_ts_id = record.max_effort_id

        if last_ts_id is not None:
            # cast to integer because if its double/float
            # ByKeys will raise error (int is expected in this case)
            last_ts_id = int(last_ts_id)

            last_ts = TimeSheet.ByKeys(effort_id=last_ts_id)
            for attr in ATTR_WITH_DEFAULT_VALS:
                result[attr] = last_ts[attr]
        return result

    def checkTaskState(self, ctx):
        # Aufwande können nur auf die Aufgaben eingetragen werden,
        # die in bestimmten Objektregeln definiert sind.
        if self.Task and (
            not self.Project.MatchRule(BOOKABLE_PROJECT_RULE)
            or not self.Task.MatchRule(BOOKABLE_TASK_RULE)
        ):
            raise ue.Exception("pcs_err_effort1")

    def checkEffort(self, ctx):
        if self.Task:
            # Aufwände dürfen eingetragen werden, wenn an der Aufgabe keine Aufwände manuell
            # im Aufwandsfeld 'effort_act' erfasst wurden
            if (
                self.Task.effort_act
                and not self.Task.is_group
                and len(self.Task.TimeSheets) == 0
            ):
                raise ue.Exception("pcs_err_effort2", self.Task.task_name)

    def _saveTaskProjectIDs(self, ctx):
        if ctx.object:
            ctx.keep("old_project_id", ctx.object.cdb_project_id)

    def adjustEfforts(self, ctx):
        new_project = self.Project
        from cs.pcs.projects import tasks_efforts

        if new_project:
            tasks_efforts.aggregate_changes(new_project)

        if (
            "old_project_id" in ctx.ue_args.get_attribute_names()
            and ctx.ue_args["old_project_id"] != self.cdb_project_id
        ):
            old_project = Project.ByKeys(cdb_project_id=ctx.ue_args["old_project_id"])
            if old_project:
                tasks_efforts.aggregate_changes(old_project)

    def checkPersonEfforts(self, ctx):
        default_limit_hours = util.PersonalSettings().getValueOrDefaultForUser(
            "user.limit_hours_per_day", "", None, None
        )
        if default_limit_hours and not ctx.uses_webui:
            sheets = TimeSheet.KeywordQuery(
                day=self.day, person_id=self.person_id
            ).hours
            hsum = reduce(lambda x, y: x + y, sheets, 0.0)
            if ctx.action == "modify" and ctx.object.day == ctx.dialog.day:
                try:
                    orival = float(ctx.object.hours)
                except (TypeError, ValueError):
                    orival = 0.0
                hsum -= orival
            if self.hours:
                hsum += self.hours
            if "exceed" not in ctx.dialog.get_attribute_names() and hsum > float(
                default_limit_hours
            ):
                msgbox = ctx.MessageBox(
                    "pcs_efforts_exceed_limit",
                    [hsum, self.day.date(), default_limit_hours],
                    "exceed",
                    ctx.MessageBox.kMsgBoxIconAlert,
                )
                msgbox.addButton(ctx.MessageBoxButton("ok", 1))
                ctx.show_message(msgbox)

    def setTaskProgress(self, ctx):
        if self.Task.effort_act and not self.Task.percent_complet:
            self.Task.percent_complet = 1

    @classmethod
    def get_day_hours(cls):
        """
        This method returns the number of hours available in a day.

        It specifies the number of hours expected to be booked per person and working day.

        The constant `TimeSheet.DAY_HOURS` is 0 by default. This hides the following elements:
            - Progress Bar in the efforts Day Card.
            - Warning icon in the efforts Day Card.
            - The total daily target hours in the efforts Day Card.
            - The total weekly target hours in the efforts footer app.

        To show the above elements or change the target hours values in a customer environment,
        this method must return value greater than zero

        Default value is 0.
        """
        return TimeSheet.DAY_HOURS

    @classmethod
    def get_default_groupby_fields(cls):
        """
        This method returns the default groupby field for the efforts app.
        The constant `TimeSheet.DEFAULT_GROUP_BY_FIELDS` can be changed in customer environment
        for any change in behavior.

        Default group by day.
        """
        return TimeSheet.DEFAULT_GROUP_BY_FIELDS

    @classmethod
    def get_hours_field(cls):
        """
        This method returns the field used for hours calculation in efforts app.
        The constant `TimeSheet.HOURS_FIELD` can be changed in customer environment
        for any change in behavior.

        Default is the 'hours' field.
        """
        return TimeSheet.HOURS_FIELD

    def checkLastEffort(self, ctx):
        efforts = sqlapi.RecordSet2("cdbpcs_time_sheet", f"task_id = '{self.task_id}'")
        if len(efforts) == 0:
            self.Task.effort_act = ""

    def dialog_item_changed(self, ctx):
        self.set_read_only(ctx)
        self.setDefaults()
        self.validate_dialog_selection(ctx)

    def set_read_only(self, ctx):
        def uses_webui():
            # when called from dialog_item_change hook, ctx doesn't have uses_webui attr
            return hasattr(ctx, "uses_webui") and ctx.uses_webui

        attribute_names = ctx.dialog.get_attribute_names()
        if (
            not uses_webui()
            and "cdb_project_id" in attribute_names
            and "project_name" in attribute_names
        ):
            if ctx.dialog.cdb_project_id and ctx.dialog.project_name:
                ctx.set_writeable("task_name")
            else:
                ctx.set_readonly("task_name")

    def validate_dialog_selection(self, ctx):
        if ctx.changed_item == "cdb_project_id":
            if self.Project and not self.Project.MatchRule(BOOKABLE_PROJECT_RULE):
                raise ue.Exception("pcs_efforts_invalid_proj_selection")

        if ctx.changed_item == "task_id":
            if self.Task and not self.Task.MatchRule(BOOKABLE_TASK_RULE):
                raise ue.Exception("pcs_efforts_invalid_task_selection")

    def prioritize_selected_task(self, ctx):
        """
        If the effort entry is created, copied or modified, it's task
        should be re-prioritized to get recently used tasks by any user.
        """
        if ctx.interactive or ctx.uses_webui:
            # only update when the user performed the operation
            kwargs = {
                "catalog_name": EFFORTS_TASK_CATALOG,
                "catalog_personalnummer": auth.persno,
                "cdb_project_id": self.cdb_project_id,
                "task_id": self.task_id,
                "ce_baseline_id": "",
            }
            catalog_entry = CatalogProjectTaskProposals.KeywordQuery(**kwargs)
            try:
                # we update one entry even if multiple entries exist for a task
                catalog_entry[0].Update(catalog_sel_time=datetime.datetime.now())
            except IndexError:  # no entry exists yet
                kwargs.update({"catalog_sel_time": datetime.datetime.now()})
                CatalogProjectTaskProposals.Create(**kwargs)

    def setRelshipFieldsReadOnly(self, ctx):
        if ctx.relationship_name == "cdbpcs_project2effort":
            ctx.set_fields_readonly(["project_name"])
        elif ctx.relationship_name == "cdbpcs_task2efforts":
            ctx.set_fields_readonly(["project_name", "task_name"])

    event_map = {
        (("create", "copy"), "pre"): ("checkTask", "checkTaskState", "checkEffort"),
        (("modify"), "pre"): ("checkTask", "checkTaskState", "_saveTaskProjectIDs"),
        (("delete"), "pre"): ("checkTaskState"),
        (("create", "copy", "modify"), "post"): (
            "adjustEfforts",
            "setTaskProgress",
            "prioritize_selected_task",
        ),
        (("create", "copy", "modify"), "post_mask"): ("checkPersonEfforts"),
        (("delete"), "post"): ("checkLastEffort", "adjustEfforts", "setTaskProgress"),
        (("create"), "pre_mask"): ("setRelshipFieldsReadOnly"),
        (("create", "copy", "modify"), "pre_mask"): ("set_read_only"),
        (("create", "copy", "modify"), "dialogitem_change"): ("dialog_item_changed"),
    }


class WithEffortReport:
    @classmethod
    def on_cdbpcs_effort_report_now(cls, ctx):
        project = Project.ByKeys(cdb_project_id=ctx.dialog.cdb_project_id)
        task = Task.ByKeys(
            cdb_project_id=ctx.dialog.cdb_project_id, task_id=ctx.dialog.task_id
        )
        report_file = cls.GenerateEffortReport(
            project,
            task,
            ctx.dialog.person_id,
            ctx.dialog.billable,
            ctx.dialog.fromdate,
            ctx.dialog.to,
            ctx.dialog.ordercode,
        )
        if os.path.isfile(report_file):
            ctx.file(report_file)
        else:
            raise ue.Exception("cdbpcs_effort_report_failed", report_file)

    @classmethod
    def on_cdbpcs_effort_report_pre_mask(cls, ctx):
        # fromdate auf monatsanfang setzen
        day = int(time.strftime("%d", time.localtime(time.time())))
        if day != 1:
            fromdate = "01." + time.strftime("%m.%Y", time.localtime(time.time()))
            ctx.set("fromdate", fromdate)

    @classmethod
    def GenerateEffortReport(
        cls,
        project,
        task=None,
        persno=None,
        billable=None,
        from_date=None,
        to_date=None,
        order_by=None,
        layoutFile=None,
    ):
        # Select efforts
        cond = f"cdb_project_id = '{project.cdb_project_id}'"
        if billable:
            cond += f" AND billable = '{billable}'"
        if persno:
            cond += f" AND person_id = '{persno}'"
        if not to_date:
            to_date = typeconversion.to_legacy_date_format(datetime.date.today(), False)
        cond += f" AND day <= {sqlapi.SQLdbms_date(to_date)}"
        if from_date:
            cond += f" AND day >= {sqlapi.SQLdbms_date(from_date)}"
        if task:
            cond += f" AND (task_id = '{task.task_id}'"
            for sub_task in task.AllSubTasks:
                cond += f" OR task_id = '{sub_task.task_id}'"
            cond += ")"
        if not order_by:
            order_by = "effort_id"
        efforts = sqlapi.RecordSet2(
            "cdbpcs_time_sheet", condition=cond, addtl=f"order by {order_by}"
        )
        # Find layout file and setup output file
        if not layoutFile:
            xml_template = "layout_cdbpcs_effort_report.xml"
            layoutFile = os.path.join(CADDOK.BASE, "reports", xml_template)
            if not os.path.isfile(layoutFile):
                layoutFile = os.path.join(os.path.dirname(__file__), xml_template)
        str_datetime_now = datetime.datetime.now().strftime("%a-%d-%b-%Y-%H-%M-%S")
        resultFile = os.path.join(
            CADDOK.TMPDIR,
            f"effreport-{auth.login}-{str_datetime_now}.xml",
        )
        # Generate Report
        from cdb.reportutils import xmlDataSourceCreator, xmlReportCreator

        dataFile = None
        rds = xmlDataSourceCreator.ReportDataSourceCreator(layoutFile, dataFile)
        rds.fillWithRecordset([project])
        rds.fillWithRecordset(efforts, {}, "cdbpcs_time_sheet_v")
        rep = xmlReportCreator.ReportCreator(layoutFile, dataFile, resultFile)
        rep.setDatas(rds.getDatas())
        rep.createReport()
        rep.output()
        return resultFile


class ActivityType(Object):
    __maps_to__ = "cdbpcs_effort_activity_type"
    __classname__ = "cdbpcs_effort_activity_type"

    Name = LocalizedField("name")
