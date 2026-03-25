#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


import unittest

from cdb import testcase

from cs.pcs.projects.tests.common import generate_project, generate_task
from cs.pcs.projects.updates import v15_6_2_13


class UpdateDiscardedTaskGroups(testcase.RollbackTestCase):
    def _setup_data(self):
        """
        PROJECT
            DISCARDED TASKGROUP 0
                FINISHED TASK
            DISCARDED TASKGROUP 1
                COMPLETED TASK
            DISCARDED TASKGROUP 2
                DISCARDED TASK
        """
        self.project = generate_project(status=v15_6_2_13.Project.EXECUTION.status)
        self.groups = [
            generate_task(self.project, f"GROUP {index}", is_group=1)
            for index in range(3)
        ]

        for index, (parent, status) in enumerate(
            [
                ("GROUP 0", v15_6_2_13.Task.FINISHED.status),
                ("GROUP 1", v15_6_2_13.Task.COMPLETED.status),
                ("GROUP 2", v15_6_2_13.Task.DISCARDED.status),
            ]
        ):
            task = generate_task(self.project, f"SUBTASK {index}", parent_task=parent)
            task.Update(status=status)

        for group in self.groups:
            group.Update(status=v15_6_2_13.Task.DISCARDED.status)

    def test_run(self):
        self._setup_data()

        with testcase.max_sql(4):
            # 4 SQL statements:
            # 1. identify UUIDs of tasks to update
            # 2. update task statuses in on3 stmt
            # 3. insert protocol entry for "GROUP 0"
            # 4. insert protocol entry for "GROUP 1"
            # ("GROUP 2" is not updated, thus no protocol entry is made)
            self.assertIsNone(v15_6_2_13.UpdateDiscardedTaskGroups().run())

        values = []

        for x in self.groups:
            x.Reload()
            values.append((x.task_id, x.status, len(x.StatusProtocol)))

        self.assertEqual(
            values,
            [
                ("GROUP 0", v15_6_2_13.Task.FINISHED.status, 1),
                ("GROUP 1", v15_6_2_13.Task.FINISHED.status, 1),
                ("GROUP 2", v15_6_2_13.Task.DISCARDED.status, 0),
            ],
        )


if __name__ == "__main__":
    unittest.main()
