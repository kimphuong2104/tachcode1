#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import datetime
from cdb import testcase
from cdb import util
from cs.workflow import reports
from cs.workflow.processes import Process
from cs.workflow.protocols import MSGAPPROVED

TEST_REPORT_ID = "TEST_REPORT"
TEST_TEMPLATE_ID = "TEST_TEMPLATE"


def setup_module():
    testcase.run_level_setup()


def getProcess():
    return Process.ByKeys(TEST_REPORT_ID)


def getTemplate():
    return Process.ByKeys(TEST_TEMPLATE_ID)


class WorkflowReportTestCase(testcase.RollbackTestCase):
    #
    # Test will fail if the system language during testing is not "de"
    #
    def test_getProtocolDescriptionAndRemark(self):
        protocol_desc_nothing = u""
        expected_desc = u""
        expected_rem = u""
        desc, rem = reports.WorkflowReport.getProtocolDescriptionAndRemark(
            reports.WorkflowReport(),
            protocol_desc_nothing)
        self.assertEqual(
            [desc, rem],
            [expected_desc, expected_rem]
        )
        protocol_desc_add = u"Hinzugefügt: T00000021 (Systemaufgabe)"
        expected_desc = u"Hinzugefügt"
        expected_rem = u"T00000021 (Systemaufgabe)"
        desc, rem = reports.WorkflowReport.getProtocolDescriptionAndRemark(
            reports.WorkflowReport(),
            protocol_desc_add)
        self.assertEqual(
            [desc, rem],
            [expected_desc, expected_rem]
        )
        protocol_desc_delete = u"Gelöscht: T00000018 (PreA)"
        expected_desc = u"Gelöscht"
        expected_rem = u"T00000018 (PreA)"
        desc, rem = reports.WorkflowReport.getProtocolDescriptionAndRemark(
            reports.WorkflowReport(),
            protocol_desc_delete)
        self.assertEqual(
            [desc, rem],
            [expected_desc, expected_rem]
        )
        protocol_desc_modify = u"Geändert: T00000019 subject_id:  -> caddok\nsubject_type:  -> Person"
        expected_desc = u"Geändert"
        expected_rem = u"T00000019 subject_id:  -> caddok\nsubject_type:  -> Person"
        desc, rem = reports.WorkflowReport.getProtocolDescriptionAndRemark(
            reports.WorkflowReport(),
            protocol_desc_modify)
        self.assertEqual(
            [desc, rem],
            [expected_desc, expected_rem]
        )
        protocol_desc_copy = u"Kopiert: T00000018 (Prüfung) aus Vorlage REPORT_TEMPLATE (P00000048)"
        expected_desc = u"Kopiert"
        expected_rem = u"T00000018 (Prüfung) aus Vorlage REPORT_TEMPLATE (P00000048)"
        desc, rem = reports.WorkflowReport.getProtocolDescriptionAndRemark(
            reports.WorkflowReport(),
            protocol_desc_copy)
        self.assertEqual(
            [desc, rem],
            [expected_desc, expected_rem]
        )
        protocol_desc_aggregated = u"[Durchlauf 1 P00000051] Geändert: T00000019 subject_id:  -> caddok\nsubject_type:  -> Person"
        expected_desc = u"[Durchlauf 1 P00000051] Geändert"
        expected_rem = u"T00000019 subject_id:  -> caddok\nsubject_type:  -> Person"
        desc, rem = reports.WorkflowReport.getProtocolDescriptionAndRemark(
            reports.WorkflowReport(),
            protocol_desc_aggregated)
        self.assertEqual(
            [desc, rem],
            [expected_desc, expected_rem]
        )


class WorkflowTemplateTestCase(testcase.RollbackTestCase):
    #
    # This test will fail if the Workflow Test Report is edited
    #
    def test_getTemplateIdAndCopyTimeStamp(self):
        # In this test case we ignore the time component of datetime
        process = getProcess()
        expected_template_id = TEST_TEMPLATE_ID
        expected_timestamp = datetime.date.today()
        process.addProtocol(util.get_label("cdbwf_process_from_template").format(expected_template_id))
        template_id, timestamp = reports.WorkflowTemplate.getTemplateIdAndCopyTimeStamp(reports.WorkflowTemplate(), process)
        self.assertEqual(
            [expected_template_id, expected_timestamp],
            [template_id, timestamp.date()]
        )

    #
    # This test will fail if the Workflow Template TEST_TEMPLATE is edited
    #
    def test_getTemplateReleaseDate(self):
        # In this test case we ignore the time component of datetime
        template_id = TEST_TEMPLATE_ID
        timestamp = datetime.date.today() + datetime.timedelta(1)
        expected_release_date = datetime.datetime.now().date()
        template = getTemplate()
        template.addProtocol(
            util.get_label("cdbwf_process_template_approved"),
            MSGAPPROVED
            )
        release_date = reports.WorkflowTemplate.getTemplateReleaseDate(
            reports.WorkflowTemplate(), template_id, timestamp)
        self.assertEqual(
            expected_release_date,
            release_date.date()
        )
