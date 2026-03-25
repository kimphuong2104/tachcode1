#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from datetime import date

import pytest
from cdb import testcase

from cs.pcs.projects import tasks_efforts
from cs.pcs.projects.tests import common


@pytest.mark.integration
class ProjectIntegrationAggregationTestCase(testcase.RollbackTestCase):
    @staticmethod
    def generate_sub_tasks(project, parent_task=""):
        # tasks
        tasks = {
            "new": (0, 3, 0),
            "ready": (20, 5, 0),
            "execution": (50, 7, 50),
            "discarded": (180, 11, 0),
            "finished": (200, 13, 100),
            "completed": (250, 17, 100),
        }
        for key, val in tasks.items():
            kwargs = {
                "task_id": f"sub_{key}",
                "automatic": 1,
                "auto_update_time": 1,
                "effort_fcast": val[1],
                "percent_complet": val[2],
            }
            if parent_task:
                kwargs.update(parent_task=parent_task)
            t = common.generate_project_task(project, **kwargs)
            t.Update(status=val[0])

    @pytest.mark.dependency(depends=["cs.pcs.projects"])
    def test_aggregate_changes_for_project(self):
        "Project: adjust effort to sum of sub task efforts"
        # create data
        # Note: Using fixed dates, which will have a
        # defined amount of workdays between them
        start_time = date(2021, 1, 4)
        end_time = date(2021, 1, 5)
        project = common.generate_project(
            status=50,
            effort_fcast=1,
            effort_plan=0,
            auto_update_effort=1,
            start_time_act=start_time,
            end_time_act=end_time,
        )
        self.generate_sub_tasks(project)

        # call method
        tasks_efforts.aggregate_changes(project)

        # check adjustments
        project.Reload()
        self.assertEqual(45, project.effort_fcast)
        self.assertEqual(45, project.effort_plan)
        self.assertEqual(74, project.percent_complet)
        self.assertEqual(2, project.days_act)

    @pytest.mark.dependency(depends=["cs.pcs.projects"])
    def test_aggregate_changes_for_parent_task(self):
        "Task: adjust effort to sum of sub task efforts"
        # create data
        project = common.generate_project(status=50)
        parent = common.generate_project_task(
            project,
            task_id="parent",
            status=0,
            effort_fcast=1,
            effort_plan=0,
            auto_update_effort=1,
        )
        self.generate_sub_tasks(project, parent_task=parent.task_id)

        # call method
        tasks_efforts.aggregate_changes(project)

        # check adjustments
        parent.Reload()
        self.assertEqual(45, parent.effort_fcast)
        self.assertEqual(45, parent.effort_plan)
        self.assertEqual(74, parent.percent_complet)


