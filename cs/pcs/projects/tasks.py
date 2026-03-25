#!/usr/bin/env powerscript
# -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=too-many-lines,protected-access

"""
This module provides the business logic of a project task.
"""

import datetime
import functools
import logging
from collections import defaultdict

from cdb import (
    auth,
    cdbuuid,
    cmsg,
    ddl,
    i18n,
    misc,
    sig,
    sqlapi,
    transactions,
    ue,
    util,
)
from cdb.classbody import classbody
from cdb.constants import (
    kOperationCopy,
    kOperationDelete,
    kOperationModify,
    kOperationNew,
)
from cdb.objects import (
    Forward,
    Object,
    Reference_1,
    Reference_Methods,
    Reference_N,
    ReferenceMapping_N,
    unique,
)
from cdb.objects.common import WithStateChangeNotification
from cdb.objects.operations import operation, system_args
from cdb.objects.org import WithSubject
from cdb.platform import gui, mom, olc
from cdb.platform.mom import OperationContext
from cdb.typeconversion import (
    from_legacy_date_format,
    to_legacy_date_format_auto,
    to_python_rep,
    to_user_repr_date_format,
)
from cs.actions import Action
from cs.calendar import workday
from cs.metrics.qcclasses import WithQualityCharacteristic
from cs.platform.web import get_root_url
from cs.platform.web.rest import support
from cs.tools.powerreports import WithPowerReports
from cs.baselining import Baseline

from cs.pcs.efforts import WithEffortReport
from cs.pcs.issues import WithFrozen, WithIssueReport
from cs.pcs.projects import Project, Role
from cs.pcs.projects import calendar as Calendar
from cs.pcs.projects import utils
from cs.pcs.projects.auto_update_time import AutoUpdateTime
from cs.pcs.projects.calendar import getNextEndDate, getNextStartDate
from cs.pcs.projects.common import assert_valid_project_resp, format_in_condition
from cs.pcs.projects.common.email import get_email_links
from cs.pcs.projects.common.sharing import WithSharingAndProjectRoles
from cs.pcs.projects.helpers import ensure_date
from cs.pcs.projects.tasks_plugin import TaskWithCsTasks

__all__ = ["Task", "TaskRelation", "TaskRelationType", "TaskCategory"]

# Forward declarations
fProject = Forward("cs.pcs.projects.Project")
fTask = Forward("cs.pcs.projects.tasks.Task")
fTaskRelation = Forward("cs.pcs.projects.tasks.TaskRelation")
fTaskRelationType = Forward("cs.pcs.projects.tasks.TaskRelationType")
Issue = Forward("cs.pcs.issues.Issue")
TimeSheet = Forward("cs.pcs.efforts.TimeSheet")
Checklist = Forward("cs.pcs.checklists.Checklist")
fOrganization = Forward("cdb.objects.org.Organization")
fPerson = Forward("cdb.objects.org.Person")

kTaskDependencyEA = "EA"  # FS / finish-to-start / Normalfolge
kTaskDependencyAA = "AA"  # SS / start-to-start / Anfangsfolge
kTaskDependencyAE = "AE"  # SF / start-to-finish / Sprungfolge
kTaskDependencyEE = "EE"  # FF / finish-to-finish / Endfolge

ALLOWED_TASK_GROUP_DEPENDECIES = [kTaskDependencyEA, kTaskDependencyAA]

DAYTIME_MORNING = 0
DAYTIME_EVENING = 1
# only for windows client
DAYTIME_NOT_APPLICABLE = ""

BASE_ATTRIBUTES = [
    "start_time_act",
    "start_time_fcast",
    "start_time_plan",
    "end_time_act",
    "end_time_fcast",
    "end_time_plan",
    "days",
    "days_fcast",
    "early_finish",
    "early_start",
    "late_finish",
    "late_start",
    "free_float",
    "total_float",
    "status",
    "effort_act",
    "effort_fcast",
    "effort_fcast_a",
    "effort_fcast_d",
    "effort_plan",
    "status_effort_fcast",
    "status_time_fcast",
    "work_uncovered",
    "percent_complet",
]


