#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=protected-access

"""
Module portfolios_pcs

Schnittstellenmodul portfolio - pcs
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import datetime

from cdb.classbody import classbody

# Some imports
from cdb.objects import ByID
from cdb.typeconversion import from_legacy_date_format
from cs.portfolios import PortfolioFolder


@classbody
class PortfolioFolder:
    def _get_current_projects(self):
        from cdb.objects import Rule

        from cs.pcs.projects import Project

        rule = Rule.ByKeys(name="cdbpcs: Active Project")
        projects = [
            x
            for x in [
                Project.ByKeys(cdb_object_id=object_id)
                for object_id in self.FolderContents.cdb_content_id
            ]
            if x is not None and rule.match(x)
        ]
        return projects

    @staticmethod
    def number_of_current_projects(qc):
        self = ByID(qc.cdbf_object_id)
        result = len(self._get_current_projects()) + self._get_childern_values(qc)
        return result

    @staticmethod
    def _get_project_workdays(project, start_date, end_date):
        from cs.pcs.projects import calendar as Calendar

        def format_date(dt):
            if isinstance(dt, str):
                return from_legacy_date_format(dt)
            return dt

        return len(
            Calendar.project_workdays(
                project.cdb_project_id, format_date(start_date), format_date(end_date)
            )
        )

    # FIXME: implement the methods in Tasks.py. DO NOT USE
    # usage in configured metric (cdbqc_computation_rule)
    @staticmethod
    def effort_per_year(qc):
        self = ByID(qc.cdbf_object_id)

        year = (datetime.datetime.now() - datetime.timedelta(1)).year
        first_day = datetime.datetime(year, 1, 1)
        last_day = datetime.datetime(year, 12, 31)

        result = 0
        projects = self._get_current_projects()
        for project in projects:
            leaf_tasks = [task for task in project.Tasks if task.is_group == 0]
            for task in leaf_tasks:
                if task.start_time_fcast and task.end_time_fcast:
                    total_workdays = PortfolioFolder._get_project_workdays(
                        project, task.start_time_fcast, task.end_time_fcast
                    )

                    first_task_day = max(first_day, task.start_time_fcast)
                    last_task_day = min(last_day, task.end_time_fcast)

                    if first_task_day <= last_task_day:
                        workdays = PortfolioFolder._get_project_workdays(
                            project, first_task_day, last_task_day
                        )
                    else:
                        workdays = 0
                if total_workdays and task.effort_plan:
                    percent = workdays / float(total_workdays)
                    result += task.effort_plan * percent

        result += self._get_childern_values(qc)
        return result
