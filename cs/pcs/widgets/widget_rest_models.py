#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
cs.pcs.projects.widgets.widget_rest_models
==========================================================

Model classes for the widget REST application of
``cs.pcs.widgets``.

.. autoclass :: RatingModel
    :members: get_rating

.. autoclass :: InTimeModel
    :members: get_in_time

.. autoclass :: InBudgetModel
    :members: get_in_budget

.. autoclass :: RemainingTimeModel
    :members: get_remaining_time

.. autoclass :: UnassignedRolesModel
    :members: get_unassigned_roles_and_tasks
"""

import datetime
import logging

import webob
from cdb import ElementsError, auth, constants, i18n, sqlapi, util
from cdb.objects.operations import operation
from cdb.platform import gui
from cs.platform.web import JsonAPI
from cs.platform.web.rest.support import values_from_rest_key
from cs.platform.web.root import Internal, get_internal

from cs.pcs.helpers import get_and_check_object
from cs.pcs.projects import Project
from cs.pcs.projects.calendar import getWorkdays
from cs.pcs.projects.common.lists.list import ListConfig
from cs.pcs.widgets.notes_content import NotesContent

NOTES_TXT = "cdbpcs_notes_content_txt"


def _serialize_date(date):
    if date:
        return date.isoformat()
    return None


class InternalWidgetApp(JsonAPI):
    PATH = "cs-pcs-widgets"

    @classmethod
    def get_app(cls, request):
        return get_internal(request).child(cls.PATH)


@Internal.mount(app=InternalWidgetApp, path=InternalWidgetApp.PATH)
def _():
    return InternalWidgetApp()


class ProjectModelBase:
    """
    Base class for project widget models.
    """

    def __init__(self, rest_key):
        """
        :raises webob.exc.HTTPNotFound: if project cannot be instantiated or
            read access is denied for logged-in user.
        """
        # NOTE: Widget are only used for non-baseline projects
        project = None
        cdb_project_id = None
        keys = None
        if rest_key:
            keys = values_from_rest_key(rest_key)
        if keys and len(keys) == len(Project.GetTablePKeys()):
            cdb_project_id = keys[0]
            ce_baseline_id = keys[1]
            kwargs = {
                "cdb_project_id": cdb_project_id,
                "ce_baseline_id": ce_baseline_id,
            }
            if ce_baseline_id == "":
                project = get_and_check_object(Project, "read", **kwargs)
            else:
                logging.error(
                    "Widget Models are only allowed to be instantiated for non-baseline projects."
                )
        if project is None:
            raise webob.exc.HTTPNotFound()

        self.cdb_project_id = cdb_project_id
        self.rest_key = rest_key
        self.project = project


class RatingModel(ProjectModelBase):
    def get_rating(self):
        """
        :returns: Dictionary with two Strings, project rating and
                  project rating_descr
        :rtype: dict
        """
        rating = self.project.rating
        rating_descr = self.project.rating_descr
        return {"rating": rating, "rating_descr": rating_descr}


@InternalWidgetApp.path(path="rating/{rest_key}", model=RatingModel)
def get_rating_model(request, rest_key):
    return RatingModel(rest_key)


@InternalWidgetApp.json(model=RatingModel)
def get_rating(model, request):
    return model.get_rating()


class InTimeModel(ProjectModelBase):
    def get_in_time(self):
        """
        :returns: Dictionary with
            Float spi, the schedule performance index according to EVA
                analysis,
            Float sv, the schedule variance according to EVA analysis,
            Bool projectHasNoTask indicating if the project has no tasks and
            dict timeSchedules, holding for any valid and/or new timeSchedules
                of the project a dict with relative URL, name and status
                with the cdb_object_id as key
                {id: {"url": url, "name": name, "status": status}, ...}
        :rtype: dict
        """
        timeSchedules = {}
        # TimeScheduleStatus: New = 0L, Valid = 100L Invalid = 200L
        validAndNewTimeSchedules = [
            ts
            for ts in self.project.PrimaryTimeSchedule
            if (
                (ts.status == 100 and ts.cdb_status_txt == "Valid")
                or (ts.status == 0 and ts.cdb_status_txt == "New")
            )
        ]

        for ts in validAndNewTimeSchedules:
            timeScheduleURL = ts.getProjectPlanURL()
            timeScheduleName = ts.name
            timeScheduleStatus = ts.cdb_status_txt
            timeSchedules.update({timeScheduleURL: {}})
            timeSchedules[timeScheduleURL].update(
                {"name": timeScheduleName, "status": timeScheduleStatus}
            )

        if len(self.project.Tasks) > 0:
            # We are only interested in the time efficiency value spi
            (ev, pv) = self.project.get_ev_pv_for_project()
            _, _, sv, spi, _, _, _ = self.project.get_schedule_state(ev, pv)
            return {
                "efficiency": spi,
                "variance": sv,
                "projectHasNoTask": False,
                "timeSchedules": timeSchedules,
            }
        else:
            return {"projectHasNoTask": True, "timeSchedules": timeSchedules}


@InternalWidgetApp.path(path="in_time/{rest_key}", model=InTimeModel)
def get_in_time_model(request, rest_key):
    return InTimeModel(rest_key)


@InternalWidgetApp.json(model=InTimeModel)
def get_in_time(model, request):
    return model.get_in_time()


class InBudgetModel(ProjectModelBase):
    def get_in_budget(self):
        """
        :returns: Dictionary with two floats, cpi and cv,
                  and Bool projectHasNoTask, indicating if
                  the project has no tasks
        :rtype: dict
        """
        if len(self.project.Tasks) > 0:
            # We are only interested in the cost variance cv
            # and cost performance index cpi (== efficiency)
            (ev, _) = self.project.get_ev_pv_for_project()
            _, _, cv, cpi, _, _, _ = self.project.get_cost_state(ev)
            return {"efficiency": cpi, "variance": cv, "projectHasNoTask": False}
        else:
            return {"projectHasNoTask": True}


@InternalWidgetApp.path(path="in_budget/{rest_key}", model=InBudgetModel)
def get_in_budget_model(request, rest_key):
    return InBudgetModel(rest_key)


@InternalWidgetApp.json(model=InBudgetModel)
def get_in_budget(model, request):
    return model.get_in_budget()


class RemainingTimeModel(ProjectModelBase):
    def get_remaining_time(self):
        """
        :returns: Dictionary with
            String status, that is in
                ["Execution", "Finished", "NotExecNorFin"],
            String plannedStart, the forecast planned start date
                of the project in isoformat,
            String plannedEnd, the forecast planned end date
                of the project in isoformat and
            Bool projectHasNoDatesSet, if the project has either
                Start or End date not set
        :rtype: dict
        """
        if self.project.status == self.project.EXECUTION.status:
            status = "Execution"
        elif self.project.status == self.project.COMPLETED.status:
            status = "Finished"
        else:
            status = "NotExecNorFin"

        plannedStart = self.project.start_time_fcast
        plannedEnd = self.project.end_time_fcast

        missing_dates = not (plannedStart and plannedEnd)

        if missing_dates:
            remainingWorkDays = None
            valid_until = None
        else:
            today = datetime.date.today()

            valid_until = self.project.CalendarProfile.valid_until
            project_id = self.project.cdb_project_id
            if today > valid_until:
                remainingWorkDays = getWorkdays(project_id, valid_until, plannedEnd)
            else:
                remainingWorkDays = getWorkdays(project_id, today, plannedEnd)

        return {
            "status": status,
            "plannedStart": _serialize_date(plannedStart),
            "plannedEnd": _serialize_date(plannedEnd),
            "projectHasNoDatesSet": missing_dates,
            "remainingWorkDays": remainingWorkDays,
            "endDateCalendarProfile": _serialize_date(valid_until),
        }


@InternalWidgetApp.path(path="remaining_time/{rest_key}", model=RemainingTimeModel)
def get_remaining_time_model(request, rest_key):
    return RemainingTimeModel(rest_key)


@InternalWidgetApp.json(model=RemainingTimeModel)
def get_remaining_time(model, request):
    return model.get_remaining_time()


class UnassignedRolesModel(ProjectModelBase):
    def get_unassigned_roles_and_tasks(self):
        """
        :returns: Dictionary with
            String status, that is in ["success", "info", "danger"],
            Number status_yellow, amount of new task,
                assigned to a project role without team member,
            Number status_red, total amount of planned, evaluation, execution, review or waitingfor tasks,
                assigned to a project role without team member,
            Number roles, amount of roles, that are not assigned
                to a project member
            Dict rolesAndTasks, contains for each role without
                Team member assigned all assigned planned tasks
                and tasks in execution.
                {role:{planned:[...], execution:[...]}, role: ...}
        :rtype: dict
        """
        status_yellow = 0
        status_red = 0
        other_RolesAndTasks = {
            "cdbpcs_task": 0,
            "cdbpcs_issue": 0,
            "cdbpcs_checklist": 0,
            "cdbpcs_cl_item": 0,
        }
        new_RolesAndTasks = {
            "cdbpcs_task": 0,
            "cdbpcs_issue": 0,
            "cdbpcs_checklist": 0,
            "cdbpcs_cl_item": 0,
        }
        otherRolesID = []
        newRolesID = []
        projectRoles = self.project.Roles
        # get all project roles, that are not assigned to a team member
        for role in projectRoles:
            roleAssignedNoMember = self.getRoleAssignedNoMember(role)

            # for each role without team member get all tasks,
            # that are assigned to it
            for role_id, task_type, role_tasks in roleAssignedNoMember:
                otherRolesAndTasks, newRolesAndTasks = self.getTasksInfo(
                    task_type, role_tasks
                )

                other_RolesAndTasks[task_type] += otherRolesAndTasks
                if otherRolesAndTasks > 0:
                    otherRolesID.append(role_id)
                new_RolesAndTasks[task_type] += newRolesAndTasks
                if newRolesAndTasks > 0:
                    newRolesID.append(role_id)

                status_yellow += newRolesAndTasks
                status_red += otherRolesAndTasks
        new_RolesAndTasks["roles_id"] = list(set(newRolesID))
        new_RolesAndTasks["Total_tasks"] = status_yellow
        other_RolesAndTasks["roles_id"] = list(set(otherRolesID))
        other_RolesAndTasks["Total_tasks"] = status_red
        totalNumberOfTasks = status_yellow + status_red

        status = self.getStatus(status_red, status_yellow)
        # get number of roles not assigned a team member
        unassignedRoleCount = len(
            set(other_RolesAndTasks["roles_id"] + new_RolesAndTasks["roles_id"])
        )

        return {
            "status": status,
            "totalNumberOfTasks": totalNumberOfTasks,
            "totalUnassignedRoles": unassignedRoleCount,
            "otherRolesAndTasks": other_RolesAndTasks,
            "newRolesAndTasks": new_RolesAndTasks,
        }

    def getTasksInfo(self, task_type, role_tasks):
        """
        :returns: Number task_type, as total number of other tasks,
                Number new_tasks, as total number of new tasks
        :rtype: int
        """
        new_tasks = 0
        other_tasks = 0
        for task in role_tasks:
            # if task is new
            if task.status == task.NEW.status:
                new_tasks += 1
            if task_type == "cdbpcs_checklist":
                if task.status == task.EVALUATION.status:
                    other_tasks += 1
            elif task_type == "cdbpcs_cl_item":
                if task.status == task.READY.status:
                    other_tasks += 1
            elif task_type == "cdbpcs_issue":
                if task.status in [
                    task.EXECUTION.status,
                    task.EVALUATION.status,
                    task.REVIEW.status,
                    task.WAITINGFOR.status,
                ]:
                    other_tasks += 1
            elif task_type == "cdbpcs_task":
                if task.status in [task.EXECUTION.status, task.READY.status]:
                    other_tasks += 1
        return other_tasks, new_tasks

    def getRoleAssignedNoMember(self, role):
        """
        :returns: list roleAssignedNoMember, as list of all tasks which
            are not assigned to any member,
        :rtype: list
        """
        roleAssignedNoMember = []
        # if role has at least one task
        if len(role.Owners) == 0:
            roleAssignedNoMember.append((role.role_id, "cdbpcs_task", role.Tasks))
            roleAssignedNoMember.append((role.role_id, "cdbpcs_issue", role.Issues))
            roleAssignedNoMember.append(
                (role.role_id, "cdbpcs_checklist", role.Checklists)
            )
            roleAssignedNoMember.append(
                (role.role_id, "cdbpcs_cl_item", role.ChecklistItems)
            )
        return roleAssignedNoMember

    def getStatus(self, status_red, status_yellow):
        """
        :returns: string status, as string of status
            danger if tile have to be red
            info if tile have o be yellow
            success if tyle have to be green
        :rtype: string
        """
        if status_red > 0:
            status = "danger"
        elif status_yellow > 0:
            status = "info"
        else:
            status = "success"
        return status


@InternalWidgetApp.path(
    path="project_Unassigned/{rest_key}", model=UnassignedRolesModel
)
def get_unassigned_roles_model(request, rest_key):
    return UnassignedRolesModel(rest_key)


@InternalWidgetApp.json(model=UnassignedRolesModel)
def get_unassigned_roles_and_tasks(model, request):
    return model.get_unassigned_roles_and_tasks()


class ProjectNotesModel(ProjectModelBase):
    def __init__(self, rest_key, cdb_object_id):
        """
        :raises webob.exc.HTTPNotFound: if project or notes_content
        cannot be instantiated or read access is denied for logged-in user.
        """
        super().__init__(rest_key)
        self.cdb_object_id = cdb_object_id
        self.notes_content = NotesContent.ByKeys(cdb_config_id=self.cdb_object_id)
        # Note: If theres is no self.notes_content, one is created
        # during saving, so only check for read access here
        if self.notes_content and not self.notes_content.CheckAccess("read"):
            raise webob.exc.HTTPNotFound()

    def get_notes(self):
        """
        :returns: Dictionary with
            String content, the stringified JSON content of the editor and
            Bool isAllowedToModify, for if the current user is allowed to
                modify the editor's content
        :rtype: dict
        """
        if not self.notes_content:
            # if no project notes in given language exist, default to english
            default_en_content = util.PersonalSettings().getValueOrDefaultForUser(
                "cs.pcs.widgets.project_notes_default_txt_en",
                "",
                auth.persno,
                "",  # if also no en default exists default to empty
            )
            # return default content in login language of user
            content = util.PersonalSettings().getValueOrDefaultForUser(
                f"cs.pcs.widgets.project_notes_default_txt_{i18n.default()}",
                "",
                auth.persno,
                default_en_content,
            )
        else:
            content = self.notes_content.GetText(NOTES_TXT)
        # Only the project leader is allowed to modify the
        # Project Note Content. Check access by checking the save right
        # of the project
        isAllowedToModify = self.project.CheckAccess("save")
        return {"content": content, "isAllowedToModify": isAllowedToModify}

    def save_notes(self, data):
        """
        Saves data (stringified json) as the cdbpcs_notes_content_txt Project
        attribute.
        Raises Error, if either the user is not allowed to save the content
        or if the saving fails.
        """
        # check if the current user is allowed to save content
        if not (self.project and self.project.CheckAccess("save")):
            raise webob.exc.HTTPNotFound()

        # if there is no project_notes_content, create one
        if not (self.notes_content):
            self.notes_content = NotesContent.Create(cdb_config_id=self.cdb_object_id)

        try:
            vals = {
                NOTES_TXT: data,
            }
            operation(constants.kOperationModify, self.notes_content, **vals)
        except ElementsError as error:
            raise webob.exc.HTTPBadRequeststr(error) from error
        except AttributeError as exc:
            raise webob.exc.HTTPUnprocessableEntity(
                gui.Message.GetMessage("cdbpcs_saving_notes_failed")
            ) from exc


@InternalWidgetApp.path(
    path="project_notes/{rest_key}/{cdb_object_id}", model=ProjectNotesModel
)
def get_project_notes_model(request, rest_key, cdb_object_id):
    return ProjectNotesModel(rest_key, cdb_object_id)


@InternalWidgetApp.json(model=ProjectNotesModel)
def get_project_notes(model, request):
    return model.get_notes()


@InternalWidgetApp.json(model=ProjectNotesModel, request_method="POST")
def save_project_notes(model, request):
    # test/check if key is there, except raise exception
    return model.save_notes(request.json)


class ListModel(ProjectModelBase):
    def __init__(self, rest_key, list_config_name):
        """
        :raises webob.exc.HTTPNotFound: if project or list_config cannot be
        instantiated or read access is denied for logged-in user.
        """
        super().__init__(rest_key)
        self.list_config_name = list_config_name

        try:
            self.list_config = ListConfig.Query(
                f"name = '{sqlapi.quote(self.list_config_name)}'",
                access="read",
            )[0]
        except IndexError:
            logging.error(
                "ListModel - user '%s' has no read access on list config '%s'"
                " or the list config does not exists.",
                auth.persno,
                self.list_config_name,
            )
            self.list_config = None

    def get_JSON(self, request):
        if not self.list_config:
            # return an empty list result
            return {
                "title": util.get_label("web.cs-pcs-widgets.list_widget_error_title"),
                "items": [],
                "displayConfigs": {},
                "configError": util.get_label(
                    "cs.pcs.projects.common.lists.list_access_error"
                ).format(self.list_config_name),
            }
        return self.list_config.generateListJSON(request, self.rest_key)


@InternalWidgetApp.path(
    path="list_widget/{rest_key}/{list_config_name}", model=ListModel
)
def get_list_model(request, rest_key, list_config_name):
    return ListModel(rest_key, list_config_name)


@InternalWidgetApp.json(model=ListModel)
def get_JSON(model, request):
    return model.get_JSON(request)
