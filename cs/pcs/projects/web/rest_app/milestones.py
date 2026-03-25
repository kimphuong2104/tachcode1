#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


import datetime
import logging

import isodate
from cdb import auth, sqlapi
from cdb.platform.olc import StatusInfo
from cs.platform.web import JsonAPI
from cs.platform.web.rest.support import get_restlink
from cs.platform.web.root import Internal, get_internal
from webob.exc import HTTPBadRequest

from cs.pcs.projects.common.web import get_url_patterns
from cs.pcs.projects.common.webdata.util import get_rest_key, get_sql_condition
from cs.pcs.projects.tasks import Task
from cs.pcs.projects.web.rest_app import _get_key_values

APP = "cs.pcs.projects.milestones"


def get_app_url_patterns(request):
    milestone_app = MilestonesApp.get_app(request)
    models = [
        ("milestones", MilestonesModel, []),
    ]
    return get_url_patterns(request, milestone_app, models)


def ensure_iso_date(datevalue):
    """
    :param datevalue: Date to convert to ISO 8601 string.
    :type datevalue: datetime.datetime or str

    :returns: Date represented as ISO 8601 string (``None`` if input is falsy)
    :rtype: str

    :raises ValueError: If ``datevalue`` is not empty and...
        - (sqlite only) ...not an ISO 8601 string
        - (other DBMSes) ...no ``datetime.datetime`` object
    """
    if not datevalue:
        return None

    if sqlapi.SQLdbms() == sqlapi.DBMS_SQLITE:
        # sqlite: aggregated date fields are returned as ISO 8601 strings
        try:
            return isodate.parse_date(datevalue).isoformat()
        except (isodate.ISO8601Error, TypeError) as exc:
            raise ValueError(
                f"not an ISO 8601 date string: {datevalue} ({type(datevalue)})"
            ) from exc
    else:
        if not isinstance(datevalue, datetime.datetime):
            raise ValueError(f"not a datetime object: {datevalue} ({type(datevalue)})")

        # other DBMSes: aggregated date fields are returnes as datetime objs
        return datevalue.date().isoformat()


class MilestonesApp(JsonAPI):
    @classmethod
    def get_app(cls, request):
        "Try to look up /internal/cs.pcs.projects.milestones"
        return get_internal(request).child(APP)


@Internal.mount(app=MilestonesApp, path=APP)
def _mount_app():
    return MilestonesApp()


class MilestonesModel:
    def getTaskStatusInfo(self, task):
        status = task["status"]
        label = ""
        color = None
        if status is not None:
            info = StatusInfo("cdbpcs_task", status)
            label = info.getLabel()
            color = info.getCSSColor()

        return {
            "status": status,
            "label": label,
            "color": color,
        }

    def getResponsibleThumbnail(self, task):
        thumbnail_link = ""
        responsible = task.Subject
        if responsible:
            thumbnail_link = get_restlink(responsible.GetThumbnailFile())

        return thumbnail_link

    def _getTaskValues(self, task):
        """
        :param task: Task Object to extract values for
        :type task: Task

        :returns: extracted values of given task object
        :rtype: dict
        """
        whitelisted_attributes = [
            "task_name",
            "mapped_subject_name",
            "joined_status_name",
        ]
        return_value = {
            attribute: task[attribute] for attribute in whitelisted_attributes
        }
        return_value["status"] = self.getTaskStatusInfo(task)
        return_value["resp_thumbnail"] = self.getResponsibleThumbnail(task)
        return_value["@id"] = get_restlink(task)
        return_value["end_time_fcast"] = task.end_time_fcast.strftime("%Y-%m-%d")
        return return_value

    def get_milestones(self, request):
        """
        :param request: Request with project ids to get milestone data for
        :type request: Request

        :returns: Milestones Data indexed by Project Ids
                    {pid: {data: [{milestone}, ...]}, ...}
                    see _get_milestones.
                    Returns empty dict if access rights are not granted.
        :rtype: json

        :raises webob.exc.HTTPBadRequest: if ``request``
            does not include a JSON payload

        .. note ::

            This is intended to be used with an HTTP POST request for the
            simplicity of JSON over URL query parameters.
        """
        try:
            rest_keys = request.json["projects"]
        except KeyError as exc:
            logging.exception("get_milestones, request: %s", request)
            raise HTTPBadRequest() from exc

        key_values = _get_key_values(rest_keys)
        project_keynames = ["cdb_project_id", "ce_baseline_id"]
        projects_condition = get_sql_condition(
            "cdbpcs_project",
            project_keynames,
            key_values,
        )
        # since we need to access mapped and joined attributes,
        # we request real objects rather than records
        task_condition = f"{projects_condition} AND milestone = 1"
        tasks = Task.Query(task_condition, access="read")

        return_json = {}

        for rest_key in rest_keys:
            return_json[rest_key] = {"data": [], "tasks_date_range": {}}

        # fail early if no tasks were retrieved and return an empty result
        if not tasks:
            logging.warning(
                "get_milestones: Either '%s' have no read access on"
                "the tasks of projects '%s' or the tasks do not exist.",
                auth.persno,
                key_values,
            )
            return return_json

        # also query for min and max limits for each project
        proj_task_min_max = sqlapi.RecordSet2(
            "cdbpcs_task",
            projects_condition,
            columns=[
                "MIN(end_time_fcast) AS min_end",
                "MAX(end_time_fcast) AS max_end",
            ]
            + project_keynames,
            addtl=f"GROUP BY {', '.join(project_keynames)}",
        )

        for task in tasks:
            # only count the ones having an end date
            if task.end_time_fcast:
                rest_key = get_rest_key(task, project_keynames)
                return_json[rest_key]["data"].append(self._getTaskValues(task))

        for min_max in proj_task_min_max:
            rest_key = get_rest_key(min_max, project_keynames)
            return_json[rest_key]["tasks_date_range"] = {
                "min": ensure_iso_date(min_max.min_end),
                "max": ensure_iso_date(min_max.max_end),
            }

        return return_json


@MilestonesApp.path(path="", model=MilestonesModel)
def get_milestones_model(request):
    return MilestonesModel()


@MilestonesApp.json(model=MilestonesModel, request_method="POST")
def get_milestones_for_projects(model, request):
    return model.get_milestones(request)
