#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=too-many-nested-blocks

"""
The module contains functionality for creating and updating time schedules that
have been processed with |tm.project|.

The data is transferred based on the XML schema of |tm.project|.
The XML schema has been extended by |cs.pcs|.
"""

import math
import re

from cdb import auth, misc, ue, util
from cdb.constants import kOperationCopy
from cdb.objects.org import CommonRole, Person
from cs.workflow.processes import Process

from cs.pcs.checklists import Checklist
from cs.pcs.msp import misc as msp_misc
from cs.pcs.msp.import_results import DiffType
from cs.pcs.msp.imports import XmlMergeImport
from cs.pcs.projects import Project, Role, kProjectManagerRole
from cs.pcs.projects.tasks import (
    DAYTIME_EVENING,
    DAYTIME_MORNING,
    DAYTIME_NOT_APPLICABLE,
    Task,
)


class XmlMergeImportConfiguration(XmlMergeImport):
    """
    Configuration class for publishing and importing projects using |tm.project| xml format
    """

    # Start of the manual part for DEFAULT_START_TIME
    DEFAULT_START_TIME = msp_misc.DEFAULT_START_TIME
    # End of the manual part for DEFAULT_START_TIME
    """
    Default start time for tasks.
    This value must match the project settings of |tm.project|.

    The following configuration is delivered:
    """

    # Start of the manual part for DEFAULT_FINISH_TIME
    DEFAULT_FINISH_TIME = msp_misc.DEFAULT_FINISH_TIME
    # End of the manual part for DEFAULT_FINISH_TIME
    """
    Default end time for tasks.
    This value must match the project settings of |tm.project|.

    The following configuration is delivered:
    """

    # Start of the manual part for DEFAULT_DURATION
    DEFAULT_DURATION = msp_misc.DEFAULT_DURATION
    # End of the manual part for DEFAULT_DURATION
    """
    Default duration for tasks in hour.
    This value must match the project settings of |tm.project|.

    The following configuration is delivered:
    """

    # TODO: Describe following 5 variables and also export them to the documentation?
    REF_OBJECTS_SEPARATOR = msp_misc.REF_OBJECTS_SEPARATOR
    REF_OBJECT_TOKENS_SEPARATOR = msp_misc.REF_OBJECT_TOKENS_SEPARATOR
    REF_PROJECT_ID_FIELD = msp_misc.REF_PROJECT_ID_FIELD
    REF_CHECKLIST_ID_FIELD = msp_misc.REF_CHECKLIST_ID_FIELD
    REF_WORKFLOW_ID_FIELD = msp_misc.REF_WORKFLOW_ID_FIELD

    # Attribute mappings

    # Start of the manual part for SYSTEM_ATTRIBUTES
    SYSTEM_ATTRIBUTES = [
        "msp_guid",
        "msp_uid",
        "position",
        "early_start",
        "early_finish",
        "late_start",
        "late_finish",
        "free_float",
        "total_float",
        "is_group",
        "daytime",
    ]
    # End of the manual part for SYSTEM_ATTRIBUTES
    """
    For tasks: List of system attributes which are not shown in the preview.
    The following configuration is delivered:
    """

    # Attribute mappings

    # Start of the manual part for TASK_READONLY_FIELDS
    TASK_READONLY_FIELDS = [
        "start_time_fcast",
        "end_time_fcast",
        "days_fcast",
        "milestone",
        "parent_task_name",
        "parent_task",
        "start_is_early",
        "end_is_early",
        "daytime",
        "position",
        "automatic",
        "constraint_type",
        "constraint_date",
        "task_name",
        "mapped_constraint_type_name",
    ]
    # End of the manual part for TASK_READONLY_FIELDS
    """
    For tasks: List of attributes which are read only in Project Offices
    when editing tasks.
    The following configuration is delivered:
    """

    # Attribute mappings

    # Start of the manual part for PROJECT_MANAGER
    PROJECT_MANAGER = kProjectManagerRole
    # End of the manual part for PROJECT_MANAGER
    """
    For tasks: The project manager role as configured in |tm.project|
    The following configuration is delivered:
    """

    # Attribute mappings

    # Start of the manual part for PROJECT_MAPPING
    PROJECT_MAPPING = {
        # Defaults:
        #
        # End Date (Target)
        "FinishDate": "end_time_fcast",
        # Start Date (Target)
        "StartDate": "start_time_fcast",
    }
    # End of the manual part for PROJECT_MAPPING
    """
    For projects: Dictionary with a mapping between fields of |tm.project|
    (as keys) and fields of Project Office (as values).

    Valid values:

    - single string corresponding to the field name
    - tuple containing a method name of a callback class and the field name

    Callback method signature:

       .. code-block:: python

          def msp_field_x_to_pcs_attr_x(
              self, msp_project, msp_attr, pcs_project_attrs, pcs_attr, pcs_obj_or_cls
          ):
              ...

    The following configuration is delivered:
    """

    # Start of the manual part for PROJECT_DEFAULTS
    PROJECT_DEFAULTS = {
        # Defaults:
        #
        # No default values are configured
    }
    # End of the manual part for PROJECT_DEFAULTS
    """
    For projects: Dictionary with a mapping between fields of
    Project Office (as keys) and default values (as values).

    The default value is only used if no other value is transferred based
    on PROJECT_MAPPING

    The following configuration is delivered:
    """

    # Start of the manual part for PROJECT_ATTR_ORDER
    PROJECT_ATTR_ORDER = [
        # Defaults:
        #
        # Start Date (Target)
        "start_time_fcast",
        # End Date (Target)
        "end_time_fcast",
    ]
    # End of the manual part for PROJECT_ATTR_ORDER
    """
    For projects: Here you  can  define the order in which the fields are
    displayed in the preview dialog of the import.

    The following configuration is delivered:
    """

    # Start of the manual part for TASK_MAPPING
    TASK_MAPPING = {
        # Defaults:
        #
        # Task Name
        "Name": "task_name",
        # Task Group (not displayed in the UI)
        "Summary": "is_group",
        # Milestone
        "Milestone": ("msp_milestone_to_pcs_milestone", "milestone"),
        # Responsible Type and ID
        "Text14": ("msp_text_to_pcs_responsible", None),
        # Object Life Cycle Status
        "PercentComplete": ("msp_task_completion_to_pcs_status", "percent_complet"),
        # Duration (Target)
        "ManualDuration": ("msp_duration_to_pcs_duration", "days_fcast"),
        # Start Date (Target)
        "Start": ("msp_task_start_to_pcs_task_start", None),
        # End Date (Target)
        "Finish": ("msp_task_finish_to_pcs_task_finish", None),
        # Automatic Calculation
        "Manual": ("msp_flag_to_pcs_flag_inverted", ["automatic", "auto_update_time"]),
        # Constraint Type
        "ConstraintType": "constraint_type",
        # Constraint Date
        "ConstraintDate": "constraint_date",
        # Early Start
        "EarlyStart": "early_start",
        # Early Finish
        "EarlyFinish": "early_finish",
        # Late Start
        "LateStart": "late_start",
        # Late Finish
        "LateFinish": "late_finish",
        # Free Float
        "FreeSlack": ("msp_slack_to_pcs_float", "free_float"),
        # Total Float
        "TotalSlack": ("msp_slack_to_pcs_float", "total_float"),
        # Reference ID for free usage
        "Text12": ("msp_text_to_pcs_reference_id", "reference_id"),
        # ------------------------------------------------------------
        # DO NOT CHANGE THE FOLLOWING MAPPINGS (for internal use only)
        # Global unique identifier
        "GUID": "msp_guid",
        # Unique identifier
        "UID": "msp_uid",
        # ------------------------------------------------------------
    }
    # End of the manual part for TASK_MAPPING
    """
    For tasks: Dictionary with a mapping between fields of |tm.project|
    (as keys) and fields of Project Office (as values).

    Valid values:

    - single string corresponding to the field name
    - tuple containing a method name of a callback class and the field name

    .. _`projects_api_importing_callback_method_signature`:

    Callback method signature:

       .. code-block:: python

          def msp_field_x_to_pcs_attr_x(
              self, msp_task, msp_attr, pcs_task_attrs, pcs_attr, pcs_obj_or_cls
          ):
              ...

    .. important::
       ``pcs_obj_or_cls`` contains different information if you are creating or modifying an object.
       Either the actual object (modify) or the class of the object (create).

    The following configuration is delivered:
    """

    # Start of the manual part for TASK_DEFAULTS
    TASK_DEFAULTS = {
        # Subject Type
        "subject_type": Role.__subject_type__,
        # Subject Id: Team Member
        "subject_id": "Projektmitglied",
        # Object Life Cycle
        "cdb_objektart": "cdbpcs_task",
        # Status
        "status": 0,
        # Status
        "cdb_status_txt": "New",
        # Adopt Buttom Up Date as Target
        "auto_update_time": 2,
        # Effort (Target) [h]
        "effort_fcast": 0.0,
        # Resource Allocation [h]
        "effort_fcast_a": 0.0,
        # Resource Demand [h]
        "effort_fcast_d": 0.0,
        # Effort (Bottom Up) [h]
        "effort_plan": 0.0,
        # Effort (Actual) [h]
        "effort_act": 0.0,
    }
    # End of the manual part for TASK_DEFAULTS
    """
    For tasks: Dictionary with a mapping between fields of
    Project Office (as keys) and default values (as values).

    The default value is only used if no other value is transferred based
    on TASK_MAPPING

    The following configuration is delivered:
    """

    # Start of the manual part for TASK_ATTR_ORDER
    TASK_ATTR_ORDER = [
        # Defaults:
        #
        # Start Date (Target)
        "start_time_fcast",
        # End Date (Target)
        "end_time_fcast",
        # Duration
        "days_fcast",
        # Task Name
        "task_name",
        # Constraint Type
        "constraint_type",
        # Constraint Date
        "constraint_date",
        # Automatic Calculation
        "automatic",
        # Adopt Buttom Up Date as Target
        "auto_update_time",
        # Milestone
        "milestone",
        # Early Start
        "early_start",
        # Early Finish
        "early_finish",
        # Late Start
        "late_start",
        # Late Finish
        "late_finish",
        # Free Float
        "free_float",
        # Total Float
        "total_float",
    ]
    # End of the manual part for TASK_ATTR_ORDER
    """
    For tasks: Here you  can  define the order in which the fields are
    displayed in the preview dialog of the import.

    The following configuration is delivered:
    """

    # Start of the manual part for TASK_ATTR_IMPORT_ORDER
    TASK_ATTR_IMPORT_ORDER = [
        "Start",
        "Finish",
        "ManualDuration",
        "Name",
        "ConstraintType",
        "ConstraintDate",
        "Manual",
        "Milestone",
        "EarlyStart",
        "EarlyFinish",
        "LateStart",
        "LateFinish",
        "FreeSlack",
        "TotalSlack",
    ]
    # End of the manual part for TASK_ATTR_IMPORT_ORDER
    """
    For tasks: Here you can define the order in which the fields are
    evaluated when the import from MSP is executed.

    The following configuration is delivered:
    """

    # Start of the manual part for TASK_REFERENCE_MAPPING
    TASK_REFERENCE_MAPPING = {
        # Defaults:
        #
        # Checklists
        "Text13": "msp_text_to_pcs_checklists",
        # Workflows
        "Text11": "msp_text_to_pcs_workflows",
    }
    # End of the manual part for TASK_REFERENCE_MAPPING
    """
    For tasks: Dictionary with a mapping between fields of |tm.project|
    (as keys) and referenced objects of Project Office (as values).
    Valid Values are method names of callback classes.
    Referenced objects can be: checklists, workflows

    Callback method signature:

       .. code-block:: python

          def msp_field_x_to_pcs_object_x(self, msp_task, msp_attr, pcs_task):
              ...

    The following configuration is delivered:
    """

    def msp_task_completion_to_pcs_status(
        self, msp_object, msp_attr, pcs_object_attrs, pcs_attr, pcs_obj_or_cls
    ):
        if not isinstance(pcs_obj_or_cls, type):
            return
        active = int(f"{getattr(msp_object, 'Active', 1)}")
        percent = getattr(msp_object, msp_attr, 0)
        percent = int(percent) if percent else 0
        if active:
            status, status_txt = Task.get_status_by_completion(percent)
        else:
            status = Task.DISCARDED.status
            status_txt = Task.get_status_txt(status)
        pcs_object_attrs[pcs_attr] = percent
        pcs_object_attrs["status"] = status
        pcs_object_attrs["cdb_status_txt"] = status_txt
        if status in Task.endStatus(full_cls=False):
            ref_checklist_ids = f'{getattr(msp_object, "Text13", "")}'
            ref_workflow_ids = f'{getattr(msp_object, "Text11", "")}'
            if ref_checklist_ids or ref_workflow_ids:
                raise ue.Exception("cdbpcs_task_status_referenced_objects")

    def msp_slack_to_pcs_float(
        self, msp_object, msp_attr, pcs_object_attrs, pcs_attr, pcs_obj_or_cls
    ):
        """
        The MSP value for 'Free Slack' and 'Total Slack':
        A duration of time, provided as an integer, that has to be adjusted
        as days value (by default devided by 4800 for a default duration of 8).
        """
        msp_value = f'{getattr(msp_object, msp_attr, "")}'
        pcs_val = 0
        if msp_value:
            pcs_val = int(msp_value) / 600 / int(self.DEFAULT_DURATION)
        pcs_object_attrs[pcs_attr] = int(pcs_val)

    def msp_duration_to_pcs_duration(
        self, msp_object, msp_attr, pcs_object_attrs, pcs_attr, pcs_obj_or_cls
    ):
        """
        The MSP data type 'duration':
         A duration of time, provided in the format PnYnMnDTnHnMnS where nY represents the number of
         years, nM the number of months, nD the number of days, T the date/time separator, nH the
         number of hours, nM the number of minutes, and nS the number of seconds.
         For example, to indicate a duration of 1 year, 2 months, 3 days, 10 hours, and 30 minutes,
         you write: P1Y2M3DT10H30M. You could also indicate a duration of minus 120 days as -P120D.
        """
        msp_value = f"{getattr(msp_object, msp_attr, getattr(msp_object, 'RemainingDuration', ''))}"
        if msp_value:
            match = re.match(
                r"P"
                r"((?P<years>\d*)Y)?"
                r"((?P<months>\d*)M)?"
                r"((?P<days>\d*)D)?"
                r"T?"
                r"((?P<hours>\d*)H)?"
                r"((?P<minutes>\d*)M)?"
                r"((?P<seconds>\d*)S)?",
                msp_value,
            )
            hours = int(match.group("hours") if match.group("hours") else 0)
            hours += (
                int(match.group("days") if match.group("days") else 0)
                * self.DEFAULT_DURATION
            )
            hours += (
                int(match.group("months") if match.group("months") else 0)
                * self.DEFAULT_DURATION
                * 20
            )  # <= ???
            hours += (
                int(match.group("years") if match.group("years") else 0)
                * self.DEFAULT_DURATION
                * 240
            )  # <= ???
            pcs_object_attrs[pcs_attr] = int(math.ceil(hours / self.DEFAULT_DURATION))

    def _is_msp_placeholder_task(self, msp_task, msp_attr):
        """
        An empty "StartText" or "FinishText" value defines the task as a "Placeholder" in MSP
        MSP exports empty placeholders in XML as "\n      "

        Don't apply the "Start" and "Finish" values for placeholder tasks,
        since they values are always written to XML by MSP,
        even if they are displayed as empty values in their respective column in MSP.
        """
        return (
            hasattr(msp_task, msp_attr)
            and not f"{getattr(msp_task, msp_attr, '')}".strip()
        )

    def msp_task_start_to_pcs_task_start(
        self, msp_task, msp_attr, pcs_task_attrs, _, __
    ):
        if self._is_msp_placeholder_task(msp_task, "StartText"):
            pcs_task_attrs["start_time_fcast"] = None
            milestone = getattr(msp_task, "Milestone", 0)
            if milestone:
                pcs_task_attrs["start_is_early"] = 0
            else:
                pcs_task_attrs["start_is_early"] = 1
        else:
            msp_value = f'{getattr(msp_task, msp_attr, "")}'
            start, start_is_early = msp_misc.xml_date2date(
                msp_value, False, self.DEFAULT_START_TIME, self.DEFAULT_FINISH_TIME
            )
            pcs_task_attrs["start_time_fcast"] = start
            pcs_task_attrs["start_is_early"] = start_is_early

    def msp_task_finish_to_pcs_task_finish(
        self, msp_task, msp_attr, pcs_task_attrs, _, __
    ):
        if self._is_msp_placeholder_task(msp_task, "FinishText"):
            pcs_task_attrs["end_time_fcast"] = None
            pcs_task_attrs["end_is_early"] = 0
        else:
            msp_value = f'{getattr(msp_task, msp_attr, "")}'
            end, end_is_early = msp_misc.xml_date2date(
                msp_value, False, self.DEFAULT_START_TIME, self.DEFAULT_FINISH_TIME
            )
            pcs_task_attrs["end_time_fcast"] = end
            pcs_task_attrs["end_is_early"] = end_is_early

    def msp_flag_to_pcs_flag_inverted(
        self, msp_object, msp_attr, pcs_object_attrs, pcs_attr, pcs_obj_or_cls
    ):
        msp_value = f'{getattr(msp_object, msp_attr, "")}'
        if pcs_attr == "automatic":
            pcs_object_attrs[pcs_attr] = 0 if msp_value == "1" else 1
        if pcs_attr == "auto_update_time":
            if pcs_obj_or_cls and isinstance(pcs_obj_or_cls, Task):
                if msp_value == "1":
                    if pcs_obj_or_cls[pcs_attr] == 1:
                        pcs_object_attrs[pcs_attr] = 2
                    else:
                        pcs_object_attrs[pcs_attr] = pcs_obj_or_cls[pcs_attr]
                else:
                    pcs_object_attrs[pcs_attr] = 1
            else:
                pcs_object_attrs[pcs_attr] = 2 if msp_value == "1" else 1

    def msp_milestone_to_pcs_milestone(
        self, msp_task, msp_attr, pcs_task_attrs, pcs_attr, _
    ):
        milestone = getattr(msp_task, msp_attr, 0)
        pcs_task_attrs[pcs_attr] = int(milestone)

        if milestone and getattr(msp_task, "Manual", 0):
            if self._is_msp_placeholder_task(msp_task, "StartText"):
                pcs_task_attrs["daytime"] = DAYTIME_EVENING
            else:
                msp_start = f'{getattr(msp_task, "Start", "")}'
                _, start_is_early = msp_misc.xml_date2date(
                    msp_start, False, self.DEFAULT_START_TIME, self.DEFAULT_FINISH_TIME
                )
                if start_is_early:
                    pcs_task_attrs["daytime"] = DAYTIME_MORNING
                else:
                    pcs_task_attrs["daytime"] = DAYTIME_EVENING
        else:
            pcs_task_attrs["daytime"] = DAYTIME_NOT_APPLICABLE

    def msp_text_to_pcs_reference_id(
        self, msp_task, msp_attr, pcs_task_attrs, pcs_attr, pcs_obj_or_cls
    ):
        msp_value = f'{getattr(msp_task, msp_attr, "")}'
        if msp_value:
            # only initially write values from msp to pcs - don't overwrite existing ones
            if isinstance(pcs_obj_or_cls, type) or not getattr(
                pcs_obj_or_cls, pcs_attr
            ):
                pcs_task_attrs[pcs_attr] = msp_misc.MspToPcs.convert_value(
                    pcs_obj_or_cls, pcs_attr, msp_value
                )

    def msp_text_to_pcs_responsible(
        self, msp_task, msp_attr, pcs_task_attrs, pcs_attr, pcs_obj_or_cls
    ):
        msp_value = f'{getattr(msp_task, msp_attr, "")}'
        # only initially write values from msp to pcs - don't overwrite existing ones
        if (
            msp_value
            and isinstance(pcs_obj_or_cls, type)
            or (
                not getattr(pcs_obj_or_cls, "subject_type")
                and not getattr(pcs_obj_or_cls, "subject_id")
            )
        ):
            vals = msp_value.split(self.REF_OBJECT_TOKENS_SEPARATOR, 1)
            if len(vals) < 2:
                subject_id = vals[0]
                subject_type = ""
                if not subject_id:
                    return
            else:
                subject_type, subject_id = vals
            if not subject_type:
                person = Person.Query(
                    """name = '{subject_id}' OR
                                         personalnummer = '{subject_id}' OR
                                         login = '{subject_id}'""".format(
                        subject_id=subject_id
                    )
                )
                if person:
                    subject_type = "Person"
                    subject_id = person[0].personalnummer
                else:
                    found_no_role = True
                    for r in self.pcs_project.Roles:
                        if subject_id in (r.role_id, r.mapped_name):
                            subject_type = Role.__subject_type__
                            subject_id = r.role_id
                            found_no_role = False
                            break
                    if found_no_role:
                        for cr in CommonRole.Query():
                            if subject_id in (cr.role_id, cr.name):
                                subject_type = "Common Role"
                                subject_id = cr.role_id
                                found_no_role = False
                                break
                    if found_no_role:
                        raise ue.Exception("cdbpcs_subject_type_not_found", subject_id)
            else:
                if subject_type == "Person":
                    if not Person.ByKeys(personalnummer=subject_id):
                        raise ue.Exception("cdbpcs_person_not_found", subject_id)
                elif subject_type == Role.__subject_type__:
                    roles = [r.role_id for r in self.pcs_project.Roles]
                    if subject_id not in roles:
                        raise ue.Exception(
                            "cdbpcs_role_not_found", subject_type, subject_id
                        )
                else:
                    roles = [r.role_id for r in CommonRole.Query()]
                    if subject_id not in roles:
                        raise ue.Exception(
                            "cdbpcs_role_not_found", subject_type, subject_id
                        )
            pcs_task_attrs["subject_type"] = msp_misc.MspToPcs.convert_value(
                pcs_obj_or_cls, "subject_type", subject_type
            )
            pcs_task_attrs["subject_id"] = msp_misc.MspToPcs.convert_value(
                pcs_obj_or_cls, "subject_id", subject_id
            )

    def msp_text_to_pcs_checklists(self, msp_task, msp_attr, pcs_task):
        already_existing = []
        ref_checklist_ids = f'{getattr(msp_task, msp_attr, "")}'
        if ref_checklist_ids:
            for ref_checklist_id in ref_checklist_ids.split(self.REF_OBJECTS_SEPARATOR):
                ref_checklist_id = ref_checklist_id.strip()

                try:
                    template_project = None
                    if self.REF_OBJECT_TOKENS_SEPARATOR in ref_checklist_id:
                        template_project_id, ref_checklist_id = ref_checklist_id.split(
                            self.REF_OBJECT_TOKENS_SEPARATOR, 1
                        )
                        args = {
                            self.REF_PROJECT_ID_FIELD: template_project_id,
                            "ce_baseline_id": "",
                            "template": 1,
                        }
                        template_project = Project.KeywordQuery(**args)
                        if not template_project:
                            raise ue.Exception(
                                "cdbpcs_template_object_not_found", repr(args)
                            )
                        template_project = template_project[0]

                    args = {self.REF_CHECKLIST_ID_FIELD: ref_checklist_id}
                    # check if it's either a new task or if the checklist doesn't exist yet
                    if not isinstance(
                        pcs_task, Task
                    ) or not pcs_task.Checklists.KeywordQuery(**args):
                        args["template"] = 1
                        if template_project:
                            args["cdb_project_id"] = template_project.cdb_project_id
                            cl_src = Checklist.KeywordQuery(**args)
                        else:
                            cl_src = self.pcs_project.Checklists.KeywordQuery(**args)
                        if not cl_src:
                            raise ue.Exception(
                                "cdbpcs_template_object_not_found", repr(args)
                            )
                        cl_src = cl_src[0]

                        args_new = {
                            "cdb_project_id": self.pcs_project.cdb_project_id,
                            "task_id": "",
                            "template": 0,
                        }
                        if (
                            not self.dry_run
                            and ref_checklist_id not in already_existing
                        ):
                            args_new["checklist_id"] = util.nextval("cdbpcs_checklist")
                            cl_new = msp_misc.operation_ex(
                                kOperationCopy,
                                cl_src,
                                args_new,
                                self.called_from_officelink,
                            )
                            # task_id has to be set after operation because task might not exist yet
                            # and in this case operation would result in an error
                            task_id = getattr(
                                pcs_task, "task_id", None
                            ) or pcs_task.get("task_id")
                            cl_new.Update(task_id=task_id)
                            already_existing.append(ref_checklist_id)
                        else:
                            # bogus preview object
                            cl_new = args_new
                            for k, v in cl_src.items():
                                cl_new.setdefault(k, v)

                        icon_name = msp_misc.get_icon_name(
                            f"cdbpcs_{cl_src.type.lower()}"
                        )
                        self.result.add_diff_object(
                            DiffType.ADDED,
                            cl_new,
                            Checklist,
                            icon_name,
                            parent=pcs_task,
                        )
                except Exception as ex:
                    misc.log_traceback("")
                    self.result.add_diff_object(
                        DiffType.MODIFIED, pcs_task, Task, exception=ex
                    )

    def msp_text_to_pcs_workflows(self, msp_task, msp_attr, pcs_task):
        already_existing = []
        ref_workflow_ids = f'{getattr(msp_task, msp_attr, "")}'
        if ref_workflow_ids:
            for ref_workflow_id in ref_workflow_ids.split(self.REF_OBJECTS_SEPARATOR):
                ref_workflow_id = ref_workflow_id.strip()

                try:
                    template_project = None
                    if self.REF_OBJECT_TOKENS_SEPARATOR in ref_workflow_id:
                        template_project_id, ref_workflow_id = ref_workflow_id.split(
                            self.REF_OBJECT_TOKENS_SEPARATOR, 1
                        )
                        args = {
                            self.REF_PROJECT_ID_FIELD: template_project_id,
                            "ce_baseline_id": "",
                            "template": 1,
                        }
                        template_project = Project.KeywordQuery(**args)
                        if not template_project:
                            raise ue.Exception(
                                "cdbpcs_template_object_not_found", repr(args)
                            )
                        template_project = template_project[0]

                    args = {self.REF_WORKFLOW_ID_FIELD: ref_workflow_id}
                    # check if it's either a new task or if the process doesn't exist yet
                    if not isinstance(
                        pcs_task, Task
                    ) or not pcs_task.Processes.KeywordQuery(**args):
                        args["is_template"] = "1"
                        if template_project:
                            args["cdb_project_id"] = template_project.cdb_project_id
                            proc_src = Process.KeywordQuery(**args)
                        else:
                            proc_src = self.pcs_project.Processes.KeywordQuery(**args)
                        if not proc_src:
                            raise ue.Exception(
                                "cdbpcs_template_object_not_found", repr(args)
                            )
                        proc_src = proc_src[0]

                        if not self.dry_run and ref_workflow_id not in already_existing:
                            # adapted from cs.workflow.briefcases.BriefcaseContent
                            #  .on_cdbwf_ahwf_new_from_template_now
                            proc_new = Process.CreateFromTemplate(
                                proc_src.cdb_process_id,
                                {"subject_id": auth.persno, "subject_type": "Person"},
                            )
                            proc_new.make_attachments_briefcase()
                            # remember workflow to task mapping for later
                            # (only persistent tasks can be attached to workflows)
                            self.result.workflow_content.append(
                                (proc_new, Task(**pcs_task))
                            )
                            already_existing.append(ref_workflow_id)
                        else:
                            # bogus preview object
                            proc_new = {
                                "cdb_project_id": self.pcs_project.cdb_project_id,
                                "is_template": "0",
                            }
                            for k, v in proc_src.items():
                                proc_new.setdefault(k, v)

                        icon_name = msp_misc.get_icon_name(proc_src.cdb_classname)
                        self.result.add_diff_object(
                            DiffType.ADDED,
                            proc_new,
                            Process,
                            icon_name,
                            parent=pcs_task,
                        )
                except Exception as ex:
                    misc.log_traceback("")
                    self.result.add_diff_object(
                        DiffType.MODIFIED, pcs_task, Task, exception=ex
                    )
