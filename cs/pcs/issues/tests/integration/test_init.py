#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access,no-value-for-parameter,consider-using-f-string

import mock
import pytest
from cdb import rte, testcase
from cdb.constants import kOperationCopy
from cdb.objects.operations import operation

from cs.pcs import issues
from cs.pcs.issues.tests.common import generate_issue
from cs.pcs.projects.common import email
from cs.pcs.projects.tests import common


def setup_module():
    testcase.run_level_setup()


@pytest.mark.integration
class IssueIntegrationTestCase(testcase.RollbackTestCase):
    def _create_email_issue(self):
        project = common.generate_project(
            cdb_project_id="TEST_ISSUE_PROJECT",
            project_name="Test Issue's Project",
        )
        return generate_issue(project, 999)

    @mock.patch.dict(rte.environ, {"CADDOK_WWWSERVICE_URL": "http://foo"})
    def test_setNotificationContext(self):
        sc = mock.MagicMock()
        issue = self._create_email_issue()
        self.assertIsNone(issue.setNotificationContext(sc))
        self.assertEqual(sc.issue_name_web, "Test Issue 999 (Browser)")
        self.assertEqual(sc.issue_name_win, "Test Issue 999 (Client)")
        self.assertEqual(
            sc.issue_link_win,
            (
                "cdb:///byname/classname/cdbpcs_issue/"
                "CDB_Modify/interactive?"
                "cdbpcs_issue.issue_id={}&"
                "cdbpcs_issue.cdb_project_id=TEST_ISSUE_PROJECT"
            ).format(issue.issue_id),
        )
        self.assertEqual(
            sc.issue_link_web,
            "http://foo/info/issue/{}@TEST_ISSUE_PROJECT".format(issue.issue_id),
        )
        self.assertEqual(sc.project_name_web, "Test Issue's Project (Browser)")
        self.assertEqual(sc.project_name_win, "Test Issue's Project (Client)")
        self.assertEqual(
            sc.project_link_win,
            (
                "cdb:///byname/classname/cdbpcs_project/"
                "cdbpcs_project_overview/interactive?"
                "cdbpcs_project.cdb_project_id=TEST_ISSUE_PROJECT&"
                "cdbpcs_project.ce_baseline_id="
            ),
        )
        self.assertEqual(
            sc.project_link_web, "http://foo/info/project/TEST_ISSUE_PROJECT@"
        )

    @mock.patch.dict(rte.environ, {"CADDOK_WWWSERVICE_URL": "http://www.example.org"})
    def test_setNotificationContext_no_web_links(self):
        sc = mock.MagicMock(
            issue_name_web=None,
            issue_link_web=None,
            project_name_web=None,
            project_link_web=None,
        )
        issue = self._create_email_issue()

        with mock.patch.object(email.logging, "info") as info:
            self.assertIsNone(issue.setNotificationContext(sc))

        self.assertIsNone(sc.issue_name_web)
        self.assertEqual(sc.issue_name_win, "Test Issue 999 (Client)")
        self.assertEqual(
            sc.issue_link_win,
            (
                "cdb:///byname/classname/cdbpcs_issue/"
                "CDB_Modify/interactive?"
                "cdbpcs_issue.issue_id={}&"
                "cdbpcs_issue.cdb_project_id=TEST_ISSUE_PROJECT"
            ).format(issue.issue_id),
        )
        self.assertIsNone(sc.issue_link_web)
        self.assertIsNone(sc.project_name_web)
        self.assertEqual(sc.project_name_win, "Test Issue's Project (Client)")
        self.assertEqual(
            sc.project_link_win,
            (
                "cdb:///byname/classname/cdbpcs_project/"
                "cdbpcs_project_overview/interactive?"
                "cdbpcs_project.cdb_project_id=TEST_ISSUE_PROJECT&"
                "cdbpcs_project.ce_baseline_id="
            ),
        )
        self.assertIsNone(sc.project_link_web)
        info.assert_called_once_with(
            "set the root URL to something else than '%s' "
            "to include web links in issue e-mail notifications",
            "http://www.example.org",
        )

    @mock.patch.dict(rte.environ, {"CADDOK_WWWSERVICE_URL": "http://www.example.org"})
    def test_email_notification_body_win_only(self):
        issue = self._create_email_issue()
        templ_file = issue._getNotificationTemplateFile(None)
        self.assertEqual(
            issue._render_mail_template(None, templ_file),
            (
                '<meta charset="UTF-8" />\n'
                "<div>\n"
                "    <p>\n"
                "        Offener Punkt/Issue:&nbsp;\n"
                "        \n"
                "        <a\n"
                '            href="cdb:///byname/classname/cdbpcs_issue/'
                "CDB_Modify/interactive?"
                "cdbpcs_issue.issue_id={0}&amp;"
                "cdbpcs_issue.cdb_project_id=TEST_ISSUE_PROJECT"
                '">Test Issue 999 (Client)</a>\n'
                "    </p>\n"
                "\n"
                "    <p>\n"
                "        Projekt/Project:&nbsp;\n"
                "        \n"
                "        <a\n"
                '            href="cdb:///byname/classname/cdbpcs_project/'
                "cdbpcs_project_overview/interactive?"
                "cdbpcs_project.cdb_project_id=TEST_ISSUE_PROJECT&amp;"
                "cdbpcs_project.ce_baseline_id="
                "\">Test Issue's Project (Client)</a>\n"
                "    </p>\n"
                "</div>\n"
            ).format(issue.issue_id),
        )

    @mock.patch.dict(rte.environ, {"CADDOK_WWWSERVICE_URL": "http://foo"})
    def test_email_notification_body(self):
        issue = self._create_email_issue()
        templ_file = issue._getNotificationTemplateFile(None)
        self.assertEqual(
            issue._render_mail_template(None, templ_file),
            (
                '<meta charset="UTF-8" />\n'
                "<div>\n"
                "    <p>\n"
                "        Offener Punkt/Issue:&nbsp;\n"
                "        <a\n"
                '            href="http://foo/info/issue/{0}@TEST_ISSUE_PROJECT">'
                "Test Issue 999 (Browser)</a>\n"
                "        <a\n"
                '            href="cdb:///byname/classname/cdbpcs_issue/'
                "CDB_Modify/interactive?"
                "cdbpcs_issue.issue_id={0}&amp;"
                "cdbpcs_issue.cdb_project_id=TEST_ISSUE_PROJECT"
                '">Test Issue 999 (Client)</a>\n'
                "    </p>\n"
                "\n"
                "    <p>\n"
                "        Projekt/Project:&nbsp;\n"
                "        <a\n"
                '            href="http://foo/info/project/TEST_ISSUE_PROJECT@">'
                "Test Issue's Project (Browser)</a>\n"
                "        <a\n"
                '            href="cdb:///byname/classname/cdbpcs_project/'
                "cdbpcs_project_overview/interactive?"
                "cdbpcs_project.cdb_project_id=TEST_ISSUE_PROJECT&amp;"
                "cdbpcs_project.ce_baseline_id="
                "\">Test Issue's Project (Client)</a>\n"
                "    </p>\n"
                "</div>\n"
            ).format(issue.issue_id),
        )

    def test_set_frozen_in_event_map(self):
        "Issue event map contains 'set_frozen'"
        self.assertIn(
            "set_frozen", issues.Issue.GetEventMap()[(("create", "copy"), "pre")]
        )

    def test_derived_from_WithFrozen(self):
        "Issue is derived from WithFrozen"
        self.assertIn(issues.WithFrozen, issues.Issue.mro())

    def test_applies_defaults_on_copy(self):
        "Defaults are applied while copying an open issue"
        self.project = common.generate_project(cdb_project_id="TEST_ISSUE_PROJECT")
        self.task = common.generate_task(self.project, "TEST_ISSUE_TASK")
        self.issue = generate_issue(
            self.project,
            "1",
            category="Korrektur",
            priority="kritisch",
            reason="Test Reason",
            completion_date="01.02.2022",
            waiting_for="caddok",
            mapped_waiting_for_name="Administrator",
        )
        copied_issue = operation(kOperationCopy, self.issue)
        expected = {
            "category": self.issue.category,
            "priority": self.issue.priority,
            "reason": "",
            "completion_date": None,
            "waiting_for": "",
            "mapped_waiting_for_name": "",
        }
        result = {
            "category": copied_issue.category,
            "priority": copied_issue.priority,
            "reason": copied_issue.reason,
            "completion_date": copied_issue.completion_date,
            "waiting_for": copied_issue.waiting_for,
            "mapped_waiting_for_name": copied_issue.mapped_waiting_for_name,
        }
        self.assertDictEqual(result, expected)

    def test_base_event_map_complete(self):
        "Issue event map contains base Issue events"
        eventmap = issues.Issue.GetEventMap()
        self.assertIn("setIssueID", eventmap[(("create", "copy"), "pre")])
        self.assertIn("newChangeLog", eventmap[(("create", "copy", "modify"), "post")])
        self.assertIn(
            "check_project_role_needed",
            eventmap[(("create", "copy", "modify"), "post")],
        )
        self.assertIn("setFields", eventmap[(("modify", "info"), "pre_mask")])
        self.assertIn(
            "check_project_role_needed",
            eventmap[(("delete", "state_change", "cs_tasks_delegate"), "post")],
        )
