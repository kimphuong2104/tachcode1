#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


import unittest

import pytest
from mock import patch

from cs.pcs.projects.web import navigation


@pytest.mark.unit
class TestMisc(unittest.TestCase):
    @patch.object(navigation, "get_restname")
    @patch.object(navigation.cdbwrapc, "get_label")
    def test_navigation_default(self, get_restname, get_label):
        get_restname.side_effect = lambda x: x
        get_label.side_effect = lambda x: x
        expected = [
            (
                "cdbpcs_time_schedules",
                "cdbpcs_gantt_chart",
                "/info/cdbpcs_time_schedule",
            ),
            ("web.projects.tasks_search", "cdbpcs_task", "/info/cdbpcs_task"),
            ("web.projects.open_issues_search", "cdbpcs_issue", "/info/cdbpcs_issue"),
            (
                "web.projects.checklist_search",
                "cdbpcs_checklist",
                "/info/cdbpcs_checklist",
            ),
            ("web.projects.actions_search", "cdb_action", "/info/cdb_action"),
            ("cdbpcs_search_efforts", "cdbpcs_effort_entry", "/info/cdbpcs_effort"),
            ("web.efforts.my_efforts", "cdbpcs_efforts_person_time", "/myefforts"),
        ]
        self.assertEqual(expected, navigation.get_nav_entries_default())

    @patch.object(navigation, "sig")
    def test_get_nav_entries_sig(self, sig):
        entry1 = (("mylabel", "myicon", "mylink"),)
        entry2 = (("mylabel2", "myicon2", "mylink2"),)
        entry3 = (("mylabel3", "myicon3", "mylink3"),)
        sig.emit.return_value = lambda: [[entry1], [entry2, entry3]]
        self.assertEqual(navigation.get_nav_entries(), [entry1, entry2, entry3])

    @patch.object(navigation, "sig")
    @patch.object(navigation, "get_nav_entries_default")
    def test_get_nav_entries_default(self, get_nav_entries_default, sig):
        sig.emit.return_value = lambda: []

        self.assertEqual(
            navigation.get_nav_entries(), get_nav_entries_default.return_value
        )


if __name__ == "__main__":
    unittest.main()
