#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
This module provides the business logic of an open issue.
"""

__all__ = [
    "Issue",
    "IssueChangeLog",
    "IssueRemark",
    "IssuePriority",
    "ActionReference",
    "WithIssueReport",
    "IssueCategory",
    "IssueValue",
]

import datetime
import os
import re

from cdb import CADDOK, auth, sqlapi, ue, util
from cdb.objects import (
    ByID,
    Forward,
    Object,
    Reference_1,
    Reference_N,
    ReferenceMethods_N,
)
from cdb.objects.common import WithStateChangeNotification
from cdb.objects.org import WithSubject
from cdb.platform import gui
from cdb.storage.index import object_updater, updaters

from cs.pcs.issues.tasks_plugin import IssueWithCsTasks
from cs.pcs.projects.common import assert_valid_project_resp
from cs.pcs.projects.common.email import get_email_links
from cs.pcs.projects.common.sharing import WithSharingAndProjectRoles

# Forward declarations
Project = Forward("cs.pcs.projects.Project")
Task = Forward("cs.pcs.projects.tasks.Task")
Issue = Forward("cs.pcs.issues.Issue")
IssueChangeLog = Forward("cs.pcs.issues.IssueChangeLog")
IssueRemark = Forward("cs.pcs.issues.IssueRemark")
fAction = Forward("cs.actions.Action")
fActionReference = Forward(__name__ + ".ActionReference")


class WithFrozen:
    """
    mixin to update cdbpcs_frozen after create/copy operations
    to prevent circular imports, this has to be implemented here
    """

    def set_frozen(self, ctx):
        if hasattr(self, "cdbpcs_frozen"):
            project = getattr(self, "Project", None)
            if project:
                newFrozen = int(project.status == project.FROZEN.status)
                if newFrozen != self.cdbpcs_frozen:
                    self.cdbpcs_frozen = newFrozen

    event_map = {
        (("create", "copy"), "pre"): "set_frozen",
    }


class Issue(
    WithSubject,
    WithStateChangeNotification,
    WithSharingAndProjectRoles,
    WithFrozen,
    IssueWithCsTasks,
):
    """
    This class provides the most business logic of an open issue.
    """

    __maps_to__ = "cdbpcs_issue"
    __classname__ = "cdbpcs_issue"
    ID_PREFIX = "ISS"
    COPY_DEFAULTS_APPLIED = "copy_defaults_applied"
    CREATE_DEFAULTS_APPLIED = "create_defaults_applied"

    _change_log_attrs = [
        "reason",
        "category",
        "priority",
        "subject_id",
        "target_date",
        "effort_plan",
        "material_cost",
        "waiting_for",
        "currency_object_id",
    ]

    Project = Reference_1(Project, Issue.cdb_project_id)
    Task = Reference_1(Task, Issue.cdb_project_id, Issue.task_id)
    ChangeLogs = Reference_N(
        IssueChangeLog,
        IssueChangeLog.cdb_project_id == Issue.cdb_project_id,
        IssueChangeLog.issue_id == Issue.issue_id,
    )

    ActionReferences = Reference_N(
        fActionReference,
        fActionReference.cdb_project_id == Issue.cdb_project_id,
        fActionReference.issue_id == Issue.issue_id,
    )

    IssueActions = ReferenceMethods_N(
        fAction, lambda self: [ref.Action for ref in self.ActionReferences]
    )

    def setDone(self, comment=""):
        sc = self.GetStateChange()
        sc.step(Issue.COMPLETED.status)

    def add_waiting_for_changelog(self, ctx, valdict):
        if self.status == Issue.WAITINGFOR.status:
            valdict["reason"] = self.reason
            valdict["waiting_for"] = self.waiting_for
        elif int(ctx.old._fields["status"]) == Issue.WAITINGFOR.status:
            valdict["reason"] = ""
            valdict["waiting_for"] = ""
        IssueChangeLog.Create(**valdict)

    def newChangeLog(self, ctx):
        if ctx.error != 0:
            return
        valdict = self._key_dict()
        valdict["id"] = util.nextval("cdbpcs_iss_log")
        valdict["changed_by"] = auth.persno
        valdict["changed_at"] = self.cdb_mdate
        if len(self.ChangeLogs) == 0:
            # 1. Eintrag -> Alle Attribute einfuegen
            for attr in self._change_log_attrs:
                valdict[attr] = self[attr]
            IssueChangeLog.Create(**valdict)
        else:
            if ctx.action == "state_change":
                # adds 'reason' and 'waiting_for'
                self.add_waiting_for_changelog(ctx, valdict)
            else:
                # nur die geaenderten Attribute einfuegen
                changed_attrs = ctx.sys_args["changed_attrs"]
                if changed_attrs:
                    for attr in changed_attrs.split(","):
                        valdict[attr] = ctx.dialog[attr]
                IssueChangeLog.Create(**valdict)

    @classmethod
    def getIssueID(cls, counter):
        prefix_number = cls.issue_id.length - len(cls.ID_PREFIX)
        issue_id = f"{cls.ID_PREFIX}{counter:0{prefix_number}d}"
        return issue_id

    def setIssueID(self, ctx):
        self.issue_id = self.getIssueID(util.nextval("cdbpcs_issue"))

    def on_modify_pre(self, ctx):
        # Keep the changed attributes to create the change log entry in the modify post user exit
        changed_attrs = []
        for attr in self._change_log_attrs:
            if hasattr(ctx.dialog, attr) and ctx.dialog[attr] != ctx.object[attr]:
                changed_attrs.append(attr)
        ctx.set("cdb::argument.changed_attrs", ",".join(changed_attrs))

    def get_copy_defaults(self):
        """
        :returns: Default key/value pairs to preset in copy dialog.
        :rtype: dict

        You can overwrite this to control default values for issue copies.

        .. code-block :: python

            from cs.pcs.issues import Issue

            class MyIssue(Issue):
                def get_copy_defaults(self):
                    defaults = super().get_copy_defaults()
                    defaults["es_muy_importante"] = "1"
                    return defaults
        """

        return {
            "issue_id": "",
            "reason": "",
            "completion_date": None,
            "cdbpcs_isss_txt": "",
            "waiting_for": "",
            "mapped_waiting_for_name": "",
        }

    def on_copy_pre_mask(self, ctx):
        defaults = self.get_copy_defaults()
        for attr, val in defaults.items():
            ctx.set(attr, val)
        ctx.keep(self.COPY_DEFAULTS_APPLIED, 1)

    def on_copy_pre(self, ctx):
        pass

    def get_create_defaults(self):
        """
        :returns: Default key/value pairs to preset in create dialog.
        :rtype: dict

        You can overwrite this to control default values for issue creates.

        .. code-block :: python

            from cs.pcs.issues import Issue

            class MyIssue(Issue):
                def get_create_defaults(self):
                    defaults = super().get_create_defaults()
                    defaults["es_muy_importante"] = "1"
                    return defaults
        """

        category = IssueCategory.KeywordQuery(is_default=1)
        priority = IssuePriority.KeywordQuery(is_default=1)
        return {
            "category": category[0].category if category else None,
            "priority": priority[0].priority if priority else None,
        }

    def on_create_pre_mask(self, ctx):
        self.division = auth.get_department()
        defaults = self.get_create_defaults()
        for attr, val in defaults.items():
            ctx.set(attr, val)
        ctx.keep(self.CREATE_DEFAULTS_APPLIED, 1)

    def on_create_pre(self, ctx):
        pass

    def set_defaults(self, ctx):
        def _field_is_preset(x):
            # return True if field is part of ctx.dialog,
            # which means it has a value set beforehand, e.g. by REST API
            # These are the fields we do not want to overwrite by defaults
            value = ctx.dialog[x] if hasattr(ctx.dialog, x) else None
            return bool(value)

        ctx_ue_args = ctx.ue_args.get_attribute_names()
        if ctx.action == "create" and self.CREATE_DEFAULTS_APPLIED not in ctx_ue_args:
            defaults = self.get_create_defaults()
            defaults["division"] = auth.get_department()
        elif ctx.action == "copy" and self.COPY_DEFAULTS_APPLIED not in ctx_ue_args:
            defaults = self.get_copy_defaults()
        else:
            # No need to set defaults
            return

        if ctx.uses_restapi:
            # for creation via REST API only
            # we do not want to overwrite given
            # values by defaults
            new_defaults = {}
            for attr, val in defaults.items():
                if not _field_is_preset(attr):
                    new_defaults[attr] = val
            defaults = new_defaults
        for attr, val in defaults.items():
            ctx.set(attr, val)

    def on_cdb_show_responsible_now(self, ctx):
        return self.openSubject()

    def on_delete_post(self, ctx):
        self.ChangeLogs.Delete()

    def GetDisplayAttributes(self):
        """This method creates and returns a results dictionary, containing the
        necessary information for the html display in the client."""
        results = self.Super(Issue).GetDisplayAttributes()
        results["attrs"].update({"heading": str(self["mapped_category_name"])})
        return results

    # == Email notification ==

    def getNotificationTitle(self, ctx=None):
        """
        :param ctx:
        :return: title of the notification mail
        :rtype: basestring
        """
        return (
            f"{gui.Message.GetMessage('branding_product_name')} - "
            "Offener Punkt bereit / Issue ready"
        )

    def getNotificationTemplateName(self, ctx=None):
        """
        :param ctx:
        :return: template name of the notification mail body
        :rtype: basestring
        """
        return "cdbpcs_issue_ready.html"

    def getNotificationReceiver(self, ctx=None):
        rcvr = {}
        if self.Subject:
            for pers in self.Subject.getPersons():
                if pers.email_notification_task():
                    tolist = rcvr.setdefault("to", [])
                    tolist.append((pers.e_mail, pers.name))
        return [rcvr]

    def setNotificationContext(self, sc, ctx=None):
        win_links, web_links = get_email_links(
            (self, self.issue_name, "CDB_Modify"),
            (self.Project, self.Project.project_name, "cdbpcs_project_overview"),
        )

        sc.issue_link_win, sc.issue_name_win = win_links[0]
        sc.project_link_win, sc.project_name_win = win_links[1]

        if web_links:
            sc.issue_link_web, sc.issue_name_web = web_links[
                0
            ]  # pylint: disable=unsubscriptable-object
            sc.project_link_web, sc.project_name_web = web_links[
                1
            ]  # pylint: disable=unsubscriptable-object

    # == End email notification ==

    # ########################### Utils for copying and resetting checklists ######################

    def Reset(self):
        from cdb.platform import olc

        self.Update(
            status=Issue.NEW.status,
            cdb_status_txt=olc.StateDefinition.ByKeys(
                statusnummer=Issue.NEW.status, objektart=self.cdb_objektart
            ).StateText[""],
        )

    def MakeCopy(self, project, task):
        args = {
            "cdb_project_id": project.cdb_project_id,
            "issue_id": project.makeID("issue_id", self),
        }
        if task:
            args.update({"task_id": task.task_id})

        new_issue = self.Copy(**args)

        # Langtexts kopieren
        new_issue.SetText("cdbpcs_iss_txt", self.GetText("cdbpcs_iss_txt"))
        new_issue.SetText("cdbpcs_isss_txt", self.GetText("cdbpcs_isss_txt"))

        return new_issue

    def GetActivityStreamTopics(self, posting):
        """
        Activity Stream postings should be assigned
        to the project and the object itself.
        """
        return [self, self.Project]

    def handle_waiting_for(self, ctx):
        # Set info fields of the status Waiting For (70) readonly
        # The fields must only be editable if the target status Waiting For (70) is selected.
        if ctx.dialog.zielstatus_int == "70":
            ctx.set_fields_writeable(["waiting_for_name", "waiting_reason"])
            ctx.set_mandatory("waiting_for_name")
            ctx.set_mandatory("waiting_reason")
        else:
            ctx.set_fields_readonly(["waiting_for_name", "waiting_reason"])
            ctx.set_optional("waiting_for_name")
            ctx.set_optional("waiting_reason")

    def setFields(self, ctx):
        ctx.set_fields_readonly(self.getReadOnlyFields(action=ctx.action))

    def getReadOnlyFields(self, action="modify", avoid_check=False):
        return ["cdb_project_id", "project_name"]

    def check_project_role_needed(self, ctx):
        self.Project.check_project_role_needed(ctx)

    def notifyInBatchMode(self):
        """
        Defines when a notification of a status change will be sent.

        :return: True (Default): Notification in both use cases

                 False: Notification only in case of interaction by the user (Default in parent
                 `cdb.objects.common.WithStateChangeNotification#notifyInBatchMode)`
        :rtype: bool
        """
        return True

    def validate_responsibility(self, ctx):
        assert_valid_project_resp(ctx)

    def setRelshipFieldsReadOnly(self, ctx):
        if ctx.relationship_name == "cdbpcs_task2issues":
            ctx.set_fields_readonly(["project_name", "task_name"])
        elif ctx.relationship_name == "cdbpcs_project2issues":
            ctx.set_fields_readonly(["project_name"])

    def prevent_creating_issue(self, ctx):
        task_end_status = Task.endStatus(False)
        project_status = Project.endStatus(full_cls=False)
        if self.Task and self.Task.status in task_end_status:
            raise ue.Exception("open_issue_to_completed_task")
        if self.Project and self.Project.status in project_status:
            raise ue.Exception("open_issue_to_completed_project")

    event_map = {
        (("create", "copy"), "pre"): (
            "validate_responsibility",
            "set_defaults",
            "setIssueID",
        ),
        (("create", "copy", "modify"), "post"): (
            "newChangeLog",
            "check_project_role_needed",
        ),
        (("create"), "pre_mask"): (
            "setRelshipFieldsReadOnly",
            "prevent_creating_issue",
        ),
        (("create", "copy", "modify"), "pre"): ("prevent_creating_issue"),
        (("modify", "info"), "pre_mask"): ("setFields"),
        (("delete", "state_change", "cs_tasks_delegate"), "post"): (
            "check_project_role_needed"
        ),
        ("wf_step", ("pre_mask", "dialogitem_change")): ("handle_waiting_for"),
    }


class IssueChangeLog(Object):
    __maps_to__ = "cdbpcs_iss_log"


class IssueCategory(Object):
    __maps_to__ = "cdbpcs_iss_cat"
    __classname__ = "cdbpcs_iss_cat"

    event_map = {
        (("create", "modify"), "post"): ("reset_is_default"),
    }

    def reset_is_default(self, ctx):
        """
        Resets the default flag for other categories when one category is set as default
        """
        if self.is_default:
            sqlapi.SQLupdate(
                f"{self.__maps_to__} SET is_default=0 WHERE category!='{self.category}'"
            )


class IssuePriority(Object):
    __maps_to__ = "cdbpcs_iss_prio"
    __classname__ = "cdbpcs_iss_prio"

    event_map = {
        (("create", "modify"), "post"): ("reset_is_default"),
    }

    def reset_is_default(self, ctx):
        """
        Resets the default flag for other priorities when one priority is set as default
        """
        if self.is_default:
            sqlapi.SQLupdate(
                f"{self.__maps_to__} SET is_default=0 WHERE priority!='{self.priority}'"
            )


class IssueValue(Object):
    __maps_to__ = "cdbpcs_iss_val"


class ActionReference(Object):
    __maps_to__ = "cdb_action2issue"
    __classname__ = "cdb_action2issue"

    Action = Reference_1(fAction, fActionReference.action_object_id)


class WithIssueReport:
    @classmethod
    def on_cdbpcs_issue_report_now(cls, ctx):
        project = Project.ByKeys(cdb_project_id=ctx.dialog.cdb_project_id)
        task = Task.ByKeys(
            cdb_project_id=ctx.dialog.cdb_project_id, task_id=ctx.dialog.task_id
        )
        report_file = cls.GenerateIssueReport(
            project,
            task,
            ctx.dialog.close_flag,
            ctx.dialog.priority,
            ctx.dialog.fromdate,
            ctx.dialog.to,
        )
        if os.path.isfile(report_file):
            ctx.file(report_file)
        else:
            raise ue.Exception("cdbpcs_issue_report_failed", report_file)

    @classmethod
    def GenerateIssueReport(
        cls,
        project,
        task=None,
        close_flag=None,
        priority=None,
        from_date=None,
        to_date=None,
        layoutFile=None,
    ):
        # Select Issues
        cond = f"cdb_project_id = '{project.cdb_project_id}'"
        if close_flag:
            cond += f" AND close_flag = '{close_flag}'"
        if priority:
            cond += f" AND priority = '{priority}'"
        if task:
            cond += f" AND task_id = '{task.task_id}'"
        if not to_date:
            to_date = datetime.datetime.now()
        cond += f" AND reported_at <= {sqlapi.SQLdbms_date(to_date)}"
        if from_date:
            cond += f" AND reported_at >= {sqlapi.SQLdbms_date(from_date)}"
        issues = sqlapi.RecordSet2(
            "cdbpcs_issue", condition=cond, addtl="order by issue_id"
        )
        # Find layout file and setup output file
        if not layoutFile:
            xml_template = "layout_cdbpcs_issue_report.xml"
            layoutFile = os.path.join(CADDOK.BASE, "reports", xml_template)
            if not os.path.isfile(layoutFile):
                layoutFile = os.path.join(os.path.dirname(__file__), xml_template)

        str_datetime_now = datetime.datetime.now().strftime("%a-%d-%b-%Y-%H-%M-%S")
        resultFile = os.path.join(
            CADDOK.TMPDIR,
            f"issreport-{auth.login}-{str_datetime_now}.xml",
        )
        # generate Report
        from cdb.reportutils import xmlDataSourceCreator, xmlReportCreator

        dataFile = None
        rds = xmlDataSourceCreator.ReportDataSourceCreator(layoutFile, dataFile)
        rds.fillWithRecordset([project])
        rds.fillWithRecordset(issues, {}, "cdbpcs_issue")
        rep = xmlReportCreator.ReportCreator(layoutFile, dataFile, resultFile)
        rep.setDatas(rds.getDatas())
        rep.createReport()
        rep.output()
        return resultFile


class IssueUpdater(object_updater.ObjectUpdater):
    """
    For each issue, also index the following ID shortcuts:

    - <prefix without trailing minus><numeric part without leading zeros>
    - <prefix><numeric part without leading zeros>
    """

    def __init__(self, job_id, cdb_object_id, is_deleted):
        super().__init__(job_id, cdb_object_id, is_deleted)
        self._regexp = re.compile(r"([a-zA-Z]+)(\d+)")

    def _collect_attributes(self):
        super()._collect_attributes()
        issue = ByID(self._cdb_object_id)
        match = self._regexp.search(issue.issue_id)
        if match:
            prefix_part = match.group(1)
            numeric_part = match.group(2)
            self._add_field("identifying", f"{numeric_part}")
            self._add_field("identifying", f"{prefix_part}{numeric_part.lstrip('0')}")

    @classmethod
    def setup(cls):
        factory = updaters.IndexUpdaterFactory()
        factory.add_updater(Issue.__classname__, IssueUpdater)


IssueUpdater.setup()
