#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest
from datetime import date

import mock
import pytest

from cs.pcs.efforts.web.rest_app.models import recently_used_tasks


@pytest.mark.unit
class TestEffortsModel(unittest.TestCase):
    maxDiff = None
    __user_id__ = "pcs_unit_test"

    @mock.patch.object(recently_used_tasks.RecentlyUsedTasks, "retrieve_task_proposals")
    def test_get_recently_use_tasks(self, retrieve):
        tp1 = mock.Mock(
            cdb_project_id="P1",
            task_id="T1",
            pinned=1,
            pinned_sel_time=date(2022, 7, 4),
        )
        tp2 = mock.Mock(
            cdb_project_id="P2",
            task_id="T2",
            pinned=1,
            pinned_sel_time=date(2022, 7, 11),
        )
        tp3 = mock.Mock(
            cdb_project_id="P1",
            task_id="T3",
            pinned=0,
            pinned_sel_time=date(2022, 7, 14),
        )
        tp4 = mock.Mock(
            cdb_project_id="P2",
            task_id="T4",
            pinned=0,
            pinned_sel_time=date(2022, 7, 1),
        )

        t1 = mock.Mock(cdb_project_id="P1", task_id="T1")
        t2 = mock.Mock(cdb_project_id="P2", task_id="T2")
        t3 = mock.Mock(cdb_project_id="P1", task_id="T3")
        t4 = mock.Mock(cdb_project_id="P2", task_id="T4")

        p1 = mock.Mock(cdb_project_id="P1")
        p2 = mock.Mock(cdb_project_id="P2")

        retrieve.return_value = (
            [tp3, tp2, tp4, tp1],
            [t3, t4, t1, t2],
            [p2, p1],
        )

        ru_tasks = recently_used_tasks.RecentlyUsedTasks(self.__user_id__)
        self.assertEqual(
            ru_tasks.get_recently_use_tasks(),
            [
                {
                    "cdb_project_id": "P1",
                    "task_id": "T1",
                    "pinned": 1,
                    "task_name": t1.task_name,
                    "task_desc": t1.GetDescription.return_value,
                    "project_name": p1.project_name,
                    "project_desc": p1.GetDescription.return_value,
                },
                {
                    "cdb_project_id": "P2",
                    "task_id": "T2",
                    "pinned": 1,
                    "task_name": t2.task_name,
                    "task_desc": t2.GetDescription.return_value,
                    "project_name": p2.project_name,
                    "project_desc": p2.GetDescription.return_value,
                },
                {
                    "cdb_project_id": "P1",
                    "task_id": "T3",
                    "pinned": 0,
                    "task_name": t3.task_name,
                    "task_desc": t3.GetDescription.return_value,
                    "project_name": p1.project_name,
                    "project_desc": p1.GetDescription.return_value,
                },
                {
                    "cdb_project_id": "P2",
                    "task_id": "T4",
                    "pinned": 0,
                    "task_name": t4.task_name,
                    "task_desc": t4.GetDescription.return_value,
                    "project_name": p2.project_name,
                    "project_desc": p2.GetDescription.return_value,
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
