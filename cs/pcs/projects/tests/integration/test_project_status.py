#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from datetime import date

import pytest
from cdb import testcase

from cs.pcs.projects.tests import common


def setup_module():
    testcase.run_level_setup()


@pytest.mark.integration
class ProjectStatusIntegrationTestCase(testcase.RollbackTestCase):

    project = None
    tasks = []

    def reload(self):
        self.project.Reload()
        for t in self.tasks:
            t.Reload()

    def create_project(self):
        self.project = common.generate_project(
            is_group=1, effort_fcast=1.0, effort_act=1, days_fcast=1
        )
        t1 = common.generate_task(
            self.project, "top_task1", effort_fcast=3.0, effort_act=3.0, days_fcast=3
        )
        t2 = common.generate_task(
            self.project, "top_task2", effort_fcast=5.0, effort_act=5.0, days_fcast=5
        )
        t3 = common.generate_task(
            self.project, "top_task3", effort_fcast=7.0, effort_act=7.0, days_fcast=7
        )
        t4 = common.generate_task(
            self.project,
            "sub_task1",
            parent_task="top_task1",
            effort_fcast=11.0,
            effort_act=11,
            days_fcast=11,
        )
        t5 = common.generate_task(
            self.project,
            "sub_task2",
            parent_task="top_task1",
            effort_fcast=13.0,
            effort_act=13.0,
            days_fcast=13,
        )
        t6 = common.generate_task(
            self.project,
            "sub_task3",
            parent_task="top_task2",
            effort_fcast=17.0,
            effort_act=17.0,
            days_fcast=17,
        )
        common.generate_task_relation(t1, t2)
        common.generate_task_relation(t2, t3)
        common.generate_task_relation(t4, t5)
        self.tasks = [t1, t2, t3, t4, t5, t6]

    def start_project(self, *others):
        self.project.Reload()
        for t in self.project.Tasks:
            t.Reload()
        self.project.ChangeState(50)
        self.project.Reload()
        for other in others:
            other.Reload()

    def set_automation_attributes(self, automatic, update_time, update_effort):
        self.project.Update(
            auto_update_time=update_time, auto_update_effort=update_effort
        )
        self.project.Tasks.Update(
            auto_update_time=update_time,
            auto_update_effort=update_effort,
            automatic=automatic,
        )

    def test_change_status_of_project_01(self):
        "Change project status from NEW to EXECUTION; auto updates active"
        self.create_project()
        self.set_automation_attributes(True, 1, True)
        self.start_project()

        self.assertEqual(self.project.effort_fcast, 48.0)
        self.assertEqual(self.project.effort_plan, 48.0)
        self.assertEqual(self.project.effort_act, 48.0)
        self.assertEqual(self.project.percent_complet, 0)

    def test_change_status_of_project_02(self):
        "Change project status from NEW to EXECUTION; auto updates inactive"
        self.create_project()
        self.set_automation_attributes(False, 0, False)
        self.start_project()

        self.assertEqual(self.project.effort_fcast, 1.0)
        self.assertEqual(self.project.effort_plan, 48.0)
        self.assertEqual(self.project.effort_act, 48.0)
        self.assertEqual(self.project.percent_complet, 0)

    def test_change_status_of_project_03(self):
        # pylint: disable=too-many-statements
        "Change task status from READY to DISCARDED; auto updates active"
        self.create_project()
        self.set_automation_attributes(True, 1, True)
        task_1 = self.tasks[0]
        task_2 = self.tasks[1]
        task_3 = self.tasks[2]
        task_1_1 = self.tasks[3]
        task_1_2 = self.tasks[4]
        task_2_1 = self.tasks[5]
        self.start_project(*self.tasks)

        self.assertEqual(self.project.effort_fcast, 48.0)
        self.assertEqual(self.project.effort_plan, 48.0)
        self.assertEqual(self.project.effort_act, 48.0)
        self.assertEqual(self.project.days, 17)
        self.assertEqual(self.project.percent_complet, 0)

        self.assertEqual(task_1.days, None)
        self.assertEqual(task_1.percent_complet, 0)
        self.assertEqual(task_1.effort_fcast, 24.0)
        self.assertEqual(task_1.effort_plan, 24.0)
        self.assertEqual(task_1.effort_act, 24.0)

        self.assertEqual(task_2.effort_fcast, 17.0)
        self.assertEqual(task_2.effort_plan, 17.0)
        self.assertEqual(task_2.effort_act, 17.0)
        self.assertEqual(task_2.days, None)
        self.assertEqual(task_2.percent_complet, 0)

        self.assertEqual(task_3.effort_fcast, 7.0)
        self.assertEqual(task_3.effort_plan, 7.0)
        self.assertEqual(task_3.effort_act, 7.0)
        self.assertEqual(task_3.days, None)
        self.assertEqual(task_3.percent_complet, None)

        self.assertEqual(task_1_1.effort_fcast, 11.0)
        self.assertEqual(task_1_1.effort_plan, 11.0)
        self.assertEqual(task_1_1.effort_act, 11.0)
        self.assertEqual(task_1_1.days, None)
        self.assertEqual(task_1_1.percent_complet if task_1_1.percent_complet else 0, 0)

        self.assertEqual(task_1_2.effort_fcast, 13.0)
        self.assertEqual(task_1_2.effort_plan, 13.0)
        self.assertEqual(task_1_2.effort_act, 13.0)
        self.assertEqual(task_1_2.days, None)
        self.assertEqual(task_1_2.percent_complet, None)

        self.assertEqual(task_2_1.effort_fcast, 17.0)
        self.assertEqual(task_2_1.effort_plan, 17.0)
        self.assertEqual(task_2_1.effort_act, 17.0)
        self.assertEqual(task_2_1.days, None)
        self.assertEqual(task_2_1.percent_complet, None)

        # set first top task to DISCARDED
        # and set second top task to EXECUTION
        task_1.ChangeState(180)
        self.project.Reload()
        task_1.Reload()

        # aggregated value of project ignores the discared tasks
        self.assertEqual(self.project.effort_fcast, 24.0)
        self.assertEqual(self.project.effort_plan, 24.0)
        self.assertEqual(self.project.effort_act, 48.0)
        self.assertEqual(self.project.days, 17)

        self.assertEqual(self.project.percent_complet, 0)

        # discarded parent task has special aggregation for days
        self.assertEqual(task_1.effort_fcast, 24.0)
        self.assertEqual(task_1.effort_plan, 24.0)
        self.assertEqual(task_1.effort_act, 24.0)
        self.assertEqual(task_1.days, None)
        self.assertEqual(task_1.percent_complet, 0)

        self.assertEqual(task_1.effort_fcast, 24.0)
        self.assertEqual(task_1.effort_plan, 24.0)
        self.assertEqual(task_1.effort_act, 24.0)

        # other values are not changed
        self.assertEqual(task_2.effort_fcast, 17.0)
        self.assertEqual(task_2.effort_plan, 17.0)
        self.assertEqual(task_2.effort_act, 17.0)
        self.assertEqual(task_2.days, None)
        self.assertEqual(task_2.percent_complet, 0)

        self.assertEqual(task_3.effort_fcast, 7.0)
        self.assertEqual(task_3.effort_plan, 7.0)
        self.assertEqual(task_3.effort_act, 7.0)
        self.assertEqual(task_3.days, None)
        self.assertEqual(task_3.percent_complet, None)

        self.assertEqual(task_1_1.effort_fcast, 11.0)
        self.assertEqual(task_1_1.effort_plan, 11.0)
        self.assertEqual(task_1_1.effort_act, 11.0)
        self.assertEqual(task_1_1.days, None)
        self.assertEqual(task_1_1.percent_complet if task_1_1.percent_complet else 0, 0)

        self.assertEqual(task_1_2.effort_fcast, 13.0)
        self.assertEqual(task_1_2.effort_plan, 13.0)
        self.assertEqual(task_1_2.effort_act, 13.0)
        self.assertEqual(task_1_2.days, None)
        self.assertEqual(task_1_2.percent_complet, None)

        self.assertEqual(task_2_1.effort_fcast, 17.0)
        self.assertEqual(task_2_1.effort_plan, 17.0)
        self.assertEqual(task_2_1.effort_act, 17.0)
        self.assertEqual(task_2_1.days, None)
        self.assertEqual(task_2_1.percent_complet, None)

    def test_aa_successor_not_ready_on_project_start(self):
        "Regression test for E066433"
        self.project = common.generate_project()
        t1 = common.generate_task(self.project, "top_task1")
        t2 = common.generate_task(self.project, "top_task2")
        common.generate_task_relation(t1, t2, rel_type="AA")
        self.start_project(t1, t2)
        self.assertEqual(
            [self.project.status, t1.status, t2.status],
            [50, 20, 0],
        )

    def check_dates(self, obj, start, end):
        self.assertEqual(obj.start_time_fcast, start)
        self.assertEqual(obj.end_time_fcast, end)

    def test_discarded_predecessors_tasks(self):
        """Discard tasks: check positioning of predecessors and successors

        Task Structure:

        | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 |
        [        Task 1          ]
                                 |
                                 v
        [        Task 2          ]----------v
                                            [       Task 3          ]----------v
                                                                               [       Task 4        ]-
                                                                                                      |
                                                                                              ---------
                                                                                              |
                                                                                              ---> [M1]
        """
        self.project = common.generate_project(
            start_time_fcast=date(2022, 8, 1),
            end_time_fcast=date(2022, 8, 5),
            days_fcast=5,
        )
        t1 = common.generate_task(self.project, "t_1", days_fcast=5, automatic=1)
        t2 = common.generate_task(self.project, "t_2", days_fcast=5, automatic=1)
        t3 = common.generate_task(self.project, "t_3", days_fcast=5, automatic=1)
        t4 = common.generate_task(self.project, "t_4", days_fcast=5, automatic=1)
        m1 = common.generate_task(
            self.project, "m_1", milestone=1, start_is_early=0, automatic=1
        )
        self.tasks = [t1, t2, t3, t4, m1]
        common.generate_task_relation(t1, t2, rel_type="EE")
        common.generate_task_relation(t2, t3, rel_type="EA")
        common.generate_task_relation(t3, t4, rel_type="EA")
        common.generate_task_relation(t4, m1, rel_type="EA")

        self.reload()
        self.check_dates(t1, date(2022, 8, 1), date(2022, 8, 5))
        self.check_dates(t2, date(2022, 8, 1), date(2022, 8, 5))
        self.check_dates(t3, date(2022, 8, 8), date(2022, 8, 12))
        self.check_dates(t4, date(2022, 8, 15), date(2022, 8, 19))
        self.check_dates(m1, date(2022, 8, 19), date(2022, 8, 19))

        t2.ChangeState(180)
        self.reload()
        self.check_dates(t1, date(2022, 8, 1), date(2022, 8, 5))
        self.check_dates(t2, date(2022, 8, 1), date(2022, 8, 5))
        self.check_dates(t3, date(2022, 8, 8), date(2022, 8, 12))
        self.check_dates(t4, date(2022, 8, 15), date(2022, 8, 19))
        self.check_dates(m1, date(2022, 8, 19), date(2022, 8, 19))

        t3.ChangeState(180)
        self.reload()
        self.check_dates(t1, date(2022, 8, 1), date(2022, 8, 5))
        self.check_dates(t2, date(2022, 8, 1), date(2022, 8, 5))
        self.check_dates(t3, date(2022, 8, 8), date(2022, 8, 12))
        self.check_dates(t4, date(2022, 8, 8), date(2022, 8, 12))
        self.check_dates(m1, date(2022, 8, 12), date(2022, 8, 12))

    def test_discarded_predecessors_milestones(self):
        "Discard milestones: check positioning of predecessors and successors"
        self.project = common.generate_project(
            start_time_fcast=date(2022, 8, 1),
            end_time_fcast=date(2022, 8, 5),
            days_fcast=5,
        )
        t1 = common.generate_task(self.project, "t_1", days_fcast=5, automatic=1)
        t2 = common.generate_task(
            self.project, "t_2", milestone=1, start_is_early=0, automatic=1
        )
        t3 = common.generate_task(
            self.project, "t_3", milestone=1, start_is_early=0, automatic=1
        )
        t4 = common.generate_task(self.project, "t_4", days_fcast=5, automatic=1)
        m1 = common.generate_task(
            self.project, "m_1", milestone=1, start_is_early=0, automatic=1
        )
        self.tasks = [t1, t2, t3, t4, m1]
        common.generate_task_relation(t1, t2, rel_type="EE")
        common.generate_task_relation(t2, t3, rel_type="EA")
        common.generate_task_relation(t3, t4, rel_type="EA")
        common.generate_task_relation(t4, m1, rel_type="EA")

        self.reload()
        self.check_dates(t1, date(2022, 8, 1), date(2022, 8, 5))
        self.check_dates(t2, date(2022, 8, 5), date(2022, 8, 5))
        self.check_dates(t3, date(2022, 8, 5), date(2022, 8, 5))
        self.check_dates(t4, date(2022, 8, 8), date(2022, 8, 12))
        self.check_dates(m1, date(2022, 8, 12), date(2022, 8, 12))

        t2.ChangeState(180)
        self.reload()
        self.check_dates(t1, date(2022, 8, 1), date(2022, 8, 5))
        self.check_dates(t2, date(2022, 8, 5), date(2022, 8, 5))
        self.check_dates(t3, date(2022, 8, 5), date(2022, 8, 5))
        self.check_dates(t4, date(2022, 8, 8), date(2022, 8, 12))
        self.check_dates(m1, date(2022, 8, 12), date(2022, 8, 12))

        t3.ChangeState(180)
        self.reload()
        self.check_dates(t1, date(2022, 8, 1), date(2022, 8, 5))
        self.check_dates(t2, date(2022, 8, 5), date(2022, 8, 5))
        self.check_dates(t3, date(2022, 8, 5), date(2022, 8, 5))
        self.check_dates(t4, date(2022, 8, 8), date(2022, 8, 12))
        self.check_dates(m1, date(2022, 8, 12), date(2022, 8, 12))
