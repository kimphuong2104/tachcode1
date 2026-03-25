#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
This module contains functionality for exporting time schedules in
|tm.project| 's own XML format.
"""

from cdb import i18n, sqlapi
from cdb.lru_cache import lru_cache

from cs.pcs.msp import misc as msp_misc
from cs.pcs.msp.exports import XmlExport
from cs.pcs.scheduling.constants import (
    FIXED_CONSTRAINT_TYPES_EARLY,
    FIXED_CONSTRAINT_TYPES_LATE,
)


@lru_cache(maxsize=1)
def get_checklists_map(cdb_project_id, seperator):
    mapped_checklists = {}
    records = sqlapi.RecordSet2(
        sql="select task_id, checklist_name AS title "
        f"FROM cdbpcs_checklst WHERE cdb_project_id='{cdb_project_id}'"
    )
    for row in records:
        task_id = row["task_id"]
        checklist_name = str(row["title"])
        if task_id in mapped_checklists:
            checklist_name = seperator.join(
                [mapped_checklists[task_id], checklist_name]
            )
        mapped_checklists[task_id] = checklist_name
    return mapped_checklists


@lru_cache(maxsize=1)
def get_workflows_map(cdb_project_id, seperator):
    mapped_workflows = {}
    records = sqlapi.RecordSet2(
        sql="select a.task_id, c.title AS title "
        "FROM cdbpcs_task a, cdbwf_process_content b, cdbwf_process c "
        f"WHERE a.cdb_project_id = '{cdb_project_id}' "
        "and a.ce_baseline_id = '' "
        "and a.cdb_object_id=b.cdb_content_id "
        "and b.cdb_process_id=c.cdb_process_id "
    )
    for row in records:
        task_id = row["task_id"]
        workflow_title = str(row["title"])
        if task_id in mapped_workflows:
            workflow_title = seperator.join([mapped_workflows[task_id], workflow_title])
        mapped_workflows[task_id] = workflow_title
    return mapped_workflows


@lru_cache(maxsize=1)
def get_status_map():
    mapped_status = {}
    records = sqlapi.RecordSet2("objektstati", "objektart='cdbpcs_task'")
    for row in records:
        status_id = row["statusnummer"]
        mapped_status[status_id] = row["statusbez_" + i18n.default()]
    return mapped_status


class XmlExportConfiguration(XmlExport):
    """
    Configuration class for exporting and updating projects using |tm.project| xml format
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

    # TODO: Describe following 4 variables and also export them to the documentation?
    REF_OBJECTS_SEPARATOR = msp_misc.REF_OBJECTS_SEPARATOR
    REF_OBJECT_TOKENS_SEPARATOR = msp_misc.REF_OBJECT_TOKENS_SEPARATOR
    REF_CHECKLIST_ID_FIELD = msp_misc.REF_CHECKLIST_ID_FIELD
    REF_WORKFLOW_ID_FIELD = msp_misc.REF_WORKFLOW_ID_FIELD
    # Attribute mappings

    # Start of the manual part for PROJECT_MAPPING
    PROJECT_MAPPING = {
        # Defaults:
        #
        # Start Time (Target)
        "start_time_fcast": ("pcs_start_date_to_msp_start_date", "StartDate"),
        # End Time (Target)
        "end_time_fcast": ("pcs_finish_date_to_msp_finish_date", "FinishDate"),
    }
    # End of the manual part for PROJECT_MAPPING
    """
    For projects: Dictionary with a mapping between fields of Project Office
    (as keys) and fields of |tm.project| (as values).

    Valid values:

    - single string corresponding to the field name
    - tuple containing a method name of a callback class and the field name

    Callback method signature:

       .. code-block:: python

          def pcs_attr_x_to_msp_field_x(self, pcs_project, pcs_attr, msp_project, msp_attr):
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
    |tm.project| (as keys) and default values (as values).

    The default value is only used if no other value is transferred based
    on PROJECT_MAPPING

    The following configuration is delivered:
    """

    # Start of the manual part for TASK_MAPPING
    TASK_MAPPING = {
        # Defaults:
        #
        # Task Name
        "task_name": "Name",
        # Task Group (not displayed in the UI)
        "is_group": "Summary",
        # Milestone
        "milestone": "Milestone",
        # Responsible Name
        "mapped_subject_name": "Text14:PO Responsible",
        # PSP Code
        "psp_code": "WBS",
        # Identifier of the Object Life Cycle Status and Name of the Object Life Cycle status
        "status": [
            ("pcs_status_to_msp_active", "Active"),
            "Number10:PO Status Number",
            ("pcs_status_to_msp_po_status", "Text15:PO Status"),
        ],
        # Completed [%]
        "percent_complet": "PercentComplete",
        # Duration (Target)
        "days_fcast": ("pcs_duration_to_msp_durations", None),
        # Start Time (Target)
        "start_time_fcast": ("pcs_task_start_to_msp_task_start", None),
        # End Time (Target)
        "end_time_fcast": ("pcs_task_finish_to_msp_task_finish", None),
        # Automatic Calculation
        "automatic": ("pcs_automatic_to_msp_manual", "Manual"),
        # Constraint Type
        "constraint_type": "ConstraintType",
        # Constraint Date
        "constraint_date": (
            "pcs_constraint_date_to_msp_constraint_date",
            "ConstraintDate",
        ),
        # Reference ID for free usage
        "reference_id": "Text12:PO Reference ID",
        # ------------------------------------------------------------
        # DO NOT CHANGE THE FOLLOWING MAPPINGS (for internal use only)
        # Global Unique Identifier
        "msp_guid": "GUID",
        # Unique identifier
        "msp_uid": ("ensure_msp_uid", "UID"),
        # ------------------------------------------------------------
    }
    # End of the manual part for TASK_MAPPING
    """
    For tasks: Dictionary with a mapping between fields of Project Office
    (as keys) and fields of |tm.project| (as values).

    Valid values:

    - single string corresponding to the field name
    - tuple containing a method name of a callback class and the field name
      custom defined fields need an alias
      Only custom fields of types Number, Text, Start, Finish and Duration are supported

    .. note ::

        For custom attributes it is required to append a column alias to the
        field name, e.g.

        - "rating_descr": "Text30:Reason for Evaluation"
        - "end_time_plan": ("my_function_name", "Finish10:Forcast End Date")

    Callback method signature:

        .. code-block :: python

            def pcs_attr_x_to_msp_field_x(self,
                                          pcs_task,
                                          pcs_attr,
                                          msp_task,
                                          msp_attr):
                pass

    .. important ::

        You must not add task attributes to the list that change the project structure,
        such as task start, end, duration, predecessor, successor...

        The correctness and consistency of the time schedule cannot be ensured
        if task attributes that change the project structure are synchronized in both directions.

    The following configuration is delivered:
    """

    # Start of the manual part for TASK_DEFAULTS
    TASK_DEFAULTS = {
        # Default:
        #
        # Estimated
        #   Default value of |tm.project| is set to 1
        #   which ends in values with question marks
        "Estimated": 0,
    }
    # End of the manual part for TASK_DEFAULTS
    """
    For tasks: Dictionary with a mapping between fields of
    |tm.project| (as keys) and default values (as values).

    The default value is only used if no other value is transferred based
    on TASK_MAPPING

    The following configuration is delivered:
    """

    # Start of the manual part for TASK_REFERENCE_MAPPING
    TASK_REFERENCE_MAPPING = {
        # Defaults:
        #
        # Checklists (deactivated code: will be removed in future versions)
        # "pcs_checklists_to_msp_text": "Text13:PO Checklists",
        # Workflows (deactivated code: will be removed in future versions)
        # "pcs_workflows_to_msp_text": "Text11:PO Workflows",
    }
    # End of the manual part for TASK_REFERENCE_MAPPING
    """
    For tasks: Dictionary with a mapping between method names of callback
    classes in Project Office (as keys) and field names of |tm.project|
    (as values).
    The task field name can optionally be followed by a colon and a custom
    field name of |tm.project|.

    Callback method signature:

       .. code-block:: python

          def pcs_object_x_to_msp_field_x(self, pcs_task, msp_task, msp_attr):
              ...

    The following configuration is delivered:
    """

    # Start of the manual part for TASK_UPDATABLE_MSP_ATTRS
    TASK_UPDATABLE_MSP_ATTRS = [
        # Defaults:
        #
        # Mapped to the Object Life Cycle Status (status)
        "Active",
        # Identifier of the Object Life Cycle Status (status)
        "Number10",
        # Completed [%] (percent_complet)
        "PercentComplete",
        # Reference ID for free usage (reference_id)
        "Text12",
        # Responsible Name (mapped_subject_name)
        "Text14",
        # Name of the Object Life Cycle Status (status_txt)
        "Text15",
    ]
    # End of the manual part for TASK_UPDATABLE_MSP_ATTRS
    """
    For tasks: Here you can define which MSP fields get updated into existing
    MSP plans when pressing :guilabel:`Update Attributes` in the
    |cs.projectlink| menu bar.
    The mapping of attributes has been defined in the class property
    :ref:`TASK_MAPPING <pcs_api_exporting_time_schedule_xmlexport>`.

    The following configuration is delivered:
    """

    def ensure_msp_uid(self, pcs_task, pcs_attr, msp_task, msp_attr):
        pcs_value = self.get_pcs_task_msp_uid(pcs_task)
        return pcs_value

    def pcs_start_date_to_msp_start_date(self, pcs_object, pcs_attr, _, __):
        pcs_value = getattr(pcs_object, pcs_attr, "")

        if pcs_value:
            # projects don't have "start_is_early", use "morning" as fallback
            if getattr(pcs_object, "start_is_early", 1):
                return msp_misc.date2xml_date(pcs_value, self.DEFAULT_START_TIME)
            else:
                return msp_misc.date2xml_date(pcs_value, self.DEFAULT_FINISH_TIME)

        return pcs_value

    def pcs_task_start_to_msp_task_start(self, pcs_task, pcs_attr, msp_task, msp_attr):
        pcs_value = self.pcs_start_date_to_msp_start_date(
            pcs_task, pcs_attr, msp_task, msp_attr
        )
        self.set_msp_object_attr(msp_task, "Start", pcs_value)
        self.set_msp_object_attr(msp_task, "ManualStart", pcs_value)
        if not pcs_value:
            # Setting an empty "StartText" value defines the task as a "Placeholder" in MSP
            self.set_msp_object_attr(msp_task, "StartText", pcs_value)

    def pcs_finish_date_to_msp_finish_date(self, pcs_object, pcs_attr, _, __):
        pcs_value = getattr(pcs_object, pcs_attr, "")

        if pcs_value:
            # projects don't have "end_is_early", use "evening" as fallback
            if getattr(pcs_object, "end_is_early", 0):
                return msp_misc.date2xml_date(pcs_value, self.DEFAULT_START_TIME)
            else:
                return msp_misc.date2xml_date(pcs_value, self.DEFAULT_FINISH_TIME)

        return pcs_value

    def pcs_task_finish_to_msp_task_finish(
        self, pcs_task, pcs_attr, msp_task, msp_attr
    ):
        pcs_value = self.pcs_finish_date_to_msp_finish_date(
            pcs_task, pcs_attr, msp_task, msp_attr
        )
        self.set_msp_object_attr(msp_task, "Finish", pcs_value)
        self.set_msp_object_attr(msp_task, "ManualFinish", pcs_value)
        if not pcs_value:
            # Setting an empty "FinishText" value defines the task as a "Placeholder" in MSP
            self.set_msp_object_attr(msp_task, "FinishText", pcs_value)

    def pcs_duration_to_msp_durations(self, pcs_task, pcs_attr, msp_task, msp_attr):
        # MSP rule: only setting an MSP task's "Duration" field isn't sufficient, instead
        #           "ActualDuration" and "RemainingDuration" must be set depending on
        #           "PercentComplete"
        pcs_duration = (getattr(pcs_task, pcs_attr, 0) or 0) * self.DEFAULT_DURATION
        actual_duration = 0
        remaining_duration = pcs_duration
        if pcs_duration:
            # MSP rule: MSP simply rejects values with empty dates like "P0Y0M0DT8H0M0S",
            #           thus skip the date tokens if there's no date anyway => "PT8H0M0S"
            percent_complete = getattr(pcs_task, "percent_complet", 0)
            if percent_complete:
                actual_duration = int(
                    round(float(pcs_duration) * percent_complete / 100)
                )
                remaining_duration = pcs_duration - actual_duration

        def _hours_to_duration(hours):
            # Convert an hour (int or float) value to the MSP XML duration format (string)
            # E.g. when DEFAULT_DURATION is 8.5 then 25.5 hours (3 days) result in "PT25H30M0S"
            _hours = int(hours)
            _minutes = int((hours - _hours) * 60)
            return f"PT{_hours}H{_minutes}M0S"

        self.set_msp_object_attr(
            msp_task, "ActualDuration", _hours_to_duration(actual_duration)
        )
        self.set_msp_object_attr(
            msp_task, "RemainingDuration", _hours_to_duration(remaining_duration)
        )

    def pcs_flag_to_msp_flag_inverted(self, pcs_object, pcs_attr, msp_object, msp_attr):
        pcs_value = getattr(pcs_object, pcs_attr, 0)
        return 0 if (pcs_value == 1) else 1

    def pcs_status_to_msp_po_status(self, pcs_task, pcs_attr, msp_task, msp_attr):
        status_id = getattr(pcs_task, pcs_attr, "")
        status_map = get_status_map()
        return status_map.get(status_id)

    def pcs_automatic_to_msp_manual(self, pcs_task, pcs_attr, msp_task, msp_attr):
        if pcs_task.is_group:
            pcs_value = getattr(pcs_task, "auto_update_time", 0)
        else:
            pcs_value = getattr(pcs_task, pcs_attr, 0)
        return 0 if (pcs_value == 1) else 1

    def pcs_constraint_date_to_msp_constraint_date(self, pcs_task, pcs_attr, _, __):
        pcs_value = getattr(pcs_task, pcs_attr, "")
        constraint_type = getattr(pcs_task, "constraint_type", "")

        if constraint_type in FIXED_CONSTRAINT_TYPES_EARLY:
            return msp_misc.date2xml_date(pcs_value, self.DEFAULT_START_TIME)

        elif constraint_type in FIXED_CONSTRAINT_TYPES_LATE:
            return msp_misc.date2xml_date(pcs_value, self.DEFAULT_FINISH_TIME)

        return ""

    def pcs_status_to_msp_active(self, pcs_task, pcs_attr, msp_task, msp_attr):
        pcs_value = getattr(pcs_task, pcs_attr, 0)
        return "1" if (pcs_value != 180) else "0"

    def pcs_subject_to_msp_text(self, pcs_task, pcs_attr, msp_task, msp_attr):
        """
        If you need to export 100% unique IDs instead of the descriptive mapped names for the task's
        responsible persons, then you should replace the mapping for the Text14 field like this:
        TASK_MAPPING["subject_id"] = ("pcs_subject_to_msp_text", "Text14:PO Responsible")
        """
        # Show subject_type (role) as prefix
        pcs_value = self.REF_OBJECT_TOKENS_SEPARATOR.join(
            [
                getattr(pcs_task, "subject_type", "") or "",
                getattr(pcs_task, pcs_attr, "") or "",
            ]
        )
        return pcs_value

    def pcs_checklists_to_msp_text(self, pcs_task, msp_task, msp_attr):
        cdb_project_id = self.pcs_project.cdb_project_id
        checklists_map = get_checklists_map(cdb_project_id, self.REF_OBJECTS_SEPARATOR)
        return checklists_map.get(pcs_task.task_id)

    def pcs_workflows_to_msp_text(self, pcs_task, msp_task, msp_attr):
        cdb_project_id = self.pcs_project.cdb_project_id
        workflows_map = get_workflows_map(cdb_project_id, self.REF_OBJECTS_SEPARATOR)
        return workflows_map.get(pcs_task.task_id)