@pytest.mark.integration
class StatusAggregationTestCase(testcase.RollbackTestCase):
    # pylint: disable=too-many-instance-attributes
    project = None
    tasks = []

    def create_project(self):
        self.project = common.generate_project(
            cdb_project_id="pid_status_test",
            project_name="Project Status Test",
            auto_update_effort=1,
            is_group=1,
        )

        # first layer
        self.t1 = common.generate_task(self.project, "t1")
        self.t2 = common.generate_task(self.project, "t2")

        # second layer
        self.t1_1 = common.generate_task(self.project, "t1_1", parent_task="t1")
        self.t1_2 = common.generate_task(self.project, "t1_2", parent_task="t1")
        self.t2_1 = common.generate_task(self.project, "t2_1", parent_task="t2")
        self.t2_2 = common.generate_task(self.project, "t2_2", parent_task="t2")

        # third layer
        self.t1_1_1 = common.generate_task(self.project, "t1_1_1", parent_task="t1_1")
        self.t1_1_2 = common.generate_task(self.project, "t1_1_2", parent_task="t1_1")
        self.t1_2_1 = common.generate_task(self.project, "t1_2_1", parent_task="t1_2")
        self.t1_2_2 = common.generate_task(self.project, "t1_2_2", parent_task="t1_2")
        self.t2_1_1 = common.generate_task(self.project, "t2_1_1", parent_task="t2_1")
        self.t2_1_2 = common.generate_task(self.project, "t2_1_2", parent_task="t2_1")
        self.t2_2_1 = common.generate_task(self.project, "t2_2_1", parent_task="t2_2")
        self.t2_2_2 = common.generate_task(self.project, "t2_2_2", parent_task="t2_2")
        self.t2_2_3 = common.generate_task(self.project, "t2_2_3", parent_task="t2_2")

        self.structure = [
            # project
            self.project,
            # first layer
            self.t1,
            self.t2,
            # second layer
            self.t1_1,
            self.t1_2,
            self.t2_1,
            self.t2_2,
            # third layer
            self.t1_1_1,
            self.t1_1_2,
            self.t1_2_1,
            self.t1_2_2,
            self.t2_1_1,
            self.t2_1_2,
            self.t2_2_1,
            self.t2_2_2,
            self.t2_2_3,
        ]

    def adjust_structure(self, attr, values):
        for i, obj in enumerate(self.structure):
            obj[attr] = values[i]

    def check_structure(self, attr, values):
        for i, obj in enumerate(self.structure):
            obj.Reload()
            self.assertEqual(
                obj[attr],
                values[i],
                f"{obj.GetDescription()}.{attr} ==> {obj[attr]} != {values[i]}",
            )

    def test_aggregation_weight_by_number(self):
        "Aggregate percentage: equal weight of tasks (weight by number)"
        self.create_project()
        percentage_input = [
            # project
            0,
            # first layer
            0,
            0,
            # second layer
            0,
            0,
            0,
            0,
            # third layer
            100,
            50,
            50,
            0,
            100,
            50,
            60,
            15,
            0,
        ]
        self.adjust_structure("percent_complet", percentage_input)
        tasks_efforts.aggregate_changes(self.project)

        # second branch has to have more weight than the first one
        percentage_output = [
            # project
            47,
            # first layer
            50,
            45,
            # second layer
            75,
            25,
            75,
            25,
            # third layer
            100,
            50,
            50,
            0,
            100,
            50,
            60,
            15,
            0,
        ]
        self.check_structure("percent_complet", percentage_output)

    def test_aggregation_weight_by_equal_effort(self):
        "Aggregate percentage: equal weight of tasks (equal effort)"
        self.create_project()
        effort_values = [
            # project
            0,
            # first layer
            0,
            0,
            # second layer
            0,
            0,
            0,
            0,
            # third layer
            10,
            10,
            10,
            10,
            10,
            10,
            10,
            10,
            10,
        ]
        self.adjust_structure("effort_fcast", effort_values)
        percentage_input = [
            # project
            0,
            # first layer
            0,
            0,
            # second layer
            0,
            0,
            0,
            0,
            # third layer
            100,
            50,
            50,
            0,
            100,
            50,
            60,
            15,
            0,
        ]
        self.adjust_structure("percent_complet", percentage_input)
        tasks_efforts.aggregate_changes(self.project)

        # second branch has to have more weight than the first one
        effort_values = [
            # project
            90,
            # first layer
            40,
            50,
            # second layer
            20,
            20,
            20,
            30,
            # third layer
            10,
            10,
            10,
            10,
            10,
            10,
            10,
            10,
            10,
        ]
        self.check_structure("effort_fcast", effort_values)
        percentage_output = [
            # project
            47,
            # first layer
            50,
            45,
            # second layer
            75,
            25,
            75,
            25,
            # third layer
            100,
            50,
            50,
            0,
            100,
            50,
            60,
            15,
            0,
        ]
        self.check_structure("percent_complet", percentage_output)

    def test_aggregation_weight_by_unequal_effort(self):
        "Aggregate percentage: equal weight of tasks (unequal effort)"
        self.create_project()
        effort_values = [
            # project
            0,
            # first layer
            0,
            0,
            # second layer
            0,
            0,
            0,
            0,
            # third layer
            200,
            80,
            0,
            20,
            30,
            10,
            30,
            20,
            10,
        ]
        self.adjust_structure("effort_fcast", effort_values)
        percentage_input = [
            # project
            0,
            # first layer
            0,
            0,
            # second layer
            0,
            0,
            0,
            0,
            # third layer
            100,
            50,
            50,
            0,
            100,
            50,
            60,
            15,
            0,
        ]
        self.adjust_structure("percent_complet", percentage_input)
        tasks_efforts.aggregate_changes(self.project)

        # second branch has to have more weight than the first one
        effort_values = [
            # project
            400,
            # first layer
            300,
            100,
            # second layer
            280,
            20,
            40,
            60,
            # third layer
            200,
            80,
            0,
            20,
            30,
            10,
            30,
            20,
            10,
        ]
        self.check_structure("effort_fcast", effort_values)
        percentage_output = [
            # project
            73,
            # first layer
            79,
            55,
            # second layer
            85,
            0,
            87,
            35,
            # third layer
            100,
            50,
            50,
            0,
            100,
            50,
            60,
            15,
            0,
        ]
        self.check_structure("percent_complet", percentage_output)

    def test_aggregation_discarded(self):
        "Aggregate percentage: ignore discarded tasks (equal weight)"
        self.create_project()
        status_values = [
            # project
            0,
            # first layer
            0,
            0,
            # second layer
            0,
            0,
            0,
            180,
            # third layer
            0,
            0,
            0,
            180,
            180,
            0,
            180,
            180,
            180,
        ]
        self.adjust_structure("status", status_values)
        percentage_input = [
            # project
            0,
            # first layer
            0,
            0,
            # second layer
            0,
            0,
            0,
            0,
            # third layer
            100,
            50,
            50,
            0,
            100,
            50,
            60,
            15,
            0,
        ]
        self.adjust_structure("percent_complet", percentage_input)
        tasks_efforts.aggregate_changes(self.project)

        # second branch has to have more weight than the first one
        percentage_output = [
            # project
            62,
            # first layer
            66,
            50,
            # second layer
            75,
            50,
            50,
            0,
            # third layer
            100,
            50,
            50,
            0,
            100,
            50,
            60,
            15,
            0,
        ]
        self.check_structure("percent_complet", percentage_output)

    def test_aggregation_discarded_and_unequal_effort(self):
        "Aggregate percentage: ignore discarded tasks (unequal effort)"
        self.create_project()
        status_values = [
            # project
            0,
            # first layer
            0,
            0,
            # second layer
            0,
            0,
            0,
            180,
            # third layer
            0,
            0,
            0,
            180,
            180,
            0,
            180,
            180,
            180,
        ]
        self.adjust_structure("status", status_values)
        effort_values = [
            # project
            0,
            # first layer
            0,
            0,
            # second layer
            0,
            0,
            0,
            0,
            # third layer
            200,
            80,
            0,
            20,
            30,
            10,
            30,
            20,
            10,
        ]
        self.adjust_structure("effort_fcast", effort_values)
        percentage_input = [
            # project
            0,
            # first layer
            0,
            0,
            # second layer
            0,
            0,
            0,
            0,
            # third layer
            100,
            50,
            50,
            0,
            100,
            50,
            60,
            15,
            0,
        ]
        self.adjust_structure("percent_complet", percentage_input)
        tasks_efforts.aggregate_changes(self.project)

        # second branch has to have more weight than the first one
        effort_values = [
            # project
            290,
            # first layer
            280,
            10,
            # second layer
            280,
            0,
            10,
            0,
            # third layer
            200,
            80,
            0,
            20,
            30,
            10,
            30,
            20,
            10,
        ]
        self.check_structure("effort_fcast", effort_values)
        percentage_output = [
            # project
            83,
            # first layer
            85,
            50,
            # second layer
            85,
            50,
            50,
            0,
            # third layer
            100,
            50,
            50,
            0,
            100,
            50,
            60,
            15,
            0,
        ]
        self.check_structure("percent_complet", percentage_output)

    def test_aggregation_discarded_and_branch_discarded(self):
        "Aggregate percentage: ignore discarded subtasks (unequal effort)"
        self.create_project()
        status_values = [
            # project
            0,
            # first layer
            0,
            0,
            # second layer
            0,
            0,
            180,
            180,
            # third layer
            0,
            0,
            0,
            180,
            180,
            180,
            180,
            180,
            180,
        ]
        self.adjust_structure("status", status_values)
        effort_values = [
            # project
            0,
            # first layer
            0,
            50,
            # second layer
            0,
            0,
            0,
            0,
            # third layer
            200,
            80,
            0,
            20,
            30,
            10,
            30,
            20,
            10,
        ]
        self.adjust_structure("effort_fcast", effort_values)
        percentage_input = [
            # project
            0,
            # first layer
            0,
            30,
            # second layer
            0,
            0,
            0,
            0,
            # third layer
            100,
            100,
            100,
            0,
            100,
            50,
            60,
            15,
            0,
        ]
        self.adjust_structure("percent_complet", percentage_input)
        tasks_efforts.aggregate_changes(self.project)

        # second branch has to have more weight than the first one
        effort_values = [
            # project
            330,
            # first layer
            280,
            50,
            # second layer
            280,
            0,
            0,
            0,
            # third layer
            200,
            80,
            0,
            20,
            30,
            10,
            30,
            20,
            10,
        ]
        self.check_structure("effort_fcast", effort_values)
        percentage_output = [
            # project
            89,
            # first layer
            100,
            30,
            # second layer
            100,
            100,
            0,
            0,
            # third layer
            100,
            100,
            100,
            0,
            100,
            50,
            60,
            15,
            0,
        ]
        self.check_structure("percent_complet", percentage_output)