# pylint: disable=too-many-instance-attributes
class Task(
    WithSubject,
    WithEffortReport,
    WithIssueReport,
    WithPowerReports,
    WithStateChangeNotification,
    WithQualityCharacteristic,
    Calendar.WithCalendarIndex,
    WithSharingAndProjectRoles,
    WithFrozen,
    TaskWithCsTasks,
):
    """
    This class provides the most business logic of a project task.
    """

    __maps_to__ = "cdbpcs_task"
    __classname__ = "cdbpcs_task"
    __wf_step_reject_msg__ = "pcstask_wfstep_rej"

    position_initial = 10
    position_increment = 10

    """
    The folowing fields are considered to be readOnly for all tasks.
    """
    class_specific_read_only_fields = ["effort_plan", "is_group"]

    def _allParentTasks(self):
        result = []
        if self.ParentTask:
            result.append(self.ParentTask)
            result += self.ParentTask._allParentTasks()
        return result

    def _allSubtasks(self, by_order=True):
        result = []
        for task in self.OrderedSubTasks:
            result.append(task)
            result += task._allSubtasks(by_order=by_order)
        return result

    def _allSubtasks_optimized(self):
        from cs.pcs.projects.project_structure.views import get_task_structure

        return get_task_structure(self.cdb_object_id, self.ce_baseline_id)

    def _allIssues(self):
        result = self.Issues
        for task in self.OrderedSubTasks:
            result += task._allIssues()
        return result

    Project = Reference_1(fProject, fTask.cdb_project_id, fTask.ce_baseline_id)
    OrderedSubTasks = Reference_N(
        fTask,
        fTask.cdb_project_id == fTask.cdb_project_id,
        fTask.parent_task == fTask.task_id,
        fTask.ce_baseline_id == fTask.ce_baseline_id,
        order_by="position",
    )
    AllSubTasks = Reference_Methods(fTask, lambda self: self._allSubtasks())
    AllSubTasksOptimized = Reference_Methods(
        fTask, lambda self: self._allSubtasks_optimized()
    )
    ParentTask = Reference_1(
        fTask, fTask.cdb_project_id, fTask.parent_task, fTask.ce_baseline_id
    )
    AllParentTasks = Reference_Methods(fTask, lambda self: self._allParentTasks())
    Issues = Reference_N(
        Issue,
        Issue.cdb_project_id == fTask.cdb_project_id,
        Issue.task_id == fTask.task_id,
    )
    AllIssues = Reference_Methods(Issue, lambda self: self._allIssues())
    Checklists = Reference_N(
        Checklist,
        Checklist.cdb_project_id == fTask.cdb_project_id,
        Checklist.task_id == fTask.task_id,
    )
    TimeSheets = Reference_N(
        TimeSheet,
        TimeSheet.cdb_project_id == fTask.cdb_project_id,
        TimeSheet.task_id == fTask.task_id,
    )
    PredecessorTaskRelations = Reference_N(
        fTaskRelation,
        fTaskRelation.cdb_project_id == fTask.cdb_project_id,
        fTaskRelation.task_id == fTask.task_id,
    )
    SuccessorTaskRelations = Reference_N(
        fTaskRelation,
        fTaskRelation.cdb_project_id2 == fTask.cdb_project_id,
        fTaskRelation.task_id2 == fTask.task_id,
    )
    PredecessorTaskRelationsByType = ReferenceMapping_N(
        fTaskRelation,
        fTaskRelation.cdb_project_id == fTask.cdb_project_id,
        fTaskRelation.task_id == fTask.task_id,
        indexed_by=fTaskRelation.rel_type,
    )
    SuccessorTaskRelationsByType = ReferenceMapping_N(
        fTaskRelation,
        fTaskRelation.cdb_project_id2 == fTask.cdb_project_id,
        fTaskRelation.task_id2 == fTask.task_id,
        indexed_by=fTaskRelation.rel_type,
    )

    def generate_project_structure_URL(self, request=None, rest_key=None):
        """
        Returns a URL which can be used to navigate to a task in project structure.

        In case of external programs, the domain name is fetched using cs.platform.web.get_root_url.
        The domain name is set using the environment variable :envvar:`CADDOK_WWWSERVICE_URL`

        :return: URL to show a task in the project structure
        :rtype: string
        """
        url_pattern = "{}/info/project/{}?active_tab_id=cs-pcs-projects-web-StructureView&selected={}"
        project_rest_key = f"{self.cdb_project_id}@"
        if request is not None:
            url = url_pattern.format(
                request.application_url, project_rest_key, rest_key
            )
            return url
        domain = get_root_url()
        rest_key = support.rest_key(self)
        url = url_pattern.format(domain, project_rest_key, rest_key)
        return url

    def _allSupertasks(self):
        """
        Method to get all top level tasks

        :return: returns a list of task objects (1, n, none)
        """
        result = [self]
        if self.Supertask:
            result += self.Supertask._allSupertasks()
        return result

    AllSuperTasks = Reference_Methods(fTask, lambda self: self._allSupertasks())
    Supertask = ParentTask
    Subtasks = Reference_N(
        fTask,
        fTask.cdb_project_id == fTask.cdb_project_id,
        fTask.parent_task == fTask.task_id,
        fTask.ce_baseline_id == fTask.ce_baseline_id,
    )

    def _allSupertasksPredRelations(self):
        """
        Method to get all predecessor taskrelations on self and top level tasks

        :return: returns a list of taskrelation objects (1, n, none)
        """
        result = []
        for t in self.AllSuperTasks:
            result += t.PredecessorTaskRelations
        return result

    AllPredecessorTaskRelations = Reference_Methods(
        fTaskRelation, lambda self: self._allSupertasksPredRelations()
    )

    def _allSupertasksSuccRelations(self):
        """
        Method to get all successor taskrelations on self and top level tasks

        :return: returns a list of taskrelation objects (1, n, none)
        """
        result = []
        for t in self.AllSuperTasks:
            result += t.SuccessorTaskRelations
        return result

    AllSuccessorTaskRelations = Reference_Methods(
        fTaskRelation, lambda self: self._allSupertasksSuccRelations()
    )

    # deprecated, will be removed in a future release
    def getCompleteStructure(self):
        relationships = [self.AllSubTasks, self.Issues, self.Checklists]
        for subtask in self.AllSubTasks:
            relationships.append(subtask.Issues)
            relationships.append(subtask.Checklists)
        return relationships

    # Toleranzwert fuer Berechnungen
    Tolerance = 0.01

    def setDone(self, comment=""):
        sc = self.GetStateChange()
        if self.status == 20:
            sc.step(50)
        if self.status == 50:
            sc.step(200)

    def Reset(self):
        self.Update(
            status=Task.NEW.status,
            cdb_status_txt=olc.StateDefinition.ByKeys(
                statusnummer=Task.NEW.status, objektart=self.cdb_objektart
            ).StateText[""],
            start_time_act="",
            end_time_act="",
            days_act=0,
            effort_act=0,
            percent_complet=0,
            effort_fcast_a=0,
        )

    @classmethod
    def get_projects_by_task_object_ids(cls, object_ids, ce_baseline_id=""):
        p_ids = cls.KeywordQuery(cdb_object_id=object_ids).cdb_project_id
        if p_ids:
            return Project.KeywordQuery(
                cdb_project_id=p_ids, ce_baseline_id=ce_baseline_id
            )
        return []

    @classmethod
    def makeTaskID(cls):
        return f"T{(util.nextval('cdbpcs_task')):09d}"

    def setTaskID(self, ctx):
        tasks = Task.Query(f"task_id = '{self.task_id}'")
        if not self.task_id or self.task_id in ["#", ""] or len(tasks):
            self.task_id = self.makeTaskID()

    def makePosition(self, ctx=None):
        """
        Returns following position of a task.
        If the maximum position of all tasks at the same level is 0, the initial value will be used
        :return: int
        """
        position = self.position_initial
        mymax = sqlapi.RecordSet2(
            "cdbpcs_task",
            (Task.cdb_project_id == self.cdb_project_id)
            & (Task.parent_task == self.parent_task)
            & (Task.ce_baseline_id == self.ce_baseline_id),
            columns=["MAX(position) p"],
        )
        if mymax and mymax[0].p:
            position = int(mymax[0].p) + 10
        return position

    def setPosition(self, ctx=None):
        """
        If task id exists and position does not exists, sets the position of a task using makePosition
        """
        change_control = Task.MakeChangeControlAttributes()
        if self.task_id and (
            self.position is None or (self.position == 0 and ctx is None)
        ):
            self.Update(
                position=self.makePosition(),
                cdb_mdate=change_control["cdb_mdate"],
                cdb_mpersno=change_control["cdb_mpersno"],
            )

    def on_cdbpcs_reinit_position_now(self, ctx):
        """
        Event handler for initializing positions of tasks
        :param ctx:
        :return:
        """
        self.reinitPosition()

    def raiseOnMSPProject(self):
        if self.Project and self.Project.msp_active:
            raise ue.Exception("pcs_no_op_for_msp_project")

    def on_activate_automatic_now(self, ctx):
        """
        Event handler for activating automatic flag for tasks
        :param ctx:
        :return:
        """
        self.raiseOnMSPProject()  # do not perform op in case of MSP proj
        if self.Project and not self.Project.CheckAccess("save"):
            raise ue.Exception("cdbpcs_no_project_right")
        cca = self.MakeChangeControlAttributes()
        if not self.automatic:
            self.Update(
                automatic=1, cdb_mdate=cca["cdb_mdate"], cdb_mpersno=cca["cdb_mpersno"]
            )
        if self._lastObjectOfMultiSelect(ctx=ctx):
            ids = set()
            for obj in ctx.objects:
                ids.add(obj.cdb_project_id)
            for p in Project.KeywordQuery(cdb_project_id=ids, ce_baseline_id=""):
                p.recalculate()

    def _lastObjectOfMultiSelect(self, ctx):
        object_count = 0
        if "object_count" in ctx.ue_args.get_attribute_names():
            object_count = int(ctx.ue_args["object_count"])
        object_count += 1
        ctx.keep("object_count", object_count)
        return object_count == len(ctx.objects)

    def on_deactivate_automatic_now(self, ctx):
        """
        Event handler for deactivating automatic flag for tasks
        :param ctx:
        :return:
        """
        self.raiseOnMSPProject()  # do not perform op in case of MSP proj
        if self.Project and not self.Project.CheckAccess("save"):
            raise ue.Exception("cdbpcs_no_project_right")
        cca = self.MakeChangeControlAttributes()
        if self.automatic:
            self.Update(
                automatic=0,
                auto_update_time=0,
                cdb_mdate=cca["cdb_mdate"],
                cdb_mpersno=cca["cdb_mpersno"],
            )

    @classmethod
    def on_deactivate_automatic_clean_pre_mask(cls, ctx):
        """
        The mask should only be shown in web ui and if the task project
        is not an MSP project.
        """
        if not ctx.uses_webui:
            ctx.skip_dialog()
        elif ctx.objects:
            project_ids = []
            task_ids = []
            for obj in ctx.objects:
                project_ids.append(obj.cdb_project_id)
                task_ids.append(obj.task_id)
            project_ids = set(project_ids)  # unique ids
            task_ids = set(task_ids)  # unique ids
            projects = Project.KeywordQuery(
                cdb_project_id=project_ids, ce_baseline_id=""
            )
            if any(p.msp_active for p in projects):
                raise ue.Exception(
                    "pcs_no_op_for_msp_project"
                )  # do not perform op in case of MSP proj

            if hasattr(cls, "RessourceAssignments") or hasattr(cls, "ResourcesDemands"):
                tasks = cls.KeywordQuery(task_id=task_ids, ce_baseline_id="")
                tasks_with_resources = []
                for task in tasks:
                    if (
                        len(task.RessourceAssignments) > 0
                        or len(task.RessourceDemands) > 0
                    ):
                        tasks_with_resources.append(task.task_id)
                if len(tasks_with_resources) > 0:
                    raise ue.Exception(
                        "pcs_err_task_resource_exist", len(tasks_with_resources)
                    )

    def on_deactivate_automatic_clean_now(self, ctx):
        """
        Event handler for deactivating automatic flag for tasks and removing date values
        :param ctx:
        :return:
        """

        def deactivate_and_remove_dates():
            self.removeDateValues(ctx=ctx)
            if self._lastObjectOfMultiSelect(ctx=ctx):
                self.recalculate()

        if not ctx.uses_webui:
            if "remove_date_values" not in ctx.dialog.get_attribute_names():
                self.ask_remove_date_values(ctx)
            elif ctx.dialog.remove_date_values == "1":
                deactivate_and_remove_dates()
        else:
            deactivate_and_remove_dates()

    def removeDateValues(self, ctx):
        cca = self.MakeChangeControlAttributes()
        changes = {}
        changes["cdb_mdate"] = cca["cdb_mdate"]
        changes["cdb_mpersno"] = cca["cdb_mpersno"]
        if self.automatic:
            changes["automatic"] = 0
            changes["auto_update_time"] = 0
        if self.start_time_fcast or self.end_time_fcast:
            changes["start_time_fcast"] = ""
            changes["end_time_fcast"] = ""
        if self.constraint_type not in ["0", "1"]:
            changes["constraint_type"] = "0"
            changes["constraint_date"] = ""
        if self.constraint_type not in ["0", "1"]:
            changes["constraint_type"] = "0"
            changes["constraint_date"] = ""
        self.Update(**changes)

    def reinitPosition(
        self, ctx=None, position_initial=None, position_increment=None, next_position=10
    ):
        """
        Initializes the positions of the task structure below the selected node
        Note: Position of the selected task is not initialized
        :param ctx: deprecated
        :param position_initial: initial value (Default: cs.pcs.tasks.Task.position_initial)
        :param position_increment: increment (Default: cs.pcs.tasks.Task.position_increment)
        :param next_position: deprecated
        :return:
        """
        self.current_position = (
            self.position_initial if not position_initial else position_initial
        )
        position_increment = (
            self.position_increment if not position_increment else position_increment
        )
        with transactions.Transaction():
            change_control = Task.MakeChangeControlAttributes()
            for task in self.OrderedSubTasks:
                task.Update(
                    position=self.current_position,
                    cdb_mdate=change_control["cdb_mdate"],
                    cdb_mpersno=change_control["cdb_mpersno"],
                )
                self.current_position += position_increment
                task.reinitPosition()

    def checkTaskId(self, ctx):
        if ctx.get_current_mask() == "initial":
            # Also evaluate baseline tasks to avoid reuse of old task ids
            if self.task_id not in ["#", ""] and Task.ByKeys(
                cdb_project_id=self.cdb_project_id, task_id=self.task_id
            ):
                raise ue.Exception("pcs_err_task_id_exists", self.task_id)

    def setDefaults(self, ctx):
        if ctx.get_current_mask() == "initial":
            self.task_id = "#"
        if ctx.action in ["create", "copy"]:
            if self.Project:
                ctx.set("project_name", self.Project.project_name)
            if self.ParentTask:
                ctx.set("parent_task_name", self.ParentTask.task_name)

    def checkSchedule(self, ctx):
        if self.Project:
            self.Project.checkScheduleLock()

    def checkProjectID(self, ctx):
        if not Project.ByKeys(
            cdb_project_id=self.cdb_project_id, ce_baseline_id=self.ce_baseline_id
        ):
            base = Baseline.ByKeys(cdb_object_id=self.ce_baseline_id)
            raise ue.Exception(
                "pcs_err_prj_id",
                self.project_name,
                base.ce_baseline_name if base else "?",
                self.cdb_project_id,
                self.ce_baseline_id,
            )

    def checkForSubProjects(self, ctx):
        """SampleCode below can be used in subclasses to implement
        restrictions for the project hierachie.

        # dont mix tasks with subprojects
        if self.Project.SubProjects: raise ue.Exception("pcstask_err_mix")
        """
        pass

    def hasTimeSheetEntries(self):
        return len(self.TimeSheets) > 0

    def hasResourceDemands(self):
        return False

    def hasResourceAssignments(self):
        return False

    def assignedDemands(self, _attr):
        """This method serves as a placeholder that is overwritten from
        cs.resources
        """
        return 0.0

    def assignedResources(self, _attr):
        """This method serves as a placeholder that is overwritten from
        cs.resources
        """
        return 0.0

    def assignmentRemainderInHours(self):
        # unassigned efforts in hours
        result = 0.0
        if self.effort_fcast_a:
            result -= self.effort_fcast_a
        if self.effort_fcast:
            result += self.effort_fcast
        elif self.effort_fcast != 0.0:
            result += self.getEffortMax()
        return result

    def getWorkdays(self, persno=None, assignment_oid=None):
        if self.milestone:
            return 0
        start_date = self.start_time_fcast
        end_date = self.end_time_fcast
        if not start_date or not end_date:
            return 0
        try:
            return Calendar.combined_workday_count(
                start_date=start_date,
                end_date=end_date,
                prj=self.Project,
                persno=persno,
                assignment_oid=assignment_oid,
            )
        except Exception:
            logging.exception("Workdays invalid")
            return 0

    def getWorkhours(self):
        return workday.days_to_hours(self.getWorkdays())

    def getWorkdaysInPeriod(self, start_date, end_date):
        if start_date and end_date:
            try:
                sd = self.start_time_fcast
                ed = self.end_time_fcast
                if not sd or not ed:
                    return 0
                sd = max(sd, start_date)
                ed = min(ed, end_date)
                if sd <= ed:
                    return len(Calendar.project_workdays(self.cdb_project_id, sd, ed))
            except Exception:
                logging.exception(
                    "getWorkdaysInPeriod failed for task '%s', '%s', "
                    "start_date '%s', end_date '%s'",
                    self.cdb_project_id,
                    self.task_id,
                    start_date,
                    end_date,
                )
        return 0

    def getWorkhoursInPeriod(self, start_date, end_date):
        return workday.days_to_hours(self.getWorkdaysInPeriod(start_date, end_date))

    @classmethod
    def get_status_by_completion(cls, percent_completion=0):
        status = Task.NEW.status
        if percent_completion == 100:
            status = Task.FINISHED.status
        elif percent_completion > 0:
            status = Task.EXECUTION.status
        return status, cls.get_status_txt(status)

    @classmethod
    def get_status_txt(cls, status=0):
        state_def = olc.StateDefinition.ByKeys(
            statusnummer=status, objektart="cdbpcs_task"
        )
        if state_def:
            return state_def.StateText[""]
        return ""

    def setObjectart(self, ctx):
        """Set attribute cdb_objectart to 'cdbpcs_task'."""
        self.cdb_objektart = "cdbpcs_task"

    def on_cdb_show_responsible_now(self, ctx):
        return self.openSubject()

    def getParent(self):
        """Returns either the project for project stages
        or the parent task for sub tasks or None, if parent_task ist empty."""
        if self.parent_task:
            return self.ParentTask
        return self.Project

    def getParentIDs(self):
        if self.ParentTask:
            return [self.ParentTask.task_id] + self.ParentTask.getParentIDs()
        return []

    def check_for_valid_parent(self, ctx, parent):
        if not ctx or not parent:
            # can only be checked within operation context
            # and with a given parent
            return
        if ctx.action in ["copy", "create"]:
            # "create"- and "copy"-action
            # only new parent has to be checked
            # because the new task always has status NEW
            parent.accept_new_task()
        elif ctx.action in ["modify"] and isinstance(parent, Task):
            # "modify"-action
            # - only check parent tasks because the
            #   assignment to a project can not be changed
            # - check on parent task may only be performed
            #   if parent has actually been changed
            if self.parent_task != getattr(ctx.object, "parent_task", self.parent_task):
                self.accept_new_parent_task(parent)
                parent.accept_new_task()

    def checkParent(self, ctx):
        parent = self.getParent()
        self.check_for_valid_parent(ctx, parent)
        if self.ParentTask:
            if self.task_id in self.getParentIDs():
                raise ue.Exception("pcs_err_rec")
            if self.ParentTask.milestone:
                raise ue.Exception("cdbpcs_err_task_milestone")
            if self.ParentTask in self.AllSubTasks:
                raise ue.Exception("cdbpcs_task_recursion", self.ParentTask.task_name)
            pred_rel_types = [
                rel.rel_type for rel in self.ParentTask.PredecessorTaskRelations
            ]
            if not set(pred_rel_types).issubset(set(ALLOWED_TASK_GROUP_DEPENDECIES)):
                raise util.ErrorMessage(
                    "just_a_replacement",
                    util.get_label("cdbpcs_task_group_rel_not_allowed2")
                    % self.ParentTask.task_name,
                )
            parent.checkConstraints()
            self.check_parent_constraints()

    def checkStructureLock(self, ctx=None):
        if self.Project:
            self.Project.checkStructureLock(ctx=ctx)

    def on_create_pre_mask(self, ctx):
        auto_update_time_value = AutoUpdateTime.ByKeys(
            auto_update_time=self.auto_update_time
        )
        if auto_update_time_value:
            ctx.set(
                "mapped_auto_update_time",
                auto_update_time_value.description,
            )
        if self.cdb_project_id:
            self.checkForSubProjects(ctx)
            self.setPosition(ctx)
            # Projektattribute vorblenden, falls die
            # Aufgabe im Kontext eines Projekts angelegt wird.
            self.division = self.Project.division
        else:
            self.division = auth.get_department()

    def on_copy_pre(self, ctx):
        # reset task uid used by ms project integration
        self.tuid = ""
        self.msp_uid = ""
        self.msp_guid = ""

    def _getResponsibleRole(self):
        return Role.ByKeys(role_id=self.subject_id, cdb_project_id=self.cdb_project_id)

    def get_writable_parent_fields(self, action="modify"):
        # only set fields writable if the corresponding action
        # is 'create', 'copy', 'modify'
        if action not in ["create", "copy", "modify"]:
            return []
        # fields not writable if task or parent task in valid end status
        # if parent is in end status, then the task is as well
        if self.status in self.endStatus(full_cls=False):
            return []
        # parent task fields should be editable within mask
        writable = ["parent_task_name", "parent_task"]
        if action == "copy":
            writable += ["project_name", "cdb_project_id"]
        return writable

    def getReadOnlyFields(self, action="modify", avoid_check=False):
        # pylint: disable=too-many-branches
        # start with a copy of the list containing the class specific readOnly fields
        readonly = list(self.class_specific_read_only_fields)

        if self.status != Task.EXECUTION.status:
            readonly += ["percent_complet"]

        if self.status in [Task.NEW.status, Task.READY.status, Task.DISCARDED.status]:
            readonly += ["start_time_act", "end_time_act"]
        elif self.status == Task.EXECUTION.status:
            readonly += ["end_time_act"]

        if self.is_group:
            readonly += [
                "percent_complet",
                "milestone",
                "start_time_act",
                "end_time_act",
                "effort_act",
            ]

        if action in ("create", "copy") and not self.milestone:
            readonly += ["start_is_early", "end_is_early"]

        elif action == "modify":
            readonly += ["cdb_project_id", "project_name"]

            if self.Project.msp_active:
                readonly += self.Project.get_readonly_task_fields()
                if self.automatic:
                    readonly += ["auto_update_time", "mapped_auto_update_time"]
            elif self.Project.locked_by and self.Project.locked_by != auth.persno:
                readonly += [
                    "start_time_fcast",
                    "end_time_fcast",
                    "days_fcast",
                    "milestone",
                    "parent_task_name",
                    "parent_task",
                    "auto_update_time",
                    "mapped_auto_update_time",
                    "start_is_early",
                    "end_is_early",
                    "position",
                    "automatic",
                    "constraint_type",
                    "constraint_date",
                    "task_name",
                    "mapped_constraint_type_name",
                ]

            if avoid_check:
                readonly += ["parent_task_name", "parent_task", "milestone", "position"]
            else:
                if not self.CheckAccess("pcstask_edit_all"):
                    # this access can only be granted by "FULL ACCESS"
                    # Structural changes may only be done by Project Manager or Administrator
                    readonly += [
                        "parent_task_name",
                        "parent_task",
                        "milestone",
                        "position",
                    ]
                elif self.has_ended():
                    readonly += ["parent_task_name", "parent_task"]
                if self.hasResourceDemands() or self.hasResourceAssignments():
                    readonly += ["milestone"]
                if self.hasTimeSheetEntries():
                    readonly += ["milestone", "effort_act"]
            if self.milestone:
                readonly += ["effort_fcast", "effort_plan", "effort_act", "days_fcast"]
                if self.start_is_early:
                    readonly += ["end_time_fcast"]
                else:
                    readonly += ["start_time_fcast"]
            else:
                readonly += ["start_is_early", "end_is_early"]

            if self.is_group:
                if self.auto_update_time == 1:
                    readonly += ["start_time_fcast", "end_time_fcast", "days_fcast"]
                elif self.auto_update_time == 0:
                    readonly += ["start_time_plan", "end_time_plan", "days"]
                if self.auto_update_effort:
                    readonly += ["effort_fcast"]

            if self.effort_act:
                readonly += ["milestone"]
        return unique(readonly)

    def on_modify_pre(self, ctx):
        if self.parent_task != ctx.object.parent_task:
            self.checkParent(ctx)
            if self.check_for_existing_connections_to_parent(self.ParentTask):
                raise ue.Exception("cdbpcs_parent_sub_cycle_detected")
            ctx.keep("parent_task_changed", ctx.object.parent_task)

    def check_for_existing_connections_to_parent(self, new_parent):
        """
        Checks if a given task may be chosen as the new parent task.
        A cycles of dependencies needs to be prevented.

        The new parent task is not valid, if the called task or one of its
        subtasks can already be found as a predecessor or successor of
        the given parent task.

        :param: new_parent is a task that is chosen to be the new parent task
        :return: True, if cycle is found, else False
        """
        if not new_parent:
            return False

        # all existing connections between tasks are initialized to
        # determine all predecessors and successors of a given task
        Calendar.loadTaskRelations(self.cdb_project_id, check_access=False)
        predecessors = set(Calendar.getAllPredecessors(new_parent, Calendar.START))
        successors = set(Calendar.getAllSuccessors(new_parent, Calendar.END))
        moved_task_structure = [self] + list(self.AllSubTasks)
        moved = {x.cdb_object_id for x in moved_task_structure}
        linked = {x.cdb_object_id for x, _ in predecessors | successors}
        return bool(moved.intersection(linked))

    def on_modify_post(self, ctx):
        if "parent_task_changed" in ctx.ue_args.get_attribute_names():
            old_parent_task_id = ctx.ue_args["parent_task_changed"]
            old_parent_task = None
            if old_parent_task_id:
                old_parent_task = Task.ByKeys(
                    cdb_project_id=self.cdb_project_id, task_id=old_parent_task_id
                )
            self.updateParentTask(ctx, old_parent_task=old_parent_task)

    def on_cdbxml_excel_report_pre_mask(self, ctx):
        self.Super(Task).on_cdbxml_excel_report_pre_mask(ctx)
        if ctx.get_current_mask() != "initial":
            ctx.set("task_name", self.task_name)
            ctx.set("project_name", self.project_name)
            ctx.set("cdbpcs_project_id", self.cdb_project_id)

    def updateParentTask(self, ctx, old_parent_task=None):
        if self.ParentTask:
            # finish parent task if this was the last active subtask
            target_status = self.ParentTask.getFinalStatus()
            if target_status:
                self.ParentTask.ChangeState(target_status, check_access=False)
            if len(self.ParentTask.OrderedSubTasks):
                if not self.ParentTask.is_group:
                    self.ParentTask.updateObject(is_group=1)
            else:
                if self.ParentTask.is_group:
                    self.ParentTask.updateObject(is_group=0)
        else:
            if len(self.Project.TopTasks):
                if not self.Project.is_group:
                    self.Project.updateObject(is_group=1)
            else:
                if self.Project.is_group:
                    self.Project.updateObject(is_group=0)
        if old_parent_task:
            if len(old_parent_task.OrderedSubTasks) == 0:
                old_parent_task.updateObject(is_group=0)

    def GetDisplayAttributes(self):
        """This method creates and returns a results dictionary, containing the
        necessary information for the html display in the client."""
        results = super().GetDisplayAttributes()
        results["attrs"].update({"heading": str(self["category"])})
        return results

    def GetSearchSummary(self):
        """Provides configurable diplay text for the html search results."""
        obj = self.getPersistentObject()
        return f"{obj.description}\n{obj.joined_status_name}"

    @classmethod
    def validateSchedule_many(cls, tasks):
        uuid_condition = format_in_condition(
            "cdb_object_id", [x.cdb_object_id for x in tasks]
        )

        sqlapi.SQLupdate(
            f"""cdbpcs_task
            SET work_uncovered = 0
            WHERE ({uuid_condition})
        """
        )

        for task in tasks:
            if task and not task.milestone:
                sig.emit(Task, "validateSchedule")(task)

    def initConstraintDate(self, ctx):
        if ctx.action in ["create", "copy"]:
            self.change_constraint_type(ctx)

    def set_attributes_to_copy(self):
        """
        Defines which attributes are copied in addition to the default attributes when copying tasks.

        :return: returns a list of attribute names
        :rtype: list
        """
        return ["automatic", "auto_update_time"]

    def setInitValues(self, ctx):  # TODO: REFACTOR
        """
        This method is used for the following actions: create, copy, modify, info
        Note: Copying a task using Drag&Drop identified by action create
        """
        ctx.set_focus("task_name")
        eava = self.getEffortMax()
        # Create and Copy
        if ctx.action in ("copy", "create"):
            self.percent_complet = 0
            self.start_time_act = ""
            self.end_time_act = ""
            self.days_act = 0
            self.psp_code = ""
            self.automatic = 1
            self.position = self.makePosition()
            self.effort_act = 0
            self.rating = ""
            self.rating_descr = ""
            mapped_rating_value_name = [
                attr
                for attr in ctx.dialog.get_attribute_names()
                if "mapped_rating_value_name" in attr
            ]
            for mapped_rating_value in mapped_rating_value_name:
                ctx.set(mapped_rating_value, "")
        # Copy
        if ctx.action in ("copy"):
            copy_keys = ["subject_id", "subject_type"]
            copy_keys.extend(self.set_attributes_to_copy())
            for key in copy_keys:
                self[key] = ctx.cdbtemplate[key]
        # Create
        if ctx.action == "create":
            self.constraint_type = "0"
            self.constraint_date = ""
            copy_keys = []
            my_parent = None
            ctx.set("effort_fcast", eava)
            if self.ParentTask:
                copy_keys = [
                    "task_name",
                    "subject_id",
                    "subject_type",
                    "category",
                    "division",
                    "cdb_objektart",
                    "start_time_fcast",
                    "end_time_fcast",
                    "days_fcast",
                    "auto_update_effort",
                    "auto_update_time",
                    "constraint_type",
                    "constraint_date",
                ]
                my_parent = self.ParentTask
            elif self.Project:
                copy_keys = [
                    "start_time_fcast",
                    "end_time_fcast",
                    "days_fcast",
                ]
                my_parent = self.Project
            # Copy using Drag&Drop
            if isinstance(ctx.dragdrop_op_count, int) and ctx.dragdrop_op_count > 0:
                pnumber = ctx.dragged_obj["cdb_project_id"]
                tnumber = ctx.dragged_obj["task_id"]
                ce_baseline_id = ctx.dragged_obj["ce_baseline_id"]
                task_template = Task.ByKeys(
                    cdb_project_id=pnumber,
                    task_id=tnumber,
                    ce_baseline_id=ce_baseline_id,
                )
                copy_keys = list(task_template)
                copy_keys.remove("cdb_object_id")
                copy_keys.remove("task_id")
                copy_keys.remove("psp_code")
                copy_keys.remove("tuid")
                copy_keys.remove("msp_uid")
                copy_keys.remove("msp_guid")
                copy_keys.remove("ce_baseline_id")
                copy_keys.extend(self.set_attributes_to_copy())
                my_parent = task_template
                # prefill longtext field with description of dragged object
                ctx.set("cdbpcs_task_txt", ctx.dragged_obj["cdbpcs_task_txt"])

            # Werte des übergeordndeten Objekts übertragen
            if my_parent:
                for key in list(my_parent):
                    if key in copy_keys:
                        self[key] = my_parent[key]

        # All actions
        ctx.set("effort_ava", f"{eava:.2f}")
        start_time_ava = self.getStartTimeTopDown() or ""
        ctx.set(
            "start_time_ava",
            to_user_repr_date_format(start_time_ava, i18n.get_date_format()),
        )
        end_time_ava = self.getEndTimeTopDown() or ""
        ctx.set(
            "end_time_ava",
            to_user_repr_date_format(end_time_ava, i18n.get_date_format()),
        )
        # adjust writable and read only fields within the masks
        # Note: some fields have to be set correctly by code, because
        # it can not be done by configuration:
        # - parent_task_name is virtual attribute -> false read only
        # - project_name is mapped attribute and falsely writable
        read_only_fields = self.getReadOnlyFields(action=ctx.action)
        # virtual parent task name is set to read only by default
        writable_fields = self.get_writable_parent_fields(action=ctx.action)
        ctx.set_fields_writeable(set(writable_fields) - set(read_only_fields))
        ctx.set_fields_readonly(read_only_fields)
        self.initConstraintDate(ctx)
        # enable or disable daytime field
        if ctx.uses_webui:
            if self.milestone and not self.automatic:
                if not ctx.action == "info":
                    ctx.set_writeable("mapped_daytime_value")
            else:
                ctx.set_readonly("mapped_daytime_value")
                ctx.set("daytime", "")
        else:
            if not self.milestone or self.automatic:
                ctx.set("daytime", DAYTIME_NOT_APPLICABLE)

    def getEarnedValue(self):
        if not self.isValid():
            return 0.0
        earned_values = [x.getEarnedValue() for x in self.OrderedSubTasks]
        if earned_values:
            return float(sum(earned_values))
        return self.getWorkCompletion() / 100 * self.getPlanCost()

    def getWorkCompletion(self):
        if self.percent_complet and self.isValid():
            return float(self.percent_complet)
        return 0.0

    def getPlanCost(self):
        if self.effort_plan and self.isValid():
            return float(self.effort_plan)
        return 0.0

    def getForeCast(self):
        if self.effort_fcast and self.isValid():
            return float(self.effort_fcast)
        return 0.0

    def getDemandForeCast(self):
        if self.effort_fcast_d and self.isValid():
            return float(self.effort_fcast_d)
        return 0.0

    def getAssignmentForeCast(self):
        if self.effort_fcast_a and self.isValid():
            return float(self.effort_fcast_a)
        return 0.0

    def getActCost(self):
        if self.effort_act:
            return float(self.effort_act)
        return 0.0

    def getPlanTimeCompletion(self, myDate=None):
        if not myDate:
            myDate = datetime.date.today()
        ed = self.end_time_fcast
        if ed and ed <= myDate:
            return 1.0
        return 0.0

    def isValid(self):
        return self.status != Task.DISCARDED.status

    def checkEfforts(self, ctx=None):
        if self.milestone and (
            self.effort_fcast
            or self.effort_plan
            or self.effort_act
            or self.effort_fcast_d
            or self.effort_fcast_a
        ):
            raise ue.Exception("pcs_err_effort3")

    @classmethod
    def adjustDependingObjects_many(cls, tasks):
        """
        Diese Methode muss aufgerufen werden, nachdem mehrere Aufgaben ausserhalb
        des cdb.objects-Frameworks modifiziert wurden.
        """
        # Ressourcenbedarfe und -zuweisungen anpassen
        sig.emit(Task, "adjustDependingObjects_many")(cls, tasks)

        # Testen ob Aufgaben nicht durchführbar sind
        cls.validateSchedule_many(tasks)

    # == Email notification ==

    def getNotificationTitle(self, ctx=None):
        """
        :param ctx:
        :return: title of the notification mail
        :rtype: basestring
        """
        return f"{gui.Message.GetMessage('branding_product_name')} - Công việc đã sẵn sàng / Task ready"

    def getNotificationTemplateName(self, ctx=None):
        """
        :param ctx:
        :return: template name of the notification mail body
        :rtype: basestring
        """
        return "cdbpcs_task_ready.html"

    def getNotificationReceiver(self, _ctx=None):
        """Build a dictionary with adresses to notify. The dictionary must be
        in the form defined by WithEmailNotification.getNotificationReceiver()
        """
        rcvr = {}
        tolist = []
        if self.Subject:
            for pers in self.Subject.getPersons():
                if pers.email_notification_task():
                    tolist.append((pers.e_mail, pers.name))
        if tolist:
            rcvr["to"] = tolist
        # Dependent objects may want to add receivers to notify. Each connected
        # slot must return a dict as described above.
        results = sig.emit(Task, "getNotificationReceiver")(self)
        # Collect results into a single dict.
        for result_dict in results:
            for key in ("to", "cc", "bcc"):
                lst = result_dict.get(key)
                if lst:
                    rcvr[key] = unique(rcvr.get(key, []) + lst)
        return [rcvr]

    def setNotificationContext(self, sc, ctx=None):
        win_links, web_links = get_email_links(
            (self, self.task_name, "CDB_Modify"),
            (self.Project, self.Project.project_name, "cdbpcs_project_overview"),
        )

        sc.task_link_win, sc.task_name_win = win_links[0]
        sc.project_link_win, sc.project_name_win = win_links[1]

        if web_links:
            sc.task_link_web, sc.task_name_web = web_links[
                0
            ]  # pylint: disable=unsubscriptable-object
            sc.project_link_web, sc.project_name_web = web_links[
                1
            ]  # pylint: disable=unsubscriptable-object

    # == End email notification ==

    @classmethod
    def _get_task_id_dictionary(cls, prj_id, check_access=False, tasks_to_check=None):
        task_subtasks = defaultdict(list)
        task_infos = {}
        save_granted = []
        tasks = Project.ByKeys(cdb_project_id=prj_id).Tasks
        for t in tasks:
            if (
                not check_access
                or tasks_to_check
                and t.task_id not in tasks_to_check
                or t.CheckAccess("save", auth.persno)
            ):
                save_granted.append(t.task_id)
            tid = t.task_id
            task_subtasks[t.parent_task].append(tid)
            task_infos[tid] = t
        return task_subtasks, task_infos, save_granted

    @classmethod
    def _get_all_parents(cls, task_id, dic, parent_task=None):
        result = []
        if task_id not in dic:
            task_id = parent_task
        if task_id in dic:
            pt = dic[task_id]["parent_task"]
            if pt:
                result.append(pt)
                result += cls._get_all_parents(pt, dic)
        return result

    @classmethod
    def _check_task_rel_special_case(cls, prj_id, additional=None):
        # pylint: disable=too-many-locals
        edges = []
        nodes = set()
        _, task_infos, _ = Task._get_task_id_dictionary(prj_id)
        for task_id in task_infos:
            nodes.add(task_id)
        sql = (
            "SELECT task_id AS succ, task_id2 AS pred, rel_type"
            " FROM cdbpcs_taskrel"
            f" WHERE cdb_project_id = '{prj_id}' AND cdb_project_id2 = '{prj_id}'"
        )
        rset = sqlapi.RecordSet2(sql=sql)
        for rec in rset:
            edges.append((rec.pred, rec.succ))
        if additional is not None:
            task_id_pred, task_id_succ, _ = additional
            edges.append((task_id_pred, task_id_succ))
            nodes.add(task_id_pred)
            nodes.add(task_id_succ)
        # First clear out nodes without any edges
        toremove = []
        for node in nodes:
            result = False
            for edge in edges:
                if node in edge:
                    result = True
            if not result:
                toremove.append(node)
        for each in toremove:
            nodes.remove(each)

        visited = []
        finished = []

        def dfs(v):
            if v in finished:
                return True
            if v in visited:
                return False
            visited.append(v)
            edges_of_v = [
                t_id_task_id2 for t_id_task_id2 in edges if v == t_id_task_id2[0]
            ]
            result = True
            for each in edges_of_v:
                if not dfs(each[1]):
                    result = False
            if result:
                finished.append(v)
            return result

        result = True
        for node in nodes:
            r2 = dfs(node)
            if not r2:
                result = False
                break

        notfinished = list(set(nodes) - set(finished))
        predecessor = None
        if not result:
            predecessor = {}
            for node in notfinished:
                edges_of_v = [
                    t_id_task_id2 for t_id_task_id2 in edges if node == t_id_task_id2[0]
                ]
                sucessors = [(y, "") for _, y in edges_of_v]
                predecessor[(node, "")] = sucessors

        return predecessor

    @classmethod
    def _check_task_rel_cycles(cls, prj_id, additional=None):
        # pylint: disable=too-many-locals
        """Check if there are cyclic task relationships defined inside the
        project given by prj_id. To account for the different relationship
        types (EA, EE, AA, AE), each task is split into a START and an END
        position, and implicit relationships are added between each task's
        START and END, as well as between the START of a parent and subtask
        and the END of a subtask and its parent.
        In the parameter additional, a further relationship can be given by
        the caller as a tuple
        (predecessor task id, successor task id, relationship type),
        that is added to the total set. The purpose of this parameter is to
        implement a cycle check before a relationship is actually added to
        the DB.
        Returns a dict [task id] -> set([predecessor task ids]).
        If a cycle is found, the dict contains all the relationships that
        are (directly or indirectly) part of the cycle. If no cycle is found,
        the dict is empty.
        """
        START = "START"
        END = "END"
        REL_TYPE_POSITIONS = {
            kTaskDependencyAA: (START, START),
            kTaskDependencyEA: (END, START),
            kTaskDependencyAE: (START, END),
            kTaskDependencyEE: (END, END),
        }
        task_subtasks, task_infos, _ = Task._get_task_id_dictionary(prj_id)
        # For each task start / end, store all task relations that point there.
        predecessors = defaultdict(set)
        # Each task has an implicit relation from start to end, this simplifies
        # the logic later because we don't have to distinguish between the
        # various relation types.
        for task_id in task_infos:
            predecessors[(task_id, END)].add((task_id, START))
        # Child tasks may not start before their parents, and not end after
        # their parents.
        for parent_id, subtasks in task_subtasks.items():
            for subtask_id in subtasks:
                predecessors[(subtask_id, START)].add((parent_id, START))
                predecessors[(parent_id, END)].add((subtask_id, END))
        # Add the explicitly stored task relations.
        sql = (
            "SELECT task_id AS succ, task_id2 AS pred, rel_type"
            " FROM cdbpcs_taskrel"
            f" WHERE cdb_project_id = '{prj_id}' AND cdb_project_id2 = '{prj_id}'"
        )
        rset = sqlapi.RecordSet2(sql=sql)
        for rec in rset:
            pred_pos, succ_pos = REL_TYPE_POSITIONS[rec.rel_type]
            predecessors[(rec.succ, succ_pos)].add((rec.pred, pred_pos))
        # If an additional relship is given, add that too.
        if additional is not None:
            task_id_pred, task_id_succ, rel_type = additional
            pred_pos, succ_pos = REL_TYPE_POSITIONS[rel_type]
            predecessors[(task_id_succ, succ_pos)].add((task_id_pred, pred_pos))
        # Check for cycles
        while predecessors:
            progress = False
            # Collect everything listed as a predecessors.
            candidates = set()
            for rels in predecessors.values():
                candidates.update(rels)
            # Remove entries that are not listed as a predecessor.
            not_mentioned = set(predecessors.keys()).difference(candidates)
            for task_id in not_mentioned:
                del predecessors[task_id]
                progress = True
            # Remove refs to entries that don't have predecessors themselves.
            candidates.difference_update(list(predecessors))
            if candidates:
                # Remove those entries from the predecessor list ...
                for rels in predecessors.values():
                    rels.difference_update(candidates)
                # ... and remove all entries, that have no more predecessors
                empties = [k for k, v in predecessors.items() if not v]
                for task_id in empties:
                    del predecessors[task_id]
                    progress = True
            # If we did nothing at all, break the loop -> we have a circle.
            if not progress:
                break
        return dict(predecessors)

    @classmethod
    def _get_all_subtask_ids(cls, cdb_project_id, task_id=None):
        dbms = sqlapi.SQLdbms()
        if not task_id:
            task_id = "chr(1)" if dbms == sqlapi.DBMS_ORACLE else "''"
        query = (
            "(cdb_project_id, task_id, parent_task, lev) "
            "AS ("
            "SELECT t1.cdb_project_id, t1.task_id, t1.parent_task, 0 AS lev "
            "FROM cdbpcs_task t1 "
            f"WHERE cdb_project_id = '{cdb_project_id}' "
            f"AND parent_task = '{task_id}' "
            "AND ce_baseline_id = '' "
            "UNION ALL "
            "SELECT t2.cdb_project_id, t2.task_id, t2.parent_task, h.lev+1 AS lev "
            "FROM cdbpcs_task t2 "
            "JOIN hierarchical h ON h.task_id = t2.parent_task AND t2.ce_baseline_id = ''"
            ") "
            "SELECT cdb_project_id, task_id, parent_task, lev "
            "FROM hierarchical ORDER BY lev DESC"
        )
        if dbms == sqlapi.DBMS_POSTGRES:
            query = "WITH RECURSIVE hierarchical " + query
        else:
            query = "WITH hierarchical " + query
        result = []
        for task in sqlapi.RecordSet2(sql=query):
            result.append(task.task_id)
        return result

    @classmethod
    def _check_task_rel_parent_cycles(cls, prj_id, additional=None):
        if not additional:
            return None
        # check if new predecessor task is one of succcessors subtasks
        if additional[0] in cls._get_all_subtask_ids(
            cdb_project_id=prj_id, task_id=additional[1]
        ):
            return "parent circle found"
        # check if new successor task is one of predecessors subtasks
        if additional[1] in cls._get_all_subtask_ids(
            cdb_project_id=prj_id, task_id=additional[0]
        ):
            return "parent circle found"
        return None

    def _ensureResourceConstraints(self, start, end):
        if self.hasResourceDemands() and (not start or not end):
            raise AbortMessage("cdbpcs_demand_needs_dates", self.task_name)
        if self.hasResourceAssignments() and (not start or not end):
            raise AbortMessage("cdbpcs_assignment_needs_dates", self.task_name)

    def setTimeframe(self, ctx=None, start=None, end=None, days=None, **kwargs):
        with transactions.Transaction():
            start, end, days = self.calculateTimeFrame(start=start, end=end, days=days)
            self._ensureResourceConstraints(start=start, end=end)
            operation(
                kOperationModify,
                self.getPersistentObject(),
                start_time_fcast=start,
                end_time_fcast=end,
                days_fcast=days,
                **kwargs,
            )
            self.Reload()
            sig.emit(Task, "adjust_dates")(self)

    @classmethod
    def mark_as_changed(cls, **kwargs):
        c_ctrl = Task.MakeChangeControlAttributes()
        if kwargs:
            kwargs.update(ce_baseline_id="")
            tasks = Task.KeywordQuery(**kwargs)
            tasks.Update(
                cdb_apersno=c_ctrl["cdb_mpersno"], cdb_adate=c_ctrl["cdb_mdate"]
            )

    def getWorkdaysFcast(self):
        return Calendar.getWorkdays(
            self.cdb_project_id, self.start_time_fcast, self.end_time_fcast
        )

    def on_cdbpcs_task_reset_start_time_pre_mask(self, ctx):
        self.checkStructureLock(ctx=ctx)
        if not self.start_time_fcast:
            raise ue.Exception("pcs_move_task_error_01")
        ctx.set("start_time_old", self.start_time_fcast)
        ctx.set("end_time_old", self.end_time_fcast)

    def move_dates(self, start_time_new, end_time_new):
        changes = {"days": self.days_fcast}
        if start_time_new:
            changes["start"] = getNextStartDate(
                self.Project.cdb_project_id, start_time_new
            )
        elif end_time_new:
            changes["end"] = getNextEndDate(self.Project.cdb_project_id, end_time_new)
        else:
            return None
        start, end, _ = self.calculateTimeFrame(**changes)
        return start, end

    def on_cdbpcs_task_reset_start_time_dialogitem_change(self, ctx):
        if ctx.changed_item == "start_time_new":
            start_time_new = ctx.dialog.start_time_new
            end_time_new = None
        elif ctx.changed_item == "end_time_new":
            start_time_new = None
            end_time_new = ctx.dialog.end_time_new
        result = self.move_dates(start_time_new, end_time_new)
        if result:
            start, end = result
            ctx.set(".start_time_new", start)
            ctx.set(".end_time_new", end)

    def on_cdbpcs_task_reset_start_time_now(self, ctx):
        self.checkStructureLock(ctx=ctx)
        newsd = None
        try:
            newsd = ctx.dialog.start_time_new
        except AttributeError:
            logging.exception("start_time_new not found in ctx.dialog")
        if not newsd:
            return
        newsd = from_legacy_date_format(newsd).date()
        self.reset_start_time(ctx, newsd)

    def reset_start_time(self, ctx=None, start_time_new=None):
        """
        The method moves both the set value and the aggregated value of the
        called and all child elements. Finally, the parent elements are also
        adjusted. If necessary, predecessors or successors are also moved
        during the schedule shifts, provided that they are part of the
        same project.
        """
        if not start_time_new:
            return

        newsd = start_time_new

        if not newsd:
            return

        oldsd = ensure_date(ctx.dialog["start_time_old"])

        # new start date must be within the valid time span
        if newsd < self.Project.CalendarProfile.valid_from:
            nsd = to_legacy_date_format_auto(newsd)
            cp_sd = to_legacy_date_format_auto(self.Project.CalendarProfile.valid_from)
            cp_ed = to_legacy_date_format_auto(self.Project.CalendarProfile.valid_until)
            raise ue.Exception("cdb_proj_cal_prof", nsd, "?", cp_sd, cp_ed)

        # determine distance to move
        calendar_profile_id = self.Project.calendar_profile_id
        (new_start_idx, _) = Calendar.getIndexByDate(
            calendar_profile_id, to_python_rep(sqlapi.SQL_DATE, newsd)
        )
        (old_start_idx, _) = Calendar.getIndexByDate(
            calendar_profile_id, to_python_rep(sqlapi.SQL_DATE, oldsd)
        )
        if old_start_idx and new_start_idx:
            distance = new_start_idx - old_start_idx
            if distance:
                # adjust constraint dates of all subtasks and start dates for all manual tasks
                for t in self.AllSubTasks:
                    t.moveFixedDates(
                        distance=distance, calendar_profile_id=calendar_profile_id
                    )
                # move task and start adjustment process
                self.setStartTimeFcast(start=newsd)

    def moveFixedDates(self, distance, calendar_profile_id):
        try:
            if self.constraint_date:
                (constraint_idx, _) = Calendar.getIndexByDate(
                    calendar_profile_id, self.constraint_date
                )
                if constraint_idx and distance:
                    self.constraint_date = Calendar.getDateByIndex(
                        calendar_profile_id, constraint_idx + distance
                    )
            if not self.automatic and distance:
                if self.start_time_fcast and self.end_time_fcast:
                    (start_time_dix, _) = Calendar.getIndexByDate(
                        calendar_profile_id, self.start_time_fcast
                    )
                    (end_time_dix, _) = Calendar.getIndexByDate(
                        calendar_profile_id, self.end_time_fcast
                    )
                    if start_time_dix and end_time_dix:
                        sd = Calendar.getDateByIndex(
                            calendar_profile_id, start_time_dix + distance
                        )
                        ed = Calendar.getDateByIndex(
                            calendar_profile_id, end_time_dix + distance
                        )
                        self.Update(start_time_fcast=sd, end_time_fcast=ed)
        except Exception as e:
            misc.cdblogv(misc.kLogErr, 0, e)

    # == Create ==
    def on_create_post(self, ctx):
        if isinstance(ctx.dragdrop_op_count, int) and ctx.dragdrop_op_count > 0:
            pnumber = ctx.dragged_obj["cdb_project_id"]
            tnumber = ctx.dragged_obj["task_id"]
            ce_baseline_id = ctx.dragged_obj["ce_baseline_id"]
            task_template = Task.ByKeys(
                cdb_project_id=pnumber, task_id=tnumber, ce_baseline_id=ce_baseline_id
            )
            with transactions.Transaction():
                self._copy_task_structure(ctx, pnumber, tnumber, ce_baseline_id)
                self.Reload()
                self.Project.adopt_all_project_roles_from_template(
                    task_template=task_template
                )
                self.Project.reset_invalid_subject_ids()

    # == Copy ==
    def on_copy_post(self, ctx):
        pnumber = ctx.cdbtemplate["cdb_project_id"]
        tnumber = ctx.cdbtemplate["task_id"]
        ce_baseline_id = ctx.cdbtemplate["ce_baseline_id"]
        task_template = Task.ByKeys(
            cdb_project_id=pnumber, task_id=tnumber, ce_baseline_id=ce_baseline_id
        )
        with transactions.Transaction():
            self._copy_task_structure(ctx, pnumber, tnumber, ce_baseline_id)
            self.Reload()
            self.Project.adopt_all_project_roles_from_template(
                task_template=task_template
            )
            self.Project.reset_invalid_subject_ids()

    def _copy_task_structure(self, ctx, pnumber, tnumber, ce_baseline_id):
        task_template = Task.ByKeys(
            cdb_project_id=pnumber, task_id=tnumber, ce_baseline_id=ce_baseline_id
        )
        new_project_id = self.cdb_project_id
        parent_id = self.parent_task
        my_task = self.getPersistentObject()
        task_id_mapping_table, new_task = task_template._copy_task(
            ctx, new_project_id, parent_id, my_task
        )
        # Copy of task relations
        Task._copy_taskrels_by_mapping(pnumber, new_project_id, task_id_mapping_table)

        # Check consistency for whole project
        self.Project.Reload()
        self.Project.recalculate()
        sig.emit(Task, "copy_task_structure")(new_task)

    @classmethod
    def _copy_taskrels_by_mapping(
        cls, old_project_id, new_project_id, task_id_mapping_table
    ):
        # Copy of task relations
        task_rel_keys = list(task_id_mapping_table)
        # Only the relations within internal tasks are copied
        task_relations = TaskRelation.KeywordQuery(
            cdb_project_id=old_project_id,
            task_id=task_rel_keys,
            cdb_project_id2=old_project_id,
            task_id2=task_rel_keys,
        )
        for rel in task_relations:
            copy_cdb_project_id = rel.cdb_project_id
            copy_cdb_project_id2 = rel.cdb_project_id2
            copy_task_id = rel.task_id
            copy_task_id2 = rel.task_id2
            if copy_cdb_project_id == old_project_id:
                copy_cdb_project_id = new_project_id
            if copy_cdb_project_id2 == old_project_id:
                copy_cdb_project_id2 = new_project_id
            if copy_task_id in task_rel_keys:
                copy_task_id = task_id_mapping_table[copy_task_id]
            if copy_task_id2 in task_rel_keys:
                copy_task_id2 = task_id_mapping_table[copy_task_id2]

            rel.Copy(
                cdb_project_id=copy_cdb_project_id,
                cdb_project_id2=copy_cdb_project_id2,
                task_id=copy_task_id,
                task_id2=copy_task_id2,
            )
        Task._updateTaskRelations(new_project_id)

    @classmethod
    def _updateTaskRelations(cls, prj_id):
        dbms_empty = "chr(1)" if sqlapi.SQLdbms() == sqlapi.DBMS_ORACLE else "''"
        sql_where = f" WHERE cdb_project_id = '{prj_id}'"
        upd1 = (
            "cdbpcs_taskrel SET succ_project_oid = ("
            "SELECT cdb_object_id FROM cdbpcs_project WHERE "
            "cdbpcs_taskrel.cdb_project_id = cdbpcs_project.cdb_project_id "
            f"AND cdbpcs_project.ce_baseline_id = {dbms_empty}"
            ")"
        )
        upd2 = (
            "cdbpcs_taskrel SET pred_project_oid = ("
            "SELECT cdb_object_id FROM cdbpcs_project WHERE "
            "cdbpcs_taskrel.cdb_project_id2 = cdbpcs_project.cdb_project_id "
            f"AND cdbpcs_project.ce_baseline_id = {dbms_empty}"
            ")"
        )
        upd3 = (
            "cdbpcs_taskrel SET succ_task_oid = ("
            "SELECT cdb_object_id FROM cdbpcs_task WHERE "
            "cdbpcs_taskrel.cdb_project_id = cdbpcs_task.cdb_project_id "
            "AND cdbpcs_taskrel.task_id = cdbpcs_task.task_id "
            f"AND cdbpcs_task.ce_baseline_id = {dbms_empty}"
            ")"
        )
        upd4 = (
            "cdbpcs_taskrel SET pred_task_oid = ("
            "SELECT cdb_object_id FROM cdbpcs_task WHERE "
            "cdbpcs_taskrel.cdb_project_id2 = cdbpcs_task.cdb_project_id "
            "AND cdbpcs_taskrel.task_id2 = cdbpcs_task.task_id "
            f"AND cdbpcs_task.ce_baseline_id = {dbms_empty}"
            ")"
        )

        sqlapi.SQLupdate(upd1 + sql_where)
        sqlapi.SQLupdate(upd2 + sql_where)
        sqlapi.SQLupdate(upd3 + sql_where)
        sqlapi.SQLupdate(upd4 + sql_where)

    @classmethod
    def warn_msp_synchronize(cls, ctx):
        if ctx.uses_webui:
            raise ue.Exception(-1024, util.get_label("cdbpcs_msp_synchronize"))

        msgbox = ctx.MessageBox(
            "cdbpcs_msp_synchronize",
            [],
            "cdbpcs_msp_synchronize",
            ctx.MessageBox.kMsgBoxIconInformation,
        )
        msgbox.addButton(ctx.MessageBoxButton("ok", "OK"))
        ctx.show_message(msgbox)

    @classmethod
    def on_cdbpcs_create_from_pre_mask(cls, ctx):
        if not ctx.uses_webui:
            ctx.skip_dialog()
        else:
            if hasattr(ctx.parent, "cdb_project_id"):
                parent_project = ctx.parent.cdb_project_id
                ctx.set("parent_project", parent_project)

            if hasattr(ctx.parent, "task_id"):
                parent_task = ctx.parent.task_id
                ctx.set("parent_task", parent_task)

    @classmethod
    def on_cdbpcs_create_from_now(cls, ctx):
        if "cdbpcs_msp_synchronize" not in ctx.dialog.get_attribute_names():
            project = None
            parent_obj = None
            if (
                ctx.uses_webui
                and hasattr(ctx.dialog, "parent_project")
                and hasattr(ctx.dialog, "parent_task")
            ):
                p_id = ctx.dialog.parent_project
                t_id = ctx.dialog.parent_task
                # baseline id is not evaluated, because they can not be
                # chosen as template
                if p_id:
                    parent_obj = Project.ByKeys(cdb_project_id=p_id)
                    project = parent_obj
                if t_id:
                    parent_obj = Task.ByKeys(cdb_project_id=p_id, task_id=t_id)
            elif "cdbpcs_project" in ctx.parent_keys:
                parent_obj = Project.ByKeys(cdb_project_id=ctx.parent["cdb_project_id"])
                project = parent_obj
            elif "cdbpcs_task" in ctx.parent_keys:
                parent_obj = Task.ByKeys(
                    cdb_project_id=ctx.parent["cdb_project_id"],
                    task_id=ctx.parent["task_id"],
                )
                project = parent_obj.Project
            cls._cdbpcs_create_from(ctx=ctx, project=project, parent_obj=parent_obj)
            if (
                parent_obj
                and hasattr(parent_obj, "msp_active")
                and parent_obj.msp_active
            ) or (
                parent_obj
                and hasattr(parent_obj, "Project")
                and parent_obj.Project.msp_active
            ):
                cls.warn_msp_synchronize(ctx)

    @classmethod
    def _cdbpcs_create_from(cls, ctx, project=None, parent_obj=None):
        if (
            not project
            or not parent_obj
            or not getattr(parent_obj, "cdb_project_id", False)
        ):
            raise ue.Exception("pcs_error_create_from_context")

        parent_obj.accept_new_task()
        if not parent_obj.CheckAccess("save"):
            raise ue.Exception("cdbpcs_no_right_to_create_task_from_template")

        pnumber, tnumber, ce_baseline_id = cls._get_task_selection(ctx)
        if pnumber and tnumber:
            cls._process_create_from(
                ctx, pnumber, tnumber, ce_baseline_id, project, parent_obj
            )

    @classmethod
    def _get_task_selection(cls, ctx):
        pnumber, tnumber, ce_baseline_id = None, None, None
        if ctx.uses_webui:
            pnumber = ctx.dialog["cdb_project_id"]
            tnumber = ctx.dialog["task_id"]
            ce_baseline_id = ctx.dialog["ce_baseline_id"]
        else:
            if not ctx.catalog_selection:
                ctx.start_selection(catalog_name="cdbpcs_projects")
            elif "task_id" not in ctx.catalog_selection[0].get_attribute_names():
                pnumber = ctx.catalog_selection[0]["cdb_project_id"]
                ce_baseline_id = ctx.catalog_selection[0]["ce_baseline_id"]
                ctx.start_selection(
                    catalog_name="cdbpcs_task_templates",
                    cdb_project_id=pnumber,
                    ce_baseline_id=ce_baseline_id,
                )
            else:
                pnumber = ctx.catalog_selection[0]["cdb_project_id"]
                tnumber = ctx.catalog_selection[0]["task_id"]
                ce_baseline_id = ctx.catalog_selection[0]["ce_baseline_id"]
        return (pnumber, tnumber, ce_baseline_id)

    @classmethod
    def _process_create_from(
        cls, ctx, pnumber, tnumber, ce_baseline_id, project, parent_obj
    ):
        task_template = Task.ByKeys(
            cdb_project_id=pnumber, task_id=tnumber, ce_baseline_id=ce_baseline_id
        )
        parent_id = ""
        if "task_id" in parent_obj:
            parent_id = parent_obj["task_id"]

        new_project_id = parent_obj["cdb_project_id"]
        sig_args = {
            "template_task": task_template,
            "target_parent": parent_obj,
            "target_project": project,
        }
        # signal for collecting changes to be applied during creation of task
        # from template. A dictionary of key-value-pairs is expected from each
        # connecting method. The dictionaries are merged and handed to
        # the signal 'modify_new_task_created_from_template' in _copy_task.
        changes = {}
        sig_response = sig.emit(
            Task, "collect_additional_info_before_create_from_template"
        )(sig_args)
        if sig_response and len(sig_response) > 0:
            for sig_changes in sig_response:
                changes.update(sig_changes)
        with transactions.Transaction():
            task_id_mapping_table, new_task = task_template._copy_task(
                ctx, new_project_id, parent_id, **changes
            )

            # Copy of task relations
            Task._copy_taskrels_by_mapping(
                pnumber, new_project_id, task_id_mapping_table
            )

        # Check consistency for whole project
        project.Reload()
        if not project.msp_active:
            project.recalculate()

        project.adopt_all_project_roles_from_template(task_template=task_template)
        project.reset_invalid_subject_ids()
        if not project.msp_active:
            if not ctx.uses_webui:
                ctx.url(new_task.MakeURL("cdbpcs_task_reset_start_time"))
            elif ctx.dialog.start_time_old:
                new_task.on_cdbpcs_task_reset_start_time_now(ctx)

    def _copy_task(
        self,
        ctx,
        new_project_id,
        parent="",
        new_task=None,
        clear_msp_task_ids=True,
        **kwargs,
    ):
        # pylint: disable=too-many-locals
        mapping_table = {}

        # We assume in the delivery state, no attributes are changed that determine the type
        # of the task object (class determined by the Most-Derived-Type-Discovery of the CE Server).
        cls = type(self)
        new_task_check = cls(**self._record)

        # If the task is copied to it's own subtasks
        redundantTasks = []
        taskIsItsOWnParent = 0
        if self.task_id == parent:
            taskIsItsOWnParent = 1
            # Updating the parents as the task points to itsef as parent
            parent = self.ParentTask.task_id if self.ParentTask is not None else ""

        new_task_check.cdb_project_id = new_project_id
        new_task_check.parent_task = parent

        # Create a new UUID for the copied task object
        new_task_check.cdb_object_id = cdbuuid.create_uuid()

        # Ensure that baseline id is empty for new tasks
        new_task_check.ce_baseline_id = ""

        # Reset psp_code for the copied task object
        new_task_check.psp_code = ""

        # Template object id stored to identify the original copied task
        new_task_check.template_oid = self.cdb_object_id

        # Reset status for the copied task object. Needs to be 0 to allow copy.
        new_task_check.status = 0

        # Reset cdb_finishedby for the copied task object.
        new_task_check.cdb_finishedby = None

        # remove forecast dates
        new_task_check.start_time_plan = None
        new_task_check.end_time_plan = None
        new_task_check.days = None

        # clear evaluation and evaluation descr for action 'cdbpcs_create_from'
        if ctx.action == "cdbpcs_create_from":
            new_task_check.rating = ""
            new_task_check.rating_descr = ""

        # Reset position for the copied task object. Position will be set later.
        keep_positions_of_tasks = (
            getattr(ctx.ue_args, "keep_positions_of_tasks", "0") == "1"
        )
        if not keep_positions_of_tasks:
            new_task_check.position = ""

        if clear_msp_task_ids:
            # Reset tuid for the copied task object
            # (identifier for transmitting task between msp and cdb)
            new_task_check.tuid = ""
            new_task_check.msp_uid = ""
            new_task_check.msp_guid = ""

        # emit signal after pcs specific changes to allow further changes
        # emit with new task and kwargs to determine changes on the new task
        sig_args = {"parent_id": parent, "new_task": new_task_check, "params": kwargs}
        sig_response = sig.emit(Task, "modify_new_task_created_from_template")(sig_args)
        if sig_response and len(sig_response) > 0:
            for changes in sig_response:
                # Update new_task_check with retrieved changes
                # NOTE: In case of multiple changes for the same attribute
                #       the last one wins
                new_task_check.Update(**changes)

        old_task_id = new_task_check.task_id
        if not new_task:
            new_task_check._create_from_pre_check(ctx)

        # Create a new task object and write it into database
        new_task_check.Update(**Task.MakeChangeControlAttributes())

        if not new_task:
            new_task = Task.Create(**new_task_check)
        new_task.Reset()

        # Mapping table for task ID (old task ID -> new task ID)
        new_task_id = new_task.task_id
        mapping_table[old_task_id] = new_task_id

        # Copy long text fields
        new_cdbpcs_task_txt = self.GetText("cdbpcs_task_txt")
        if (
            ctx
            and ctx.dialog
            and hasattr(ctx.dialog, "cdbpcs_task_txt")
            and hasattr(ctx.dialog, "task_id")
        ):
            if ctx.dialog.task_id == new_task.task_id:
                new_cdbpcs_task_txt = ctx.dialog.cdbpcs_task_txt
        new_task.SetText("cdbpcs_task_txt", new_cdbpcs_task_txt)

        # Copy sub-tasks recursively
        for task in self.OrderedSubTasks:
            if taskIsItsOWnParent and mapping_table[self.task_id] == task.task_id:
                redundantTasks.append(task)
            if task not in redundantTasks:
                task_mapping, _ = task._copy_task(
                    ctx,
                    new_project_id,
                    new_task.task_id,
                    clear_msp_task_ids=clear_msp_task_ids,
                    **kwargs,
                )
                mapping_table.update(task_mapping)

        new_project = Project.ByKeys(cdb_project_id=new_project_id)
        self.copyRelatedObjects(new_project, new_task)

        # Check copied task
        new_task.Reload()
        new_task._create_from_post_check(ctx)
        new_task._create_from_final_check(ctx)

        return mapping_table, new_task

    def copyRelatedObjects(self, new_project, new_task):
        # Copy referenced document templates
        doc_templ_t = ddl.Table("cdbpcs_task2doctmpl")
        if doc_templ_t.exists():
            for temp_doc in self.TemplateDocRefs:
                values = new_task.KeyDict()
                values["created_at"] = None
                temp_doc.Copy(**values)

        # Copy referenced checklists
        for checklist in self.Checklists:
            new_checklist = checklist.MakeCopy(new_project, new_task)
            new_checklist.Reset()

        # Copy referenced issues
        # for issue in self.Issues:
        #     new_issue = issue.MakeCopy(new_project, new_task)
        #     new_issue.Reset()

        # Copy referenced objects (eg. resource demands)
        sig.emit(Task, "copy_task_hook")(self, new_project, new_task)

    def _create_from_pre_check(self, ctx=None):

        # Check follows before cdbpcs_create_from operation
        # 1. checkParent
        # 2. checkProjectID
        # 3. setTaskID
        # 4. setPosition

        # Check parent
        self.checkParent(ctx)

        # Check project ID
        self.checkProjectID(ctx)

        # Set task ID
        self.setTaskID(ctx)

        # Set position
        self.setPosition(ctx)

    def _create_from_post_check(self, ctx=None):
        # Check follows after cdbpcs_create_from operation
        self.updateParentTask(ctx)

    def _create_from_final_check(self, ctx=None):
        # Final check after cdbpcs_create_from operation
        pass

    # == End Create From ==

    def getEffortAggr(self):
        if not self.isValid():
            return 0.0
        if self.effort_fcast:
            return self.effort_fcast
        if self.effort_plan:
            return self.effort_plan
        return 0.0

    def getEffortAvailable(self):
        result = 0.0
        if self.effort_fcast:
            result = self.effort_fcast
        else:
            result = self.getEffortMax()
        if self.is_group and self.effort_plan:
            result -= self.effort_plan
        return result

    def getEffortMax(self):
        parentobj = self.getParent()
        emax = self.getEffortAggr()
        if parentobj:
            emax += parentobj.getEffortAvailable()
        return max(0.0, emax)

    def calculateTimeFrame(self, start=None, end=None, days=None, shift_right=True):
        calendar_profile_id = None
        if self.Project:
            calendar_profile_id = self.Project.calendar_profile_id
        if not days and self.automatic:
            days = int(not self.milestone)
        start, end, days = Calendar.calculateTimeFrame(
            calendar_profile_id,
            start=start,
            end=end,
            days=days,
            shift_right=shift_right,
            milestone=self.milestone,
        )
        if (
            not start
            and not end
            and self.is_group
            and self.auto_update_time
            and self.automatic
        ):
            days = None
        return start, end, days

    def get_days_actual(self, start, end):
        days_act = None
        if start and end:
            _, _, days_act = self.calculateTimeFrame(start=start, end=end)
        return days_act

    def validate_time_act(self, start_time_act, end_time_act):
        if start_time_act and end_time_act and start_time_act > end_time_act:
            raise ue.Exception(1024, util.get_label("pcs_days_act_end_before_start"))
        if end_time_act and not start_time_act:
            raise ue.Exception(
                1024, util.get_label("pcs_start_act_present_when_end_act")
            )

    def validate_and_update_days_act(self, ctx):
        self.validate_time_act(self.start_time_act, self.end_time_act)

        self.Update(
            days_act=self.get_days_actual(self.start_time_act, self.end_time_act)
        )

    # create/copy/modify: pre
    def checkEffortFields(self, ctx):
        changes = {}
        if not self.is_group:
            if self.effort_plan != self.effort_fcast:
                changes.update(effort_plan=self.effort_fcast)
            if self.start_time_fcast is None:
                changes.update(start_time_fcast="")
            if self.end_time_fcast is None:
                changes.update(end_time_fcast="")
        self.Update(**changes)

        # start/end must be filled jointly
        if (
            self.start_time_fcast
            and not self.end_time_fcast
            or not self.start_time_fcast
            and self.end_time_fcast
        ):
            raise ue.Exception("pcs_capa_err_025")

        # allow other components to check preconditions before modifying a task
        sig.emit(Task, "checkEffortFields")(self)

    @classmethod
    def getDemandStartTimeFieldName(cls):
        return "start_time_fcast"

    @classmethod
    def getDemandEndTimeFieldName(cls):
        return "end_time_fcast"

    @classmethod
    def getAssignmentStartTimeFieldName(cls):
        return "start_time_fcast"

    @classmethod
    def getAssignmentEndTimeFieldName(cls):
        return "end_time_fcast"

    def getDemandStartTime(self):
        return self[self.getDemandStartTimeFieldName()]

    def getDemandEndTime(self):
        return self[self.getDemandEndTimeFieldName()]

    def getAssignmentStartTime(self):
        return self[self.getAssignmentStartTimeFieldName()]

    def getAssignmentEndTime(self):
        return self[self.getAssignmentEndTimeFieldName()]

    def getEndTimeAggr(self):
        return self.end_time_fcast if self.end_time_fcast else self.end_time_plan

    def getEffortForeCast(self):
        if not self.isValid():
            return 0.0
        return self.effort_fcast

    def getEffortPlan(self):
        if not self.isValid():
            return 0.0
        return self.effort_plan

    def getStartTimeFcast(self):
        return self.start_time_fcast

    def getStartTimePlan(self):
        return self.start_time_plan

    def getEndTimeFcast(self):
        return self.end_time_fcast

    def getEndTimePlan(self):
        return self.end_time_plan

    def getStartTimeTopDown(self):
        if self.ParentTask:
            if self.ParentTask.start_time_fcast:
                return self.ParentTask.start_time_fcast
            else:
                return self.ParentTask.getStartTimeTopDown()
        elif self.Project:
            return self.Project.start_time_fcast
        else:
            return None

    def getEndTimeTopDown(self):
        if self.ParentTask:
            if self.ParentTask.end_time_fcast:
                return self.ParentTask.end_time_fcast
            else:
                return self.ParentTask.getEndTimeTopDown()
        elif self.Project:
            return self.Project.end_time_fcast
        else:
            return None

    def getPredecessorTasks(self, dependency=kTaskDependencyEA):
        return [
            x.PredecessorTask for x in self.PredecessorTaskRelationsByType[dependency]
        ]

    def check_Project_State(self, ctx=None):
        if self.Project:
            self.Project.isFinalized()

    def setTemplateOID(self, ctx=None):
        if not ctx or ctx.action == "delete":
            sqlapi.SQLupdate(
                f"cdbpcs_task SET template_oid = '' WHERE template_oid = '{self.cdb_object_id}'"
                " AND ce_baseline_id = ''"
            )

    def check_deepdelete(self, reason=False):
        """Returns a list of objects which could block the deletion of the Task"""
        import operator

        result = []

        def add_result(prefix, obj, reason_label_id):
            if reason:
                text = f"{prefix}{obj.GetDescription()} ({util.get_label(reason_label_id)})"
            else:
                text = f"{prefix}{obj.GetDescription()}"
            result.append(text)

        if self.status != Task.NEW.status:
            add_result("Task ", self, "cdbpcs_notplanned")

        # Vorgänger-Nachfolger
        if (
            self.PredecessorTaskRelationsByType[kTaskDependencyAE]
            or self.PredecessorTaskRelationsByType[kTaskDependencyEE]
        ) and (
            self.SuccessorTaskRelationsByType[kTaskDependencyAE]
            or self.SuccessorTaskRelationsByType[kTaskDependencyAA]
        ):
            for pre in (
                self.PredecessorTaskRelationsByType[kTaskDependencyAE]
                + self.PredecessorTaskRelationsByType[kTaskDependencyEE]
            ):
                add_result("Vorgänger: ", pre, "cdbpcs_delete_vnrels")

            for succ in (
                self.SuccessorTaskRelationsByType[kTaskDependencyAE]
                + self.SuccessorTaskRelationsByType[kTaskDependencyAA]
            ):
                add_result("Nachfolger: ", succ, "cdbpcs_delete_vnrels")

        # Timesheets
        result += [ts.GetDescription() for ts in self.TimeSheets]

        # Checklists
        for checklist in self.Checklists:
            handled = False

            for cl_item in checklist.ChecklistItems:
                if cl_item.SubChecklists:
                    add_result("", checklist, "cdbpcs_hassubcl")
                    handled = True
                    break  # continue with next checklist

            if (reason or not handled) and checklist.rating_id not in ["", "clear"]:
                add_result("", checklist, "cdbpcs_rated")

        result_sub = [
            subtask.check_deepdelete(reason) for subtask in self.OrderedSubTasks
        ]
        if result_sub:
            result += functools.reduce(operator.add, result_sub)

        return result

    def ask_remove_date_values(self, ctx):
        msgbox = ctx.MessageBox("cdbpcs_remove_dates_confirm", [], "remove_date_values")
        msgbox.addYesButton(1)
        msgbox.addCancelButton()

        ctx.show_message(msgbox)

    def msp_delete(self):
        # iterate on subtasks
        for subtask in self.OrderedSubTasks:
            subtask.msp_delete()

        args = {"active_integration": "OfficeLink"}
        operation(kOperationDelete, self, system_args(**args))

    def GetActivityStreamTopics(self, posting):
        """
        Activity Stream postings should be assigned
        to the project and the object itself.
        """
        return [self, self.Project]

    def notifyInBatchMode(self):
        """
        Defines when a notification of a status change will be sent.

        :return: True (Default): Notification in both use cases

                 False: Notification only in case of interaction by the user (Default in parent
                 `cdb.objects.common.WithStateChangeNotification#notifyInBatchMode)`
        :rtype: bool
        """
        return True

    def addQCArguments(self, args, ctx=None):
        args.update(
            cdb_project_id=self.cdb_project_id, task_id=self.task_id, ce_baseline_id=""
        )

    def on_cdbpcs_new_subtask_now(self, ctx):
        create_msg = cmsg.Cdbcmsg("cdbpcs_task", kOperationNew, True)
        create_msg.add_item("cdb_project_id", "cdbpcs_task", self.cdb_project_id)
        create_msg.add_item("parent_task", "cdbpcs_task", self.task_id)
        create_msg.add_item("ce_baseline_id", "cdbpcs_task", self.ce_baseline_id)
        ctx.url(create_msg.eLink_url())

    def getResponsiblePersons(self):
        if self.Subject:
            return [s.personalnummer for s in self.Subject.getPersons()]
        return []

    def check_project_role_needed(self, ctx):
        self.Project.check_project_role_needed(ctx)

    __del_counter__ = "cs.pcs.tasks.del_counter"
    __del_recalculated__ = "cs.pcs.tasks.recalculated"

    def deleted_by_msp(self, ctx=None):
        calledByOfficeLink = (
            ctx
            and hasattr(ctx, "active_integration")
            and ctx.active_integration == "OfficeLink"
        )
        return calledByOfficeLink and ctx.action == "delete"

    def pre_delete(self, ctx):
        if not self.deleted_by_msp(ctx):
            self.pre_delete_msp_inactive(ctx)
            self.prepare_substructure_for_delete(ctx)

    def post_delete(self, ctx):
        if not self.deleted_by_msp(ctx):
            self.post_delete_msp_inactive(ctx)

    def pre_delete_msp_inactive(self, ctx):
        self.checkStructureLock(ctx)
        self.checkSchedule(ctx)
        self.check_substructure_for_delete(ctx)
        sig.emit(Task, "delete_msp_inactive", "pre")(self, ctx)

    def _delete_followups_per_project(self, task_handles, ctx):
        # these are expensive, call-once-per-project followups
        # to task deletion
        def get_del_recalculated(args):
            return int(getattr(args, self.__del_recalculated__, 0))

        already_done = (
            # ue_args: set in post_delete_msp_inactive
            # sys_args: set in prepare_substructure_for_delete
            get_del_recalculated(ctx.ue_args)
            or get_del_recalculated(ctx.sys_args)
        )
        if already_done:
            return

        project_ids = {
            handle.getValue("cdb_project_id", False) for handle in task_handles
        }
        projects = Project.KeywordQuery(cdb_project_id=project_ids, ce_baseline_id="")
        for project in projects:
            project.recalculate()
            project.check_project_role_needed(ctx)

        ctx.keep(self.__del_recalculated__, 1)

    def _get_op_handles(self, ctx):
        opctx = OperationContext(ctx.operation_context_id)
        return opctx.getObjects()

    def post_delete_msp_inactive(self, ctx):
        self.updateParentTask(ctx)
        self.setTemplateOID(ctx)

        # count UE calls to determine the last one
        counter = int(getattr(ctx.ue_args, self.__del_counter__, 0)) + 1
        ctx.keep(self.__del_counter__, counter)
        handles = self._get_op_handles(ctx)

        if counter == len(handles):
            # this is the last UE call; do follow ups for projects now
            self._delete_followups_per_project(handles, ctx)

        sig.emit(Task, "delete_msp_inactive", "post")(self, ctx)

    def final_delete(self, ctx):
        if not self.deleted_by_msp(ctx):
            handles = self._get_op_handles(ctx)
            # may not have been called yet if user did not confirm
            # all deletions in the Windows client
            self._delete_followups_per_project(handles, ctx)

    def check_substructure_for_delete(self, ctx):
        dependancies = self.check_deepdelete(reason=True)
        if dependancies:
            message = "\n".join(dependancies)
            raise ue.Exception("cdbpcs_delete_deny", message)

    def prepare_substructure_for_delete(self, ctx):
        with transactions.Transaction():
            # explicitly pass ctx args in order to support task deletion
            # via officelink (when msp is set as editor)
            args = {a: ctx.sys_args[a] for a in ctx.sys_args.get_attribute_names()}
            cl_args = system_args(**args)
            args[self.__del_recalculated__] = 1
            task_args = system_args(**args)

            for task in self.OrderedSubTasks:
                for c in task.Checklists:
                    operation(kOperationDelete, c, cl_args)
                # skip recalculate (tbd by this "outer" delete operation)
                operation(kOperationDelete, task, task_args)

            # Vorgänger-Nachfolger beziehung anpassen
            for pred in self.PredecessorTaskRelationsByType.all():
                for succ in self.SuccessorTaskRelationsByType.all():
                    TaskRelation.compose(pred, succ)

    def ChangeState(self, new_state, **kwargs):
        try:
            utils.add_to_change_stack(self)
            super().ChangeState(new_state, **kwargs)
        finally:
            utils.unregister_from_change_stack(self)

    def init_status_change(self, ctx=None):
        utils.add_interactive_call(self)

    def end_status_change(self, ctx=None):
        changes = utils.remove_from_change_stack(self, ctx)
        if changes:
            self.Project.do_status_updates(changes)

    def set_act_date(self, ctx=None):
        """
        If the user selected different dates for start_time_act or
        end_time_act on status change dialog, this method would persist
        those changes for the task on which status change is performed.
        For the followup status changes, the values will be empty
        (because of batch operation) and no changes will be made in followup tasks.
        """
        changes = {}
        start_time_attr = "start_time_act"
        end_time_attr = "end_time_act"

        def _get_date_attr(attr):
            val = None
            if ctx and ctx.dialog and hasattr(ctx.dialog, attr):
                val = getattr(ctx.dialog, attr, None)
            return ensure_date(val)

        def not_today(date):
            return date != datetime.date.today()

        def is_different(date1, date2):
            return date1 != date2

        def update_changes(attr, val):
            if val:
                # update the value if it's filled and different
                if (self[attr] and is_different(self[attr], val)) or (
                    (not self[attr]) and not_today(val)
                ):  # or (not filled and not today)
                    changes[attr] = val

        start_time_act = _get_date_attr(start_time_attr)
        end_time_act = _get_date_attr(end_time_attr)

        # validate selection
        self.validate_time_act(start_time_act, end_time_act)

        update_changes(start_time_attr, start_time_act)
        update_changes(end_time_attr, end_time_act)
        if changes:
            self.Update(**changes)

    def check_auto_flags(self, ctx):
        if self.Project.msp_active:
            if self.automatic and self.auto_update_time != 1:
                ctx.set("auto_update_time", 1)
            elif not self.automatic and self.auto_update_time == 1:
                ctx.set("auto_update_time", 2)
        else:
            if self.auto_update_time == 1:
                if self.automatic == 0 and ctx.object["automatic"] == "1":
                    ctx.set("auto_update_time", 2)
                else:
                    ctx.set("automatic", 1)

    def validate_responsibility(self, ctx):
        assert_valid_project_resp(ctx)

    @classmethod
    def on_cdbpcs_calculate_forecast_now(cls, ctx):
        """
        Uses the actual start as forecast start to calculate new forecast end.
        Forecast duration (or target) is used to calculate new forecast end.
        The forecast values of already finalized tasks are not changed.

        :param ctx: context object
        :raises ue.Exception: if error occours or adjustment can not be made
        """
        failed = False
        for obj in Task._get_tasks_by_ctx_objects(ctx):
            try:
                with util.SkipAccessCheck():
                    obj._adjust_forecast_to_actual_dates()
            except Exception:
                failed = True
        if failed:
            raise ue.Exception("cdbpcs_forecast_adjustment_failed")

    def _adjust_forecast_to_actual_dates(self):
        from cs.pcs.projects.dialog_hooks import _change_start_time_plan

        if not self.auto_update_time:
            raise ue.Exception("cdbpcs_forecast_adjustment_failed")
        operation(
            kOperationModify, self, **_change_start_time_plan(self, self.start_time_act)
        )

    def _check_percentage(self, ctx=None):
        from cs.pcs.projects.dialog_hooks import check_percentage

        check_percentage(self)

    @classmethod
    def _get_tasks_by_ctx_objects(cls, ctx):
        from cs.pcs.projects.common.webdata.util import get_sql_condition

        ids = []
        for obj in ctx.objects:
            ids.append([obj.cdb_project_id, obj.task_id])
        stmt = get_sql_condition("cdbpcs_task", ["cdb_project_id", "task_id"], ids)
        in_clause = ", ".join([f"{x}" for x in cls.endStatus(False)])
        stmt += f" AND status NOT IN ({in_clause})"
        return cls.Query(stmt)

    def setRelshipFieldsReadOnly(self, ctx):
        if ctx.relationship_name == "cdbpcs_subtasks":
            ctx.set_fields_readonly(["parent_task_name", "project_name"])

    def warn_start_before_project_start(self, ctx):
        """
        Show warning message when the start/constraint date of a task
        is before the project start date.
        """
        if self.Project.auto_update_time != 1:
            return
        if "cdbpcs_date_before_project_start" in ctx.dialog.get_attribute_names():
            return

        proj_start_date = self.Project.start_time_fcast

        if not proj_start_date:
            return

        start_before_project_start = (
            self.start_time_fcast and self.start_time_fcast < proj_start_date
        )
        constraint_date_before_project_start = (
            self.constraint_date and self.constraint_date < proj_start_date
        )
        if start_before_project_start or constraint_date_before_project_start:
            if ctx.uses_webui:
                raise ue.Exception(
                    -1024, util.get_label("cdbpcs_date_before_project_start")
                )

            msgbox = ctx.MessageBox(
                "cdbpcs_date_before_project_start",
                [],
                "cdbpcs_date_before_project_start",
                ctx.MessageBox.kMsgBoxIconInformation,
            )
            msgbox.addButton(ctx.MessageBoxButton("ok", "OK"))
            ctx.show_message(msgbox)

    def init_daytime(self, ctx):
        if self.milestone and not self.automatic:
            ctx.set_mandatory(".daytime")

        if self.Project.msp_active:
            ctx.set_readonly(".mapped_daytime_value")

    def check_set_daytime_values(self, ctx):
        """
        Make sure "daytime" value is only set when allowed
        (e.g. for manually-scheduled milestones).
        If it is set, also make sure early/late flags are set accordingly.

        Also make sure early flags for milestones are always consistent
        (even thouth only ``start_is_early`` is used).
        """
        if self.milestone and not self.automatic:
            if self.daytime not in {DAYTIME_MORNING, DAYTIME_EVENING}:
                ctx.set("daytime", DAYTIME_EVENING)
                ctx.set("start_is_early", "0")

            if self.daytime == DAYTIME_MORNING:
                ctx.set("start_is_early", "1")

            if self.daytime == DAYTIME_EVENING:
                ctx.set("start_is_early", "0")
        else:
            ctx.set("daytime", DAYTIME_NOT_APPLICABLE)

        if self.milestone:
            ctx.set("end_is_early", self.start_is_early)

    def set_auto_update_time(self, ctx):
        ctx.set("mapped_auto_update_time", 1)

    event_map = {
        (("create", "copy"), "pre_mask"): (
            "checkStructureLock",
            "setDefaults",
            "checkSchedule",
            "checkParent",
            "setInitValues",
            "check_Project_State",
        ),
        (("create"), "pre_mask"): ("setRelshipFieldsReadOnly", "set_auto_update_time"),
        (("modify"), "pre_mask"): ("setInitValues"),
        (("info"), "pre_mask"): ("setInitValues"),
        (("create", "copy", "modify"), "pre_mask"): ("init_daytime"),
        (("create", "copy", "modify"), "dialogitem_change"): ("dialog_item_change"),
        (("create", "copy", "modify"), "pre"): ("check_set_daytime_values"),
        (("create"), "pre"): (
            "checkTaskId",
            "checkConstraints",
            "checkEfforts",
            "checkEffortFields",
            "checkForSubProjects",
            "checkStructureLock",
            "setObjectart",
            "checkSchedule",
            "checkParent",
            "checkProjectID",
            "setTaskID",
            "setPosition",
            "check_Project_State",
            "validate_responsibility",
        ),
        (("copy"), "pre"): (
            "checkTaskId",
            "checkConstraints",
            "checkEffortFields",
            "checkStructureLock",
            "setObjectart",
            "checkSchedule",
            "checkParent",
            "checkProjectID",
            "setTaskID",
            "setPosition",
            "check_Project_State",
            "checkEfforts",
            "recalculate_preparation",
            "validate_responsibility",
        ),
        (("modify"), "pre"): (
            "checkConstraints",
            "checkEffortFields",
            "check_auto_flags",
            "checkParent",
            "checkEfforts",
            "recalculate_preparation",
            "validate_and_update_days_act",
            "_check_percentage",
        ),
        (("create"), "post"): (
            "updateParentTask",
            "recalculate",
            "check_project_role_needed",
        ),
        (("copy"), "post"): ("updateParentTask", "check_project_role_needed"),
        (("modify"), "post"): ("recalculate", "check_project_role_needed"),
        (("delete"), "pre"): ("pre_delete"),
        (("delete"), "post"): ("post_delete"),
        (("delete"), "final"): ("final_delete"),
        (("delete_msp_inactive"), "pre"): ("pre_delete_msp_inactive"),
        (("delete_msp_inactive"), "post"): ("post_delete_msp_inactive"),
        (("cs_tasks_delegate"), "post"): ("check_project_role_needed"),
        (("wf_step"), "dialogitem_change"): ("state_dialog_item_change"),
        (("wf_step"), "pre_mask"): ("state_dialog_pre_mask"),
        (("wf_step"), "pre"): ("state_dialog_pre"),
        (("state_change"), "pre"): ("set_act_date", "init_status_change"),
        (("state_change"), "post"): ("end_status_change"),
    }


