# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import os

from cdb import auth, misc, sig, sqlapi
from cdb.tools import getObjectByName

from cs.pcs.projects.project_structure.query_patterns import get_query_pattern
from cs.pcs.projects.project_structure.util import resolve_query
from cs.pcs.timeschedule.web.baseline_helpers import (
    get_baselined_task,
    get_project,
    get_requested_baseline,
    merge_with_baseline_task,
)
from cs.pcs.timeschedule.web.models.helpers import get_oid_query_str
from cs.pcs.timeschedule.web.models.structure_view import TimeScheduleProjectView
from cs.pcs.timeschedule.web.plugins import GET_TABLE_DATA_PLUGINS, TimeSchedulePlugin

# It is assumed, that the life cycle of status never changes
EXECUTION_STATUS = 50
NEW_STATUS = 0
READY_STATUS = 20
DISCARDED_STATUS = 180


def load_query_pattern(fname):
    """
    :param fname: The filename relative to this file's path.
    :type fname: unicode

    :returns: Contents of the file `fname`.

    :raises RuntimeError: if `fname` tries to escape this file's path.
    :raises: if `fname` does not exist or is not readable.
    """
    base = os.path.abspath(os.path.dirname(__file__))
    fpath = misc.jail_filename(base, fname)

    with open(fpath, "r", encoding="utf8") as sqlf:
        return sqlf.read()


class ProjectPlugin(TimeSchedulePlugin):
    table_name = "cdbpcs_project"
    classname = "cdbpcs_project"
    catalog_name = "cdbpcs_projects_uuid"
    allow_pinning = True
    olc_attr = "cdb_objektart"
    description_pattern = "{} {}"
    description_attrs = (
        "cdb_object_id",
        "psp_code",
        "cdb_project_id",
        "project_name",
        "ce_baseline_id",
    )
    calculation_attrs = (
        "start_time_fcast",
        "end_time_fcast",
        "auto_update_time",
        "percent_complet",
        "start_time_plan",
        "end_time_plan",
        "status",
    )
    subject_id_attr = "project_manager"

    @classmethod
    def GetDescription(cls, record):
        return cls.description_pattern.format(
            record.psp_code or record.cdb_project_id,
            record.project_name,
        )

    @classmethod
    def GetRequiredFields(cls):
        return set.union(
            set([cls.olc_attr, cls.status_attr]),
            set(cls.description_attrs),
            set(cls.calculation_attrs),
            set([cls.subject_id_attr]),
        )

    @classmethod
    def ResolveStructure(cls, root_oid, request):
        """
        :param root_oid: The `cdb_object_id` of the project to resolve.
        :type root_oid: str

        :returns: Resolved structure entries including level information.
        :rtype: list of `cs.pcs.projects.project_structure.util.PCS_LEVEL`
        """
        view = TimeScheduleProjectView(root_oid, request)
        return view.resolve()

    @classmethod
    def GetResponsible(cls, record):
        return {
            "subject_id": record[cls.subject_id_attr],
            "subject_type": "Person",
        }

    @classmethod
    def GetClassReadOnlyFields(cls):
        """
        Returns list of project-specific fields  that are always read only.

        Note:
            This method and ProjectPlugin.GetObjectReadOnlyFields together
            are a redundant implementation of
            cs.pcs.projects.Project.getReadOnlyFields with
            action='modify' and Avoid_check=True
        """
        fqpyname = sqlapi.RecordSet2(
            "switch_tabelle", f"classname='{cls.classname}'", ["fqpyname"]
        )[0].fqpyname
        return getObjectByName(fqpyname).class_specific_read_only_fields

    @classmethod
    def GetObjectReadOnlyFields(cls, oids):
        """
        Returns mapping of given project oids
        to list of object-specific fields that are always read only.

        Note:
            This method and ProjectPlugin.GetClassReadOnlyFields together
            are a redundant implementation of
            cs.pcs.projects.Project.getReadOnlyFields with
            action='modify' and Avoid_check=True
        """
        if len(oids) == 0:
            return {}

        records = sqlapi.RecordSet2(
            cls.table_name,
            get_oid_query_str(oids),
            access="read",
        )
        pids = [entry.cdb_project_id for entry in records]
        # determine which projects have timesheets
        pids_with_timesheet = [
            entry.cdb_project_id
            for entry in sqlapi.RecordSet2(
                "cdbpcs_time_sheet",
                get_oid_query_str(pids, attr="cdb_project_id"),
                ["cdb_project_id"],
            )
        ]

        # get object specific readOnly Fields by record
        readOnlyByOID = {}
        for record in records:
            read_only = ["template"]
            if record.status != EXECUTION_STATUS:
                read_only.append("percent_complet")
            if record.status in [NEW_STATUS, DISCARDED_STATUS]:
                read_only += ["start_time_act", "end_time_act"]
            elif record.status == EXECUTION_STATUS:
                read_only.append("end_time_act")
            if record.is_group:
                read_only += [
                    "percent_complet",
                    "start_time_act",
                    "end_time_act",
                    "effort_act",
                ]
                if record.auto_update_effort:
                    read_only.append("effort")
                if record.auto_update_time == 1:
                    read_only += ["start_time_fcast", "end_time_fcast", "days_fcast"]
                elif record.auto_update_time == 0:
                    read_only += ["start_time_plan", "end_time_plan", "days"]
            if record.cdb_project_id in pids_with_timesheet:
                read_only.append("effort_act")
            if record.msp_active or (
                record.locked_by and record.locked_by != auth.persno
            ):
                read_only += [
                    "start_time_fcast",
                    "end_time_fcast",
                    "days_fcast",
                    "auto_update_time",
                ]
            readOnlyByOID.update({record.cdb_object_id: list(set(read_only))})
        return readOnlyByOID


