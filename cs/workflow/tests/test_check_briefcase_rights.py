#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

from __future__ import absolute_import
import unittest
from cdb import ue
from cdb import testcase

from cs.workflow.processes import Process
from cs.workflow import briefcases


class FolderContent(testcase.RollbackTestCase):
    maxDiff = None

    def _can_add_content(self, is_template, wf_status, task_status, **_expected):
        # create wf with task, respecting statuses and template flag
        process = Process.ByKeys("TEST_ADD_CONTENT")
        process.Update(
            status=wf_status,
            is_template=int(is_template),
            subject_id="wftest_wf_owner",
            subject_type="Person",
        )
        task = process.Tasks[0]
        task.Update(status=task_status)

        def _check_access(briefcase, user_id):
            f = briefcases.FolderContent(cdb_folder_id=briefcase.cdb_object_id)
            try:
                f.check_briefcase_rights(None, persno=user_id)
            except ue.Exception:
                return 0

            return 1

        result = {
            "wftest_wf_owner": set(),
            "wftest_task_owner": set(),
            "wftest_bystander": set(),
            "wftest_lib_mgr": set(),
            "wftest_admin": set(),
        }
        expected = dict(result)
        expected.update(_expected)

        for user_id in result:
            self.assertTrue(
                process.CheckAccess("read", persno=user_id),
                "user '{}' is not set up".format(user_id),
            )
            result[user_id] = set([
                briefcase.name
                for briefcase in process.AllBriefcases
                if _check_access(briefcase, user_id)
            ])

        self.assertEqual(result, expected)

    def test_check_briefcase_rights_0_0(self):
        "wf new, task new -> wf owner, wf admin"
        self._can_add_content(0, 0, 0,
            wftest_wf_owner=set([
                u"Global Info",
                u"Global Edit",
                u"Local Info",
                u"Local Edit",
            ]),
            wftest_admin=set([
                u"Global Info",
                u"Global Edit",
                u"Local Info",
                u"Local Edit",
            ]),
        )

    def test_check_briefcase_rights_0_10(self):
        "wf new, task ready -> wf owner, wf admin"
        self._can_add_content(0, 0, 10,
            wftest_wf_owner=set([
                u"Global Info",
                u"Global Edit",
                u"Local Info",
                u"Local Edit",
            ]),
            wftest_admin=set([
                u"Global Info",
                u"Global Edit",
                u"Local Info",
                u"Local Edit",
            ]),
        )

    def test_check_briefcase_rights_10_0(self):
        "wf ready, task new -> wf owner, wf admin"
        self._can_add_content(0, 10, 0,
            wftest_wf_owner=set([
                u"Global Info",
                u"Global Edit",
                u"Local Info",
                u"Local Edit",
            ]),
            wftest_admin=set([
                u"Global Info",
                u"Global Edit",
                u"Local Info",
                u"Local Edit",
            ]),
        )

    def test_check_briefcase_rights_10_10(self):
        "wf ready, task ready -> wf owner, task owner (local only), wf admin"
        self._can_add_content(0, 10, 10,
            wftest_task_owner=set([
                u"Local Info",
                u"Local Edit",
            ]),
            wftest_wf_owner=set([
                u"Global Info",
                u"Global Edit",
                u"Local Info",
                u"Local Edit",
            ]),
            wftest_admin=set([
                u"Global Info",
                u"Global Edit",
                u"Local Info",
                u"Local Edit",
            ]),
        )

    def test_check_briefcase_rights_20_10(self):
        "wf completed, task ready -> nobody"
        self._can_add_content(0, 20, 10)

    def test_check_briefcase_rights_20_0(self):
        "wf completed, task new -> nobody"
        self._can_add_content(0, 20, 0)

    def test_check_briefcase_rights_30_0(self):
        "wf failed, task new -> nobody"
        self._can_add_content(0, 30, 0)

    def test_check_briefcase_rights_30_10(self):
        "wf failed, task ready -> nobody"
        self._can_add_content(0, 30, 10)

    def test_check_briefcase_rights_40_0(self):
        "wf discarded, task new -> nobody"
        self._can_add_content(0, 40, 0)

    def test_check_briefcase_rights_40_10(self):
        "wf discarded, task ready -> nobody"
        self._can_add_content(0, 40, 10)

    def test_check_briefcase_rights_50_0(self):
        "wf frozen, task new -> nobody"
        self._can_add_content(0, 50, 0)

    def test_check_briefcase_rights_50_10(self):
        "wf frozen, task ready -> nobody"
        self._can_add_content(0, 50, 10)

    def test_check_briefcase_rights_t_0_0(self):
        "template new -> wf owner, wf admin"
        self._can_add_content(1, 0, 0,
            wftest_lib_mgr=set([
                u"Global Info",
                u"Global Edit",
                u"Local Info",
                u"Local Edit",
            ]),
            wftest_admin=set([
                u"Global Info",
                u"Global Edit",
                u"Local Info",
                u"Local Edit",
            ]),
        )

    def test_check_briefcase_rights_t_20_0(self):
        "template released -> admin only"
        self._can_add_content(1, 20, 0)

    def test_check_briefcase_rights_t_40_0(self):
        "template invalid -> admin only"
        self._can_add_content(1, 40, 0)

    def test_check_briefcase_rights_t_100_0(self):
        "template reivew -> admin only"
        self._can_add_content(1, 100, 0)


if __name__ == "__main__":
    unittest.main()