class TaskRelation(Object):
    __maps_to__ = "cdbpcs_taskrel"
    __graph_stmt__ = """
        SELECT
            succ_task_oid,
            pred_task_oid
        FROM cdbpcs_taskrel
        WHERE
            cdb_project_id = '{0}'
            AND cdb_project_id2 = '{0}'

        UNION SELECT
            task.cdb_object_id AS succ_task_oid,
            parent.cdb_object_id AS pred_task_oid
        FROM cdbpcs_task task
        JOIN cdbpcs_task parent
            ON task.parent_task = parent.task_id
            AND task.cdb_project_id = parent.cdb_project_id
        WHERE task.cdb_project_id = '{0}'
            AND task.ce_baseline_id = ''
            AND parent.ce_baseline_id = ''
    """

    @classmethod
    def GetGraph(cls, cdb_project_id):
        """
        :param cdb_project_id: Project ID to construct graph for
        :type cdb_project_id: str

        :returns: Task UUIDs indexed by their successors's UUID:
            `{"successor1": ["predecessor1", "predecessor2"]}`
        :rtype: dict

        .. note ::

            The resulting graph is not only built from explicit task
            relationships, but also respects implicit parent-child
            relationships.
            It ignores inter-project relationships.
        """
        graph = defaultdict(list)
        condition = cls.__graph_stmt__.format(sqlapi.quote(cdb_project_id))
        records = sqlapi.RecordSet2(sql=condition)

        for record in records:
            graph[record.succ_task_oid].append(record.pred_task_oid)

        return graph

    PredecessorProject = Reference_1(fProject, fTaskRelation.cdb_project_id2)
    SuccessorProject = Reference_1(fProject, fTaskRelation.cdb_project_id)
    PredecessorTask = Reference_1(
        fTask, fTaskRelation.cdb_project_id2, fTaskRelation.task_id2
    )
    SuccessorTask = Reference_1(
        fTask, fTaskRelation.cdb_project_id, fTaskRelation.task_id
    )
    RelType = Reference_1(fTaskRelationType, fTaskRelation.rel_type)

    def getLateFinish(self):
        if self.rel_type == kTaskDependencyEA and self.SuccessorTask.start_time_fcast:
            return workday.next_day(self.SuccessorTask.start_time_fcast, -1)
        if self.rel_type == kTaskDependencyEE and self.SuccessorTask.end_time_fcast:
            return self.SuccessorTask.end_time_fcast
        return None

    def getLateStart(self):
        if self.rel_type == kTaskDependencyAA and self.SuccessorTask.start_time_fcast:
            return self.SuccessorTask.start_time_fcast
        if self.rel_type == kTaskDependencyAE and self.SuccessorTask.end_time_fcast:
            return self.SuccessorTask.end_time_fcast
        return None

    def getEarlyFinish(self):
        if self.rel_type == kTaskDependencyEE and self.PredecessorTask.end_time_fcast:
            return self.PredecessorTask.end_time_fcast
        if self.rel_type == kTaskDependencyAE and self.PredecessorTask.start_time_fcast:
            return self.PredecessorTask.start_time_fcast
        return None

    def getEarlyStart(self):
        if self.rel_type == kTaskDependencyEA and self.PredecessorTask.end_time_fcast:
            return workday.next_day(self.PredecessorTask.end_time_fcast, 1)
        if self.rel_type == kTaskDependencyAA and self.PredecessorTask.start_time_fcast:
            return self.PredecessorTask.start_time_fcast
        return None

    def checkTaskConstraints(self, ctx=None):
        "raise an error if any taskrel constraints are violated"
        messages = self.PredecessorTask.getTaskRelConstraintViolations(
            self
        ) + self.SuccessorTask.getTaskRelConstraintViolations(self)
        if messages:
            raise util.ErrorMessage("just_a_replacement", "\n\n".join(messages))

    def checkRelation(self, ctx):
        if (
            self.cdb_project_id2 == self.cdb_project_id
            and self.task_id2 == self.task_id
        ):
            raise ue.Exception("cdbpcs_taskrel_same_task")
        if (
            self.SuccessorTask.is_group
            and self.rel_type not in ALLOWED_TASK_GROUP_DEPENDECIES
        ):
            raise util.ErrorMessage(
                "just_a_replacement",
                util.get_label("cdbpcs_task_group_rel_not_allowed"),
            )

        # There must not be more than one connection between two tasks.
        tr = TaskRelation.KeywordQuery(
            cdb_project_id=self.cdb_project_id2,
            task_id=self.task_id2,
            cdb_project_id2=self.cdb_project_id,
            task_id2=self.task_id,
        )
        if tr:
            raise ue.Exception("cdbpcs_taskrel_only_one")

    def setOIDs(self, ctx=None):
        obj = TaskRelation.ByKeys(**self)
        if not obj:
            return
        kwargs = {}
        if (
            obj.PredecessorProject
            and obj.pred_project_oid != obj.PredecessorProject.cdb_object_id
        ):
            kwargs["pred_project_oid"] = obj.PredecessorProject.cdb_object_id
        if (
            obj.SuccessorProject
            and obj.succ_project_oid != obj.SuccessorProject.cdb_object_id
        ):
            kwargs["succ_project_oid"] = obj.SuccessorProject.cdb_object_id
        if (
            obj.PredecessorTask
            and obj.pred_task_oid != obj.PredecessorTask.cdb_object_id
        ):
            kwargs["pred_task_oid"] = obj.PredecessorTask.cdb_object_id
        if obj.SuccessorTask and obj.succ_task_oid != obj.SuccessorTask.cdb_object_id:
            kwargs["succ_task_oid"] = obj.SuccessorTask.cdb_object_id
        if self.cross_project != int(obj.pred_project_oid != obj.succ_project_oid):
            kwargs["cross_project"] = int(obj.pred_project_oid != obj.succ_project_oid)
        if kwargs:
            obj.Update(**kwargs)

    def isViolated(self):
        return self.violation

    @classmethod
    def createRelation(cls, **kwargs):
        return operation(kOperationNew, TaskRelation, **kwargs)

    def modifyRelation(self, **kwargs):
        return operation(kOperationModify, self, **kwargs)

    @classmethod
    def copyRelations(cls, old_cdb_project_id, new_cdb_project_id):
        kwargs = {
            "cdb_project_id": new_cdb_project_id,
            "cdb_project_id2": new_cdb_project_id,
        }
        taskrelations = TaskRelation.KeywordQuery(
            cdb_project_id=old_cdb_project_id, cdb_project_id2=old_cdb_project_id
        )
        for taskrel in taskrelations:
            operation(kOperationCopy, taskrel, **kwargs)

    @classmethod
    def deleteRelations(cls, cdb_project_id):
        taskrelations = TaskRelation.KeywordQuery(
            cdb_project_id=cdb_project_id
        ) + TaskRelation.KeywordQuery(cdb_project_id2=cdb_project_id)
        for taskrel in taskrelations:
            operation(kOperationDelete, taskrel)

    @classmethod
    def compose(cls, lhs, rhs):
        if lhs.SuccessorTask != rhs.PredecessorTask:
            return None
        else:
            task = lhs.SuccessorTask
        if (
            lhs.cdb_project_id != lhs.cdb_project_id2
            or rhs.cdb_project_id != rhs.cdb_project_id2
            or lhs.cdb_project_id != rhs.cdb_project_id
        ):
            return None

        composition_type = TaskRelationType.composeTypes(lhs.rel_type, rhs.rel_type)

        if composition_type:
            if (
                composition_type != "AA" or lhs.PredecessorTask != task.ParentTask
            ) and (composition_type != "EE" or rhs.SuccessorTask != task.ParentTask):
                args = {
                    "cdb_project_id": rhs.cdb_project_id,
                    "cdb_project_id2": lhs.cdb_project_id,
                    "task_id2": lhs.task_id2,
                    "task_id": rhs.task_id,
                }
                query = TaskRelation.KeywordQuery(**args)
                if not query:
                    # Existence check does query for all possible rel_types,
                    # but for Creation we use the composed type
                    args["rel_type"] = composition_type
                    operation(kOperationNew, TaskRelation, name="", **args)

    def check_for_taskrel_cycles(self, ctx):
        if self.cdb_project_id == self.cdb_project_id2:
            cycle = Task._check_task_rel_cycles(
                self.cdb_project_id, (self.task_id2, self.task_id, self.rel_type)
            )
            cycle2 = Task._check_task_rel_special_case(
                self.cdb_project_id, (self.task_id2, self.task_id, self.rel_type)
            )
            cycle3 = Task._check_task_rel_parent_cycles(
                self.cdb_project_id, (self.task_id2, self.task_id, self.rel_type)
            )
            cycle = cycle or cycle2 or cycle3
            if cycle:
                raise AbortMessage("cdbpcs_taskrel_cycle")

    def _fill_oid_fields(self, ctx):
        dlg_fields = ctx.dialog.get_attribute_names()
        if (
            "cdb_project_id2" in dlg_fields
            and "pred_project_oid" in dlg_fields
            and ctx.dialog.cdb_project_id2
            and not ctx.dialog.pred_project_oid
        ):
            pred_project = Project.ByKeys(cdb_project_id=ctx.dialog.cdb_project_id2)
            if pred_project:
                ctx.set("pred_project_oid", pred_project.cdb_object_id)
        if (
            "cdb_project_id2" in dlg_fields
            and "task_id2" in dlg_fields
            and "pred_task_oid" in dlg_fields
            and ctx.dialog.cdb_project_id2
            and ctx.dialog.task_id2
            and not ctx.dialog.pred_task_oid
        ):
            pred_task = Task.ByKeys(
                cdb_project_id=ctx.dialog.cdb_project_id2, task_id=ctx.dialog.task_id2
            )
            if pred_task:
                ctx.set("pred_task_oid", pred_task.cdb_object_id)
        if (
            "cdb_project_id" in dlg_fields
            and "succ_project_oid" in dlg_fields
            and ctx.dialog.cdb_project_id
            and not ctx.dialog.succ_project_oid
        ):
            succ_project = Project.ByKeys(cdb_project_id=ctx.dialog.cdb_project_id)
            if succ_project:
                ctx.set("succ_project_oid", succ_project.cdb_object_id)
        if (
            "cdb_project_id" in dlg_fields
            and "task_id" in dlg_fields
            and "succ_task_oid" in dlg_fields
            and ctx.dialog.cdb_project_id
            and ctx.dialog.task_id
            and not ctx.dialog.succ_task_oid
        ):
            succ_task = Task.ByKeys(
                cdb_project_id=ctx.dialog.cdb_project_id, task_id=ctx.dialog.task_id
            )
            if succ_task:
                ctx.set("succ_task_oid", succ_task.cdb_object_id)

    def checkStructureLock(self, ctx=None):
        if self.cdb_project_id and self.cdb_project_id == self.cdb_project_id2:
            self.PredecessorProject.checkStructureLock(ctx=ctx)

    def adjustSuccessorStatus(self, ctx):
        if ctx.error:
            return
        self.PredecessorTask.adjustSuccessorStatus()

    def recalculate(self, ctx=None):
        if ctx.action in ["create", "delete"]:
            changes = Task.MakeChangeControlAttributes()
            self.SuccessorTask.Update(**changes)
            self.PredecessorTask.Update(**changes)

        if self.cdb_project_id == self.cdb_project_id2:
            # update violation flag of relationship between tasks in one project
            # (is part of recalculation)
            changes = {}
            cca = Project.MakeChangeControlAttributes()
            changes.update(cdb_mdate=cca["cdb_mdate"])
            changes.update(cdb_mpersno=cca["cdb_mpersno"])
            self.SuccessorProject.Update(**changes)
            self.SuccessorProject.recalculate()

    def set_violation_cross_project(self, ctx):
        # update violation flag of relationship between tasks in two projects
        # (don't recalculate, just update the flag)
        if self.cdb_project_id != self.cdb_project_id2:
            from cs.pcs.scheduling.relships import calculate_relship_gap

            gap = calculate_relship_gap(
                self.SuccessorProject.calendar_profile_id,
                self.PredecessorTask,
                self.SuccessorTask,
                self.rel_type,
            )
            ctx.set("violation", (self.minimal_gap or 0) > gap)

    NUMBER_OF_PROJECTS_FOR_SETTING_TASK_SELECTION_READONLY = 50
    _ATTRIBUTES_FOR_TASK_SELECTION_READONLY = {
        "cdb_project_id": "task_id",
        "cdb_project_id2": "task_id2",
    }

    @property
    def is_task_selection_enabled(self):
        return (
            len(Project.KeywordQuery(ce_baseline_id=""))
            > self.NUMBER_OF_PROJECTS_FOR_SETTING_TASK_SELECTION_READONLY
        )

    def set_task_selection_readonly(self, ctx):
        if not self.is_task_selection_enabled:
            return
        for attr in [
            attr
            for attr in self._ATTRIBUTES_FOR_TASK_SELECTION_READONLY.values()
            if not getattr(self, attr, False)
        ]:
            ctx.set_fields_readonly([attr])

    def set_task_selection(self, ctx):
        if not self.is_task_selection_enabled:
            return
        if ctx.changed_item in self._ATTRIBUTES_FOR_TASK_SELECTION_READONLY:
            if getattr(self, ctx.changed_item, None):
                ctx.set_fields_writeable(
                    [self._ATTRIBUTES_FOR_TASK_SELECTION_READONLY[ctx.changed_item]]
                )
            else:
                ctx.set_fields_readonly(
                    [self._ATTRIBUTES_FOR_TASK_SELECTION_READONLY[ctx.changed_item]]
                )

    event_map = {
        (("create", "copy"), "pre_mask"): (
            "checkStructureLock",
            "set_task_selection_readonly",
        ),
        (("create", "copy"), "pre"): (
            "checkRelation",
            "checkStructureLock",
            "check_for_taskrel_cycles",
            "checkTaskConstraints",
        ),
        (("modify"), "pre"): ("checkRelation"),
        (("delete"), "pre"): ("checkStructureLock"),
        (("create", "copy"), "post"): (
            "setOIDs",
            "recalculate",
            "adjustSuccessorStatus",
        ),
        (("delete"), "post"): ("recalculate", "adjustSuccessorStatus"),
        (("modify"), "post"): "recalculate",
        (("create", "copy", "query", "requery"), "pre_mask"): "_fill_oid_fields",
        (("create", "copy"), "dialogitem_change"): "set_task_selection",
        (("create", "copy", "modify"), "pre"): "set_violation_cross_project",
    }


