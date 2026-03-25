#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=pointless-string-statement

from datetime import date

import mock
import pytest
from cdb import testcase

from cs.pcs.projects.tests import common_data
from cs.pcs.scheduling import scheduling
from cs.pcs.scheduling.tests.integration import ScheduleTestCase

ASAP, ALAP = "01"
MSO = "2"


def setup_module():
    testcase.run_level_setup()


@pytest.mark.dependency(depends=["schedule"])
@pytest.mark.integration
class NestedTaskGroups(ScheduleTestCase):
    def _setup_nested_groups(self):
        self.b.Update(parent_task=self.a.task_id)
        self.a.Update(is_group=1)
        self.c = self.add_child(self.b, "C", date(2016, 9, 1), date(2016, 9, 5), 3)
        self.d = self.add_child(self.c, "D", date(2016, 9, 1), date(2016, 9, 5), 3)
        self.e = self.create_task(
            self.a.cdb_project_id, "", "E", date(2016, 9, 1), date(2016, 9, 5), 3
        )

        for task in [self.a, self.b, self.c, self.d, self.e]:
            self.set_task_duration(task, 3)
            self.schedule_automatically(task, ASAP)

    def test_simple(self):
        """
        Tests a stripped-down version of some perf tests' setup (like ProjectTaskModifyBench)

        If this fails due to instable scheduling, run pytest --log-level INFO <this_file>
        to see intermediate scheduling results.

        The project is structured like this:

        - on each level, we have 2 FS-connected task groups
        - on the last level, we have 2 FS-connected regular tasks
        - we have 3 levels in total (not counting the root level)

        00 -FS-> 15
            01 -FS-> 08
                02 -FS-> 05
                    03 -FS-> 04
                    04
                05
                    06 -FS-> 07
                    07
            08
                09 -FS-> 12
                    10 -FS-> 11
                    11
                12
                    13 -FS-> 14
                    14
        15
            16 -FS-> 23
                17 -FS-> 20
                    18 -FS-> 19
                    19
                20
                    21 -FS-> 22
                    22
            23
                24 -FS-> 27
                    25 -FS-> 26
                    26
                27
                    28 -FS-> 29
                    29

        .  00  02  04  06  08  10  12  14  16  18  20  22  24  26  28  30
        00 ████████████████████████████████
        01 ████████████████
        02 ████████
        03 ████
        04     ████
        05         ████████
        06         ████
        07             ████
        08                 ████████████████
        09                 ████████
        10                 ████
        11                     ████
        12                         ████████
        13                         ████
        14                             ████
        15                                 ████████████████████████████████
        16                                 ████████████████
        17                                 ████████
        18                                 ████
        19                                     ████
        20                                         ████████
        21                                         ████
        22                                             ████
        23                                                 ████████████████
        24                                                 ████████
        25                                                 ████
        26                                                     ████
        27                                                         ████████
        28                                                         ████
        29                                                             ████
        .  01  04  05  06  07  08  11  12  13  14  15  18  19  20  21  22   Jan 2010
        """
        self.project, _ = common_data.create_structured_project(
            "Ptest.nested",
            tasks_per_level=2,
            depth=3,
            with_dates=True,
            cluster_size=5,
        )
        self.project.AllTasks.Update(start_time_plan=None, end_time_plan=None)
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "Ptest.nested_00000": [15, 0, 15, 0, 15, 0, 15, 0, 0],
                "Ptest.nested_00001": [7, 0, 7, 0, 7, 0, 7, 0, 0],
                "Ptest.nested_00002": [3, 0, 3, 0, 3, 0, 3, 0, 0],
                "Ptest.nested_00003": [1, 0, 1, 0, 1, 0, 1, 0, 0],
                "Ptest.nested_00004": [1, 2, 3, 2, 3, 2, 3, 0, 0],
                "Ptest.nested_00005": [3, 4, 7, 4, 7, 4, 7, 0, 0],
                "Ptest.nested_00006": [1, 4, 5, 4, 5, 4, 5, 0, 0],
                "Ptest.nested_00007": [1, 6, 7, 6, 7, 6, 7, 0, 0],
                "Ptest.nested_00008": [7, 8, 15, 8, 15, 8, 15, 0, 0],
                "Ptest.nested_00009": [3, 8, 11, 8, 11, 8, 11, 0, 0],
                "Ptest.nested_00010": [1, 8, 9, 8, 9, 8, 9, 0, 0],
                "Ptest.nested_00011": [1, 10, 11, 10, 11, 10, 11, 0, 0],
                "Ptest.nested_00012": [3, 12, 15, 12, 15, 12, 15, 0, 0],
                "Ptest.nested_00013": [1, 12, 13, 12, 13, 12, 13, 0, 0],
                "Ptest.nested_00014": [1, 14, 15, 14, 15, 14, 15, 0, 0],
                "Ptest.nested_00015": [15, 16, 31, 16, 31, 16, 31, 0, 0],
                "Ptest.nested_00016": [7, 16, 23, 16, 23, 16, 23, 0, 0],
                "Ptest.nested_00017": [3, 16, 19, 16, 19, 16, 19, 0, 0],
                "Ptest.nested_00018": [1, 16, 17, 16, 17, 16, 17, 0, 0],
                "Ptest.nested_00019": [1, 18, 19, 18, 19, 18, 19, 0, 0],
                "Ptest.nested_00020": [3, 20, 23, 20, 23, 20, 23, 0, 0],
                "Ptest.nested_00021": [1, 20, 21, 20, 21, 20, 21, 0, 0],
                "Ptest.nested_00022": [1, 22, 23, 22, 23, 22, 23, 0, 0],
                "Ptest.nested_00023": [7, 24, 31, 24, 31, 24, 31, 0, 0],
                "Ptest.nested_00024": [3, 24, 27, 24, 27, 24, 27, 0, 0],
                "Ptest.nested_00025": [1, 24, 25, 24, 25, 24, 25, 0, 0],
                "Ptest.nested_00026": [1, 26, 27, 26, 27, 26, 27, 0, 0],
                "Ptest.nested_00027": [3, 28, 31, 28, 31, 28, 31, 0, 0],
                "Ptest.nested_00028": [1, 28, 29, 28, 29, 28, 29, 0, 0],
                "Ptest.nested_00029": [1, 30, 31, 30, 31, 30, 31, 0, 0],
            }
        )

    def test_change_duration(self):
        """
        Setup:
            - A is a task group with child B
            - B is a task group with child C
            - C is a task group with child D
            - D is a regular task
            - E is another regular task
            - A -FS-> E
            - All tasks scheduled ASAP, durations are three days each

        Initial Schedule:
            . 00  02  04  06  08  10
            A ████████████             A (task group with child B)
            B ████████████             B (task group with child C)
            C ████████████             C (task group with child D)
            D ████████████             D
            E             ████████████ E Successor of A
            . 26  29  30  31  01  02   Sep 2016

        Now the duration of D is reduced to 2 days.

        After changing the 1st task group:
            . 00  02  04  06  08  10
            A ████████████             A Group with child B
            B ████████████             B Group with child C
            C ████████                 C Group with child D
            D ████████                 D
            E             ████████████ E Successor of A
            . 26  29  30  31  01  02   Sep 2016

        After changing the 2nd task group:
            . 00  02  04  06  08  10
            A ████████████             A
            B ████████                 B
            C ████████                 C
            D ████████                 D
            E             ████████████ E
            . 26  29  30  31  01  02   Sep 2016

        After changing the 3rd task group:
            . 00  02  04  06  08  10
            A ████████                 A
            B ████████                 B
            C ████████                 C
            D ████████                 D
            E             ████████████ E
            . 26  29  30  31  01  02   Sep 2016

        Now the successor can be scheduled earlier:
            . 00  02  04  06  08  10
            A ████████                 A
            B ████████                 B
            C ████████                 C
            D ████████                 D
            E         ████████████     E
            . 26  29  30  31  01  02   Sep 2016

        Changing all three task groups should happen in a single step.
        The forward and backward pass schould run no more than two times.
        """
        self._setup_nested_groups()
        self.link_tasks("EA", self.a, self.e)
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 0, 5, 0, 5, 0, 5, 0, 0],
                "B": [5, 0, 5, 0, 5, 0, 5, 0, 0],
                "C": [5, 0, 5, 0, 5, 0, 5, 0, 0],
                "D": [5, 0, 5, 0, 5, 0, 5, 0, 0],
                "E": [5, 6, 11, 6, 11, 6, 11, 0, 0],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 8, 26), date(2016, 8, 30)],
                [self.b, date(2016, 8, 26), date(2016, 8, 30)],
                [self.c, date(2016, 8, 26), date(2016, 8, 30)],
                [self.d, date(2016, 8, 26), date(2016, 8, 30)],
                [self.e, date(2016, 8, 31), date(2016, 9, 2)],
            ]
        )
        self.set_task_duration(self.d, 2)

        with (
            mock.patch.object(
                scheduling, "forward_pass", wraps=scheduling.forward_pass
            ) as forward_pass,
            mock.patch.object(
                scheduling, "backward_pass", wraps=scheduling.backward_pass
            ) as backward_pass,
        ):
            self.schedule_project()

        self.assertNetworkEqual(
            {
                "A": [3, 0, 3, 0, 3, 0, 3, 0, 0],
                "B": [3, 0, 3, 0, 3, 0, 3, 0, 0],
                "C": [3, 0, 3, 0, 3, 0, 3, 0, 0],
                "D": [3, 0, 3, 0, 3, 0, 3, 0, 0],
                "E": [5, 4, 9, 4, 9, 4, 9, 0, 0],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 8, 26), date(2016, 8, 29)],
                [self.b, date(2016, 8, 26), date(2016, 8, 29)],
                [self.c, date(2016, 8, 26), date(2016, 8, 29)],
                [self.d, date(2016, 8, 26), date(2016, 8, 29)],
                [self.e, date(2016, 8, 30), date(2016, 9, 1)],
            ]
        )
        self.assertEqual((forward_pass.call_count, backward_pass.call_count), (2, 1))

    def test_add_constraint_date(self):
        """
        Setup:
            - A is a task group with child B
            - B is a task group with child C
            - C is a task group with children D and E
            - D is a regular task
            - E is another regular task
            - D -FS-> E
            - All tasks scheduled ASAP, durations are three days each

        Initial Schedule:
            . 00  02  04  06  08  10
            A ████████████████████████ A (task group with child B)
            B ████████████████████████ B (task group with child C)
            C ████████████████████████ C (task group with children D and E)
            D ████████████             D
            E             ████████████ E Successor of D
            . 26  29  30  31  01  02   Sep 2016

        Now D is constrained MSO 29.08.2016:

            . 00  02  04  06  08  10  12
            A     ████████████████████████ A
            B     ████████████████████████ B
            C     ████████████████████████ C
            D     ████████████             D
            E                 ████████████ E
            . 26  29  30  31  01  02  05   Sep 2016

        Changing all three task groups should happen in a single step.
        The forward and backward pass schould run no more than two times.
        """
        self._setup_nested_groups()
        self.e.Update(parent_task=self.c.task_id)
        self.link_tasks("EA", self.d, self.e)
        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [11, 0, 11, 0, 11, 0, 11, 0, 0],
                "B": [11, 0, 11, 0, 11, 0, 11, 0, 0],
                "C": [11, 0, 11, 0, 11, 0, 11, 0, 0],
                "D": [5, 0, 5, 0, 5, 0, 5, 0, 0],
                "E": [5, 6, 11, 6, 11, 6, 11, 0, 0],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 8, 26), date(2016, 9, 2)],
                [self.b, date(2016, 8, 26), date(2016, 9, 2)],
                [self.c, date(2016, 8, 26), date(2016, 9, 2)],
                [self.d, date(2016, 8, 26), date(2016, 8, 30)],
                [self.e, date(2016, 8, 31), date(2016, 9, 2)],
            ]
        )

        self.schedule_automatically(self.d, MSO, date(2016, 8, 29))

        with (
            mock.patch.object(
                scheduling, "forward_pass", wraps=scheduling.forward_pass
            ) as forward_pass,
            mock.patch.object(
                scheduling, "backward_pass", wraps=scheduling.backward_pass
            ) as backward_pass,
        ):
            self.schedule_project()

        self.assertNetworkEqual(
            {
                "A": [11, 2, 13, 2, 13, 2, 13, 0, 0],
                "B": [11, 2, 13, 2, 13, 2, 13, 0, 0],
                "C": [11, 2, 13, 2, 13, 2, 13, 0, 0],
                "D": [5, 2, 7, 2, 7, 2, 7, 0, 0],
                "E": [5, 8, 13, 8, 13, 8, 13, 0, 0],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 8, 29), date(2016, 9, 5)],
                [self.b, date(2016, 8, 29), date(2016, 9, 5)],
                [self.c, date(2016, 8, 29), date(2016, 9, 5)],
                [self.d, date(2016, 8, 29), date(2016, 8, 31)],
                [self.e, date(2016, 9, 1), date(2016, 9, 5)],
            ]
        )
        self.assertEqual((forward_pass.call_count, backward_pass.call_count), (2, 1))

    def test_add_constraint_date_to_second_child(self):
        """
        Setup:
            - A is a task group with children B and C
            - D is a task group with children E and F
            - B -FS-> C
            - E -FS-> F
            - A -FS-> D
            - All tasks scheduled ASAP, durations are one day each

            This leads to the following initial scheduling:

            . -4  -2  00  02  04  06  08  10  12  14
            A         ████████████████                 A
            B         ████████                         B
            C                 ████████                 C
            D                         ████████████████ D
            E                         ████████         E
            F                                 ████████ F
            . 24  25  26  29  30  31  01  02  05  06   Sep 2016

        Test: We now pull C forward by adding the constraint "MSO -04" to it.
        This is the network after the first scheduling run:

            . -4  -2  00  02  04  06  08  10  12  14
            A ████████████████                         A
            B         ████████                         B
            C ████████                                 C
            D                         ████████████████ D
            E                         ████████         E
            F                                 ████████ F
            . 24  25  26  29  30  31  01  02  05  06   Sep 2016

        A is changed due to aggregating children,
        which triggers a second run:

            . -4  -2  00  02  04  06  08  10  12  14
            A ████████                                 A
            B ████████                                 B
            C ████████                                 C
            D                 ████████████████         D
            E                 ████████                 E
            F                         ████████         F
            . 24  25  26  29  30  31  01  02  05  06   Sep 2016

        Again, A is changed due to aggregating children.
        We need a third run:

            . -4  -2  00  02  04  06  08  10  12  14
            A ████████                                 A
            B ████████                                 B
            C ████████                                 C
            D         ████████████████                 D
            E         ████████                         E
            F                 ████████                 F
            . 24  25  26  29  30  31  01  02  05  06   Sep 2016

        Now everything has settled and we're done.
        Note that the relship B -FS-> C is violated due to the constraint.
        This can be resolved by either manually setting the project start earlier
        or relaxing the constraint.
        """
        self.a.Update(start_time_fcast=None, end_time_fcast=None)
        self.b.Update(
            parent_task=self.a.task_id,
            start_time_fcast=None,
            end_time_fcast=None,
            days_fcast=2,
        )
        self.c = self.add_child(self.a, "C", None, None, 2)
        self.d = self.create_task(self.project.cdb_project_id, "", "D", None, None, 2)
        self.e = self.add_child(self.d, "E", None, None, 2)
        self.f = self.add_child(self.d, "F", None, None, 2)
        for t in self.project.Tasks:
            self.set_task_duration(t, 2)
            self.schedule_automatically(t, ASAP)
        self.link_tasks("EA", self.b, self.c)
        self.link_tasks("EA", self.e, self.f)
        self.link_tasks("EA", self.a, self.d)

        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [7, 0, 7, 0, 7, 0, 7, 0, 0],
                "B": [3, 0, 3, 0, 3, 0, 3, 0, 0],
                "C": [3, 4, 7, 4, 7, 4, 7, 0, 0],
                "D": [7, 8, 15, 8, 15, 8, 15, 0, 0],
                "E": [3, 8, 11, 8, 11, 8, 11, 0, 0],
                "F": [3, 12, 15, 12, 15, 12, 15, 0, 0],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 8, 26), date(2016, 8, 31)],
                [self.b, date(2016, 8, 26), date(2016, 8, 29)],
                [self.c, date(2016, 8, 30), date(2016, 8, 31)],
                [self.d, date(2016, 9, 1), date(2016, 9, 6)],
                [self.e, date(2016, 9, 1), date(2016, 9, 2)],
                [self.f, date(2016, 9, 5), date(2016, 9, 6)],
            ]
        )
        # Add Constraint "C MSO -04"
        self.schedule_automatically(self.c, MSO, date(2016, 8, 24))

        # Do not expect too many reruns
        with (
            mock.patch.object(
                scheduling, "forward_pass", wraps=scheduling.forward_pass
            ) as forward_pass,
            mock.patch.object(
                scheduling, "backward_pass", wraps=scheduling.backward_pass
            ) as backward_pass,
        ):
            self.schedule_project()

        self.assertNetworkEqual(
            {
                "A": [3, -4, -1, -4, -1, -4, -1, 0, 0],
                "B": [3, -4, -1, -4, -1, -4, -1, 0, 0],
                "C": [3, -4, -1, -4, -1, -4, -1, 0, 0],
                "D": [7, 0, 7, 0, 7, 0, 7, 0, 0],
                "E": [3, 0, 3, 0, 3, 0, 3, 0, 0],
                "F": [3, 4, 7, 4, 7, 4, 7, 0, 0],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 8, 24), date(2016, 8, 25)],
                [self.b, date(2016, 8, 24), date(2016, 8, 25)],
                [self.c, date(2016, 8, 24), date(2016, 8, 25)],
                [self.d, date(2016, 8, 26), date(2016, 8, 31)],
                [self.e, date(2016, 8, 26), date(2016, 8, 29)],
                [self.f, date(2016, 8, 30), date(2016, 8, 31)],
            ]
        )
        self.assertEqual((forward_pass.call_count, backward_pass.call_count), (3, 1))

    def test_with_connected_children(self):
        """
        Setup:
            - A is task group with subtasks B, C
            - D is task group with subtasks E, F

        . 00  02  04
        A ███████████ A
        B ███████████ B
        C ███████████ C
        D ███████████ D
        E ███████████ E
        F ███████████ F
        . 26  29  30  Aug 2016

        Add Relation C -FS-> E

        . 00  02  04  06  08  10
        A ████████████             A
        B ████████████             B
        C ████████████             C
        D ████████████████████████ D
        E             ████████████ E
        F ████████████             F
        . 26  29  30  31  01  02   Aug 2016
        """
        self.a.Update(start_time_fcast=None, end_time_fcast=None)
        self.b.Update(
            parent_task=self.a.task_id, start_time_fcast=None, end_time_fcast=None
        )
        self.c = self.add_child(self.a, "C", None, None, 3)
        self.d = self.create_task(self.project.cdb_project_id, "", "D", None, None, 3)
        self.e = self.add_child(self.d, "E", None, None, 3)
        self.f = self.add_child(self.d, "F", None, None, 3)
        for t in self.project.Tasks:
            self.set_task_duration(t, 3)
            self.schedule_automatically(t, ASAP)

        self.schedule_project()
        self.assertNetworkEqual(
            {
                "A": [5, 0, 5, 0, 5, 0, 5, 0, 0],
                "B": [5, 0, 5, 0, 5, 0, 5, 0, 0],
                "C": [5, 0, 5, 0, 5, 0, 5, 0, 0],
                "D": [5, 0, 5, 0, 5, 0, 5, 0, 0],
                "E": [5, 0, 5, 0, 5, 0, 5, 0, 0],
                "F": [5, 0, 5, 0, 5, 0, 5, 0, 0],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 8, 26), date(2016, 8, 30)],
                [self.b, date(2016, 8, 26), date(2016, 8, 30)],
                [self.c, date(2016, 8, 26), date(2016, 8, 30)],
                [self.d, date(2016, 8, 26), date(2016, 8, 30)],
                [self.e, date(2016, 8, 26), date(2016, 8, 30)],
                [self.f, date(2016, 8, 26), date(2016, 8, 30)],
            ]
        )

        self.link_tasks("EA", self.c, self.e)

        # Do not expect too many reruns
        with (
            mock.patch.object(
                scheduling, "forward_pass", wraps=scheduling.forward_pass
            ) as forward_pass,
            mock.patch.object(
                scheduling, "backward_pass", wraps=scheduling.backward_pass
            ) as backward_pass,
        ):
            self.schedule_project()

        self.assertNetworkEqual(
            {
                "A": [5, 0, 5, 0, 11, 0, 5, 0, 0],
                "B": [5, 0, 5, 6, 11, 0, 5, 0, 6],
                "C": [5, 0, 5, 0, 5, 0, 5, 0, 0],
                "D": [11, 0, 11, 6, 11, 0, 11, 6, 6],
                "E": [5, 6, 11, 6, 11, 6, 11, 0, 0],
                "F": [5, 0, 5, 6, 11, 0, 5, 5, 6],
            }
        )
        self.assert_dates(
            [
                [self.a, date(2016, 8, 26), date(2016, 8, 30)],
                [self.b, date(2016, 8, 26), date(2016, 8, 30)],
                [self.c, date(2016, 8, 26), date(2016, 8, 30)],
                [self.d, date(2016, 8, 26), date(2016, 9, 2)],
                [self.e, date(2016, 8, 31), date(2016, 9, 2)],
                [self.f, date(2016, 8, 26), date(2016, 8, 30)],
            ]
        )
        self.assertEqual((forward_pass.call_count, backward_pass.call_count), (2, 1))
