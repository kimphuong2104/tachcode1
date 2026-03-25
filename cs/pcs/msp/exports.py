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

import os
import tempfile
from datetime import datetime

from cdb import CADDOK, sqlapi, ue
from cdb.sig import emit, signal
from cdb.transactions import Transaction
from lxml import objectify  # nosec

from cs.pcs.msp import misc as msp_misc
from cs.pcs.msp.misc import logger

CAN_UPDATE_PROJECT = signal()


class TempFile:
    def __init__(self):
        self.handle, self.temp_filename = tempfile.mkstemp(
            suffix=".xml", prefix="mspxml-", dir=CADDOK.TMPDIR
        )

    def __enter__(self):
        return self.temp_filename

    def __exit__(self, exc_type, exc_value, traceback):
        os.close(self.handle)


class XmlExport:
    def __init__(self):
        self.pcs_project = None
        self.msp_project = None

    @classmethod
    def generate_xml_from_project(cls, pcs_project_object_or_id):
        """
        Performs a full export of given PCS project and returns the path to the resulting temporary
        xml file.
        """
        logger.info("pcs_project_object_or_id=%s", pcs_project_object_or_id)

        export = cls()
        with Transaction(), TempFile() as temp_filename:
            export.set_pcs_project(pcs_project_object_or_id)
            export.set_target_xml_filename(temp_filename)
            export.execute()

        logger.info("temp_filename=%s", temp_filename)
        return temp_filename

    def set_pcs_project(self, pcs_project_object_or_id):
        from cs.pcs.projects import Project

        if isinstance(pcs_project_object_or_id, Project):
            self.pcs_project = pcs_project_object_or_id
        else:
            self.pcs_project = Project.ByKeys(cdb_project_id=pcs_project_object_or_id)

        if not (self.pcs_project and self.pcs_project.CheckAccess("read")):
            raise ue.Exception("cdbpcs_no_project_right")

        t = sqlapi.SQLselect(
            "MAX(msp_uid) FROM cdbpcs_task "
            f"WHERE cdb_project_id='{self.pcs_project.cdb_project_id}' "
            f"AND ce_baseline_id='{self.pcs_project.ce_baseline_id}'"
        )
        self.max_msp_uid = sqlapi.SQLinteger(t, 0, 0)
        logger.info("max_msp_uid=%s", self.max_msp_uid)

    def set_target_xml_filename(self, xml_filename):
        self.xml_filename = xml_filename

    def execute(self):
        from cs.pcs.msp.export_mapping import get_checklists_map, get_workflows_map

        start_time = datetime.now()
        get_checklists_map.cache_clear()
        get_workflows_map.cache_clear()
        logger.info("setting up project specific export config (callback)..")
        self.pcs_project.set_msp_default_times()

        logger.info("exporting project attributes..")
        self.msp_project = objectify.Element(
            "Project", nsmap={None: msp_misc.MSP_XML_SCHEMA}
        )
        self.get_mapped_attrs(
            self.PROJECT_MAPPING,
            self.PROJECT_DEFAULTS,
            self.pcs_project,
            self.msp_project,
        )

        logger.info("adding default calendar..")
        self.add_msp_default_calendar()

        logger.info("exporting tasks..")
        self.msp_project.extend(objectify.Element("Tasks"))
        for pcs_task in self.pcs_project.TopTasks:
            self.traverse_task(pcs_task, 1)

        logger.info("writing xml file..")
        objectify.deannotate(self.msp_project, xsi_nil=True)
        objectify.deannotate(self.msp_project.Tasks, xsi_nil=True)
        # TODO: add comment "created by <full classname> 15.x.x.x"
        self.msp_project.getroottree().write(
            self.xml_filename, encoding="UTF-8", pretty_print=True, xml_declaration=True
        )
        logger.info(
            "Export finished in %s second(s)", (datetime.now() - start_time).seconds
        )

    def get_mapped_attrs(self, attr_mapping, attr_defaults, pcs_object, msp_object):
        """Adds default and mapped attribute values of a PCS object to an MSP XML object."""
        for msp_attr, default_value in list(attr_defaults.items()):
            self.set_msp_object_attr(msp_object, msp_attr, default_value)
        for pcs_attr, msp_attrs in attr_mapping.items():
            if not isinstance(msp_attrs, list):
                msp_attrs = [msp_attrs]
            for msp_attr in msp_attrs:
                msp_column_name = None
                if isinstance(msp_attr, tuple):
                    function, msp_attr = msp_attr
                    function = getattr(self, function)
                    if msp_attr and (":" in msp_attr):
                        msp_attr, msp_column_name = msp_attr.split(":")
                    pcs_value = function(pcs_object, pcs_attr, msp_object, msp_attr)
                else:
                    if msp_attr and (":" in msp_attr):
                        msp_attr, msp_column_name = msp_attr.split(":")
                    pcs_value = getattr(pcs_object, pcs_attr, "")
                if msp_attr:
                    self.set_msp_object_attr(
                        msp_object, msp_attr, pcs_value, msp_column_name
                    )

    def add_msp_default_calendar(self):
        """
        Adds a default calendar (work times) and calendar options (default task start time, end time
        and duration). Also see the method 'get_default_msp_calendar_working_times' for
        customization purposes.
        Note: Every calendar exception must be defined in the XML as an 'Exception' with a regarding
        'WeekDay' definition.
        """
        setattr(self.msp_project, "DefaultStartTime", f"{self.DEFAULT_START_TIME}:00")
        setattr(self.msp_project, "DefaultFinishTime", f"{self.DEFAULT_FINISH_TIME}:00")
        setattr(self.msp_project, "MinutesPerDay", int(self.DEFAULT_DURATION * 60))
        setattr(self.msp_project, "MinutesPerWeek", int(self.DEFAULT_DURATION * 60 * 5))

        self.msp_project.extend(objectify.Element("Calendars"))
        self.msp_project.Calendars.extend(objectify.Element("Calendar"))
        setattr(self.msp_project.Calendars.Calendar, "Name", "Standard")

        WeekDays = objectify.Element("WeekDays")
        Exceptions = objectify.Element("Exceptions")

        for day_type in [1, 7]:  # sunday, saturday
            WeekDay = objectify.Element("WeekDay")
            setattr(WeekDay, "DayType", day_type)
            setattr(WeekDay, "DayWorking", 0)
            WeekDays.extend(WeekDay)

        for day_type in [2, 3, 4, 5, 6]:  # monday, tuesday, wednesday, thursday, friday
            WeekDay = objectify.Element("WeekDay")
            setattr(WeekDay, "DayType", day_type)
            setattr(WeekDay, "DayWorking", 1)
            WeekDay.extend(self.get_default_msp_calendar_working_times())
            WeekDays.extend(WeekDay)

        cal_name = self.pcs_project.CalendarProfile.name
        # Cut all XML and MSP critical characters from the name
        cal_name = "".join(c for c in cal_name if (c.isalnum() or c == " "))
        cal_exception_counter = 1
        for cal_exception in self.pcs_project.CalendarProfile.Exceptions:
            WeekDay = objectify.Element("WeekDay")
            setattr(WeekDay, "DayType", 0)
            TimePeriod = objectify.Element("TimePeriod")
            setattr(
                TimePeriod, "FromDate", cal_exception.day.strftime("%Y-%m-%dT00:00:00")
            )
            setattr(
                TimePeriod, "ToDate", cal_exception.day.strftime("%Y-%m-%dT23:59:00")
            )
            WeekDay.extend(TimePeriod)
            if cal_exception.day_type_id != 0:
                # A exceptional nonworking day
                setattr(WeekDay, "DayWorking", 0)
            else:
                # A exceptional day with working times
                setattr(WeekDay, "DayWorking", 1)
                WeekDay.extend(self.get_default_msp_calendar_working_times())
            WeekDays.extend(WeekDay)

            Exception_ = objectify.Element("Exception")
            setattr(Exception_, "Name", f"{cal_name}-{cal_exception_counter}")
            cal_exception_counter += 1
            setattr(Exception_, "Type", 1)
            setattr(Exception_, "Occurrences", 1)
            setattr(Exception_, "EnteredByOccurrences", 1)
            TimePeriod = objectify.Element("TimePeriod")
            setattr(
                TimePeriod, "FromDate", cal_exception.day.strftime("%Y-%m-%dT00:00:00")
            )
            setattr(
                TimePeriod, "ToDate", cal_exception.day.strftime("%Y-%m-%dT23:59:00")
            )
            Exception_.extend(TimePeriod)
            if cal_exception.day_type_id != 0:
                # An exception with nonworking days
                setattr(Exception_, "DayWorking", 0)
            else:
                # An exception with working days
                setattr(Exception_, "DayWorking", 1)
                Exception_.extend(self.get_default_msp_calendar_working_times())
            Exceptions.extend(Exception_)

        self.msp_project.Calendars.Calendar.extend(WeekDays)
        self.msp_project.Calendars.Calendar.extend(Exceptions)

    def get_default_msp_calendar_working_times(self):
        """
        The method gets called for exporting a standard calendar and is tied to the customization
        constants DEFAULT_START_TIME and DEFAULT_FINISH_TIME. By default the method also inserts a
        fixed working break of 1 hour from 12:00 to 13:00. This means that the method must be
        overwritten when requiring to export projects e.g. with a different length of the working
        break.
        """
        WorkingTimes = objectify.Element("WorkingTimes")

        WorkingTime = objectify.Element("WorkingTime")
        setattr(WorkingTime, "FromTime", f"{self.DEFAULT_START_TIME}:00")
        setattr(WorkingTime, "ToTime", "12:00:00")
        WorkingTimes.extend(WorkingTime)

        WorkingTime = objectify.Element("WorkingTime")
        setattr(WorkingTime, "FromTime", "13:00:00")
        setattr(WorkingTime, "ToTime", f"{self.DEFAULT_FINISH_TIME}:00")
        WorkingTimes.extend(WorkingTime)

        return WorkingTimes

    def traverse_task(self, pcs_task, msp_outline_level):
        """Recursively exports all PCS tasks and their relations into the MSP XML project."""
        msp_task = objectify.Element("Task")
        self.get_mapped_attrs(self.TASK_MAPPING, self.TASK_DEFAULTS, pcs_task, msp_task)
        self.get_task_links(pcs_task, msp_task)
        msp_task.OutlineLevel = msp_outline_level
        self.msp_project.Tasks.extend(msp_task)
        self.get_task_references(pcs_task, msp_task)
        for pcs_sub_task in pcs_task.OrderedSubTasks:
            self.traverse_task(pcs_sub_task, msp_outline_level + 1)

    def get_task_links(self, pcs_task, msp_task):
        for task_relation in pcs_task.PredecessorTaskRelations:
            msp_task_link = objectify.Element("PredecessorLink")
            msp_task_link.PredecessorUID = self.get_pcs_task_msp_uid(
                task_relation.PredecessorTask
            )
            msp_task_link.Type = msp_misc.PcsToMsp.TaskLinkType[task_relation.rel_type]
            # PredecessorLink.LinkLag: The amount of lag in tenths of a minute
            msp_task_link.LinkLag = (task_relation.minimal_gap or 0) * 60 * 10 * 8
            msp_task_link.LagFormat = "7"
            msp_task_link.CrossProject = "0"
            msp_task.extend(msp_task_link)

    def get_task_references(self, pcs_task, msp_task):
        """Export task reference objects (e.g. checklist) into custom msp task fields ('Text*')"""
        for function, msp_attr in self.TASK_REFERENCE_MAPPING.items():
            function = getattr(self, function)
            if ":" in msp_attr:
                msp_attr, msp_column_name = msp_attr.split(":")
            else:
                msp_column_name = None
            msp_value = function(pcs_task, msp_task, msp_attr)
            self.set_msp_object_attr(msp_task, msp_attr, msp_value, msp_column_name)

    def get_pcs_task_msp_uid(self, pcs_task):
        """Ensures that a PCS task owns an MSP task UID."""
        msp_uid = getattr(pcs_task, "msp_uid", None)
        if not msp_uid:
            self.max_msp_uid += 1
            msp_uid = self.max_msp_uid
            pcs_task["msp_uid"] = msp_uid
        return msp_uid

    def set_msp_object_attr(
        self, msp_object, msp_attr, msp_value, msp_column_name=None
    ):
        """
        Supports setting extended MSP task fields listed in
        cs.pcs.msp.miscPcsToMsp.ExtendedAttributes
        """
        if msp_attr in msp_misc.PcsToMsp.ExtendedAttributes:
            msp_extended_attribute = objectify.Element("ExtendedAttribute")
            msp_extended_attribute.FieldID = msp_misc.PcsToMsp.ExtendedAttributes[
                msp_attr
            ]
            msp_extended_attribute.Value = msp_value
            msp_object.extend(msp_extended_attribute)
            if msp_column_name:
                msp_extended_attributes = self.msp_project.xpath("ExtendedAttributes")
                if not msp_extended_attributes:
                    msp_extended_attributes = objectify.Element("ExtendedAttributes")
                    self.msp_project.extend(msp_extended_attributes)
                else:
                    msp_extended_attributes = msp_extended_attributes[0]
                msp_extended_attribute = self.msp_project.xpath(
                    "ExtendedAttributes/ExtendedAttribute/FieldID"
                    f"[text()='{msp_misc.PcsToMsp.ExtendedAttributes[msp_attr]}']/.."
                )
                if not msp_extended_attribute:
                    msp_extended_attribute = objectify.Element("ExtendedAttribute")
                    msp_extended_attribute.FieldID = (
                        msp_misc.PcsToMsp.ExtendedAttributes[msp_attr]
                    )
                    msp_extended_attribute.FieldName = msp_attr
                    msp_extended_attribute.Alias = msp_column_name
                    msp_extended_attributes.extend(msp_extended_attribute)
        else:
            setattr(msp_object, msp_attr, msp_value)

    @classmethod
    def check_export_right(
        cls, pcs_project, xml_doc=None, called_from_officelink=False
    ):
        """
        This method is called from msp officelink implementation
        """
        return all(emit(CAN_UPDATE_PROJECT)(pcs_project))