class TaskRelationType(Object):
    __maps_to__ = "cdbpcs_tr_types"
    __classname__ = "cdbpcs_tr_types"

    @classmethod
    def getTypeLabels(cls):
        return {
            kTaskDependencyAA: util.get_label("web.timeschedule.taskrel-AA"),
            kTaskDependencyAE: util.get_label("web.timeschedule.taskrel-AE"),
            kTaskDependencyEA: util.get_label("web.timeschedule.taskrel-EA"),
            kTaskDependencyEE: util.get_label("web.timeschedule.taskrel-EE"),
        }

    @classmethod
    def composeTypes(cls, type1, type2):
        if type1[1] + type2[0] == kTaskDependencyEA:
            return None
        else:
            return type1[0] + type2[1]


class TaskCategory(Object):
    __maps_to__ = "cdbpcs_task_cat"


class CatalogPCSTeamMemberData(gui.CDBCatalogContent):
    def __init__(self, cdb_project_id, catalog):
        tabdefname = catalog.getTabularDataDefName()
        self.cdef = catalog.getClassDefSearchedOn()
        if self.cdef:
            tabdef = self.cdef.getProjection(tabdefname, True)
        else:
            tabdef = tabdefname

        gui.CDBCatalogContent.__init__(self, tabdef)
        self.cdb_project_id = cdb_project_id
        self.data = None
        self.personalnummer = None

    def getSQLCondition(self, *args):
        # TODO: structure browser should also be adjusted to filter persons with active_account=1
        condition = "is_resource=1 and active_account='1' and visibility_flag=1"
        if self.personalnummer:
            condition += f" AND personalnummer LIKE '{self.personalnummer}'".replace(
                "*", "%"
            )
        if self.cdb_project_id:
            condition += (
                " AND personalnummer IN (SELECT cdb_person_id FROM cdbpcs_team"
                f" WHERE cdb_project_id='{self.cdb_project_id}')"
            )
        return condition

    def _initData(self, refresh=False):
        if not self.data or refresh:
            condition = self.getSQLCondition()
            self.data = sqlapi.RecordSet2("angestellter", f"{condition}")

    def onSearchChanged(self):
        args = self.getSearchArgs()
        self.cdb_project_id = None
        self.personalnummer = None
        for argn in args:
            if argn.name == "personalnummer":
                self.personalnummer = argn.value
        self._initData(True)

    def refresh(self):
        self._initData(True)

    def getNumberOfRows(self):
        self._initData()
        return len(self.data)

    def getRowObject(self, row):
        if not self.cdef:
            return gui.CDBCatalogContent.getRowObject(self, row)
        else:
            self._initData()
            keys = mom.SimpleArgumentList()
            for keyname in self.cdef.getKeyNames():
                keys.append(mom.SimpleArgument(keyname, self.data[row][keyname]))
            return mom.CDBObjectHandle(self.cdef, keys, False, True)


class CatalogPCSTeamMember(gui.CDBCatalog):
    def __init__(self):
        gui.CDBCatalog.__init__(self)

    def init(self):
        # if the project is known, we fill the catalog on our own
        cdb_project_id = ""
        try:
            cdb_project_id = self.getInvokingDlgValue("cdb_project_id")

        except Exception:
            logging.exception("getInvokingDlgValue failed")

        if cdb_project_id:
            self.setResultData(CatalogPCSTeamMemberData(cdb_project_id, self))


class AbortMessage(ue.Exception):
    pass


class TaskConstraint(Object):
    __maps_to__ = "cdbpcs_task_constraint"
    __classname__ = "cdbpcs_task_constraint"


@classbody
class Action:

    Task = Reference_1(fTask, Action.cdb_project_id, Action.task_id)


class DaytimeOptions(Object):
    __maps_to__ = "cdbpcs_daytime_options"
    __classname__ = "cdbpcs_daytime_options"