class TaskPlugin(TimeSchedulePlugin):
    table_name = "cdbpcs_task"
    classname = "cdbpcs_task"
    catalog_name = "cdbpcs_tasks_uuid"
    olc_attr = "cdb_objektart"
    allow_pinning = True
    description_pattern = ""  # unused, but must satisfy validation
    description_attrs = ("cdb_object_id", "task_name", "ce_baseline_id")
    calculation_attrs = (
        "start_time_fcast",
        "end_time_fcast",
        "auto_update_time",
        "percent_complet",
        "start_time_plan",
        "end_time_plan",
        "status",
        "is_group",
        "milestone",
        "total_float",
    )
    subject_id_attr = "subject_id"
    subject_type_attr = "subject_type"
    task_id_attr = "task_id"
    nullable_fields = {"daytime"}

    @classmethod
    def GetDescription(cls, record):
        return record.task_name

    @classmethod
    def GetRequiredFields(cls):
        return set.union(
            set([cls.olc_attr, cls.status_attr]),
            set([cls.task_id_attr]),
            set(cls.description_attrs),
            set(cls.calculation_attrs),
            set([cls.subject_id_attr, cls.subject_type_attr]),
        )

    @classmethod
    def ResolveStructure(cls, root_oid, request):
        query_pattern = get_query_pattern(
            "task_structure",
            load_query_pattern,
        )
        query_str = query_pattern.format(oid=root_oid)
        task_levels = resolve_query(query_str)
        project = get_project(root_oid)
        final_structure = task_levels
        if project and project.cdb_object_id:
            baseline = get_requested_baseline(project.cdb_object_id, request)
            # if no baseline data requested return the already resolved structure
            if baseline:
                bl_task = get_baselined_task(root_oid, baseline)
                if bl_task:
                    query_str = query_pattern.format(oid=bl_task.cdb_object_id)
                    bl_task_levels = resolve_query(query_str)
                    final_structure = merge_with_baseline_task(
                        final_structure, bl_task_levels, bl_task
                    )

        return final_structure

    @classmethod
    def GetClassReadOnlyFields(cls):
        """
        Returns list of task-specific fields that are always read only.

        Note:
            This method and TaskPlugin.GetObjectReadOnlyFields together
            are a redundant implementation of
            cs.pcs.projects.tasks.Task.getReadOnlyFields with
            action='modify' and Avoid_check=True
        """
        fqpyname = sqlapi.RecordSet2(
            "switch_tabelle", f"classname='{cls.classname}'", ["fqpyname"]
        )[0].fqpyname
        return getObjectByName(fqpyname).class_specific_read_only_fields

    @classmethod
    def GetObjectReadOnlyFields(cls, oids):
        """
        Returns mapping of given task oids to list of object specific fields,
        that are always read only.

        Note:
            This method and TaskPlugin.GetClassReadOnlyFields together
            are a redundant implementation of
            cs.pcs.projects.tasks.Task.getReadOnlyFields with
            action='modify' and Avoid_check=True
        """
        if len(oids) == 0:
            return {}
        records = sqlapi.RecordSet2(cls.table_name, get_oid_query_str(oids))
        pids = [entry.cdb_project_id for entry in records]
        # get msp_active and is locked by other user
        # from the corresponding projects
        attrByPID = {}
        pid_query_str = get_oid_query_str(pids, attr="cdb_project_id")
        condition = " And ".join((pid_query_str, "ce_baseline_id=''"))
        for project in sqlapi.RecordSet2("cdbpcs_project", condition):
            attr = {
                "msp_active": project.msp_active,
                "locked": (project.locked_by and project.locked_by != auth.persno),
            }
            attrByPID.update({project.cdb_project_id: attr})
        # get object specific readOnly Fields by record
        readOnlyByOID = {}
        for record in records:
            read_only = []
            if record.status != EXECUTION_STATUS:
                read_only.append("percent_complet")
            if record.status in [NEW_STATUS, READY_STATUS, DISCARDED_STATUS]:
                read_only += ["start_time_act", "end_time_act"]
            elif record.status == EXECUTION_STATUS:
                read_only.append("end_time_act")
            if record.effort_act:
                read_only.append("milestone")
            if record.is_group:
                read_only += [
                    "percent_complet",
                    "milestone",
                    "start_time_act",
                    "end_time_act",
                    "effort_act",
                ]
                if record.auto_update_effort:
                    read_only.append("effort")
                if record.auto_update_time == 1:
                    read_only += ["start_time_fcast", "end_time_fcast", "days_fcast"]
                elif record.auto_update_time == 0:
                    read_only += ["start_time_plan", "end_time_plan", "days"]
            pid = record.cdb_project_id
            if attrByPID[pid]["msp_active"] or attrByPID[pid]["locked"]:
                read_only += [
                    "start_time_fcast",
                    "end_time_fcast",
                    "days_fcast",
                    "milestone",
                    "parent_task_name",
                    "parent_task",
                    "auto_update_time",
                    "start_is_early",
                    "end_is_early",
                    "position",
                    "automatic",
                    "constraint_type",
                    "constraint_date",
                    "task_name",
                    "mapped_constraint_type_name",
                    "predecessors",
                    "successors",
                ]
            if record.milestone:
                read_only += ["effort_fcast", "effort_plan", "effort_act", "days_fcast"]
                if record.start_is_early:
                    read_only.append("end_time_fcast")
                else:
                    read_only.append("start_time_fcast")
            else:
                read_only += ["start_is_early", "end_is_early"]
            readOnlyByOID.update({record.cdb_object_id: list(set(read_only))})
        return readOnlyByOID


@sig.connect(GET_TABLE_DATA_PLUGINS)
def _register_project_plugin(register_callback):
    register_callback(ProjectPlugin)


@sig.connect(GET_TABLE_DATA_PLUGINS)
def _register_task_plugin(register_callback):
    register_callback(TaskPlugin)
