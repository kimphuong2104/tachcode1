#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=too-many-lines

import datetime
from collections import defaultdict

import pytest
from cdb import testcase
from cs.documents import Document

from cs.pcs.checklists import Checklist
from cs.pcs.msp.tests.integration.util import (
    create_document_from_base_fname,
    create_project_ex,
    create_workflow,
)
from cs.pcs.projects import Project
from cs.pcs.projects.tasks import Task


def setup_module():
    testcase.run_level_setup()


class MSPImport(testcase.RollbackTestCase):

    EXPECTED_EXCEPTIONS = defaultdict(list)
    EXPECTED_TASKS = defaultdict(dict)

    def tearDown(self):
        super().tearDown()
        self.EXPECTED_EXCEPTIONS.clear()
        self.EXPECTED_TASKS.clear()

    def add_exception(self, task_name, exception_text):
        self.EXPECTED_EXCEPTIONS[task_name].append(exception_text)

    def add_task_values(self, task_name, **kwargs):
        self.EXPECTED_TASKS[task_name].update(task_name=task_name, **kwargs)

    def add_data(self, base_fname):
        self.project = create_project_ex(user_input_custom={"project_name": base_fname})
        self.xml_doc = create_document_from_base_fname(base_fname)
        self.xml_doc.cdb_project_id = self.project.cdb_project_id
        self.project.msp_active = 1
        self.project.msp_z_nummer = self.xml_doc.z_nummer

    def execute_and_check_import(self, name):
        # create test data
        self.add_data(name)

        # prepare and check project
        projects = Project.KeywordQuery(project_name=name, ce_baseline_id="")
        project = projects[0]
        project.ChangeState(50)

        # prepare and check project XML document
        docs = Document.KeywordQuery(titel=name)
        doc = docs[0]
        doc_keys = {"z_nummer": doc.z_nummer, "z_index": doc.z_index}

        # import XML document into project
        self.result = project.XML_IMPORT_CLASS.import_project_from_xml(
            project, doc_keys, dry_run=False, called_from_officelink=True
        )

        # check exceptions
        self.check_exceptions(self.result.project, "project_name")
        checked = []
        for t in self.result.tasks.excepted:
            checked.append(self.check_exceptions(t, "task_name"))
        expected = list(self.EXPECTED_EXCEPTIONS)
        expected.sort()
        checked.sort()
        self.assertEqual(
            expected,
            checked,
            f"\nExpected exceptions: {expected}" f"\nFound exceptions: {checked}",
        )
        if not expected:
            # check added tasks
            for t in self.result.tasks.added:
                self.check_task(t)

        return project

    def check_exceptions(self, diff_object, attr):
        name = diff_object.pcs_object[attr]
        expected = self.EXPECTED_EXCEPTIONS.get(name, [])
        self.assertEqual(diff_object.exceptions, expected)
        return name

    def check_task(self, diff_object):
        name = diff_object.pcs_object["task_name"]
        tasks = Task.KeywordQuery(task_name=name, ce_baseline_id="")
        expected_values = self.EXPECTED_TASKS[name]
        self.assertNotEqual(
            expected_values,
            {},
            f"Task '{name}' is not registrated for a check.",
        )
        for key, value in expected_values.items():
            db_value = tasks[0][key]
            self.assertEqual(
                value,
                db_value,
                f"Task '{name}' has different values for attribute '{key}': "
                f"'{db_value}' != '{value}'",
            )


@pytest.mark.dependency(name="integration", depends=["cs.pcs.msp"])
class MSPImportWithExceptions(MSPImport):
    @testcase.without_error_logging
    def test_import_01(self):
        "Testing expected errors"
        self.add_exception(
            "automatically scheduled, with date and duration > 0 days",
            "Ein Meilenstein darf keine Dauer größer als 0 haben.",
        )
        self.add_exception(
            "manually scheduled, duration only, > 0 days",
            "Ein Meilenstein darf keine Dauer größer als 0 haben.",
        )
        self.add_exception(
            "manually scheduled, with date and duration > 0 days",
            "Ein Meilenstein darf keine Dauer größer als 0 haben.",
        )
        self.add_exception(
            "B",
            (
                "Das Ende der Aufgabe (16:36) entspricht nicht dem vorgegebenen "
                "Tagesende (17:00). Termine dürfen nur auf den Tagesanfang "
                "bzw. das Tagesende gelegt werden. "
                "Bitte ändern Sie das Ende der Aufgabe im Projektplan."
            ),
        )
        self.add_exception(
            "name of a project role (DE)",
            "Die Person/Rolle 'Projektkostenmanagement' konnte nicht gefunden werden.",
        )
        self.add_exception(
            "id of a project role",
            "Die Person/Rolle 'Project Cost Management' konnte nicht gefunden werden.",
        )
        self.execute_and_check_import("expected_errors")


@pytest.mark.dependency(name="integration", depends=["cs.pcs.msp"])
class MSPImportWithoutExceptions(MSPImport):
    def test_import_01(self):
        "Testing automatically scheduled milestones"
        self.add_task_values(
            "automatically scheduled, with date and duration, early position",
            start_time_fcast=datetime.date(2020, 4, 1),
            end_time_fcast=datetime.date(2020, 4, 1),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=0,
            automatic=1,
            percent_complet=0,
            status=0,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 1),
            early_finish=datetime.date(2020, 4, 1),
            late_start=datetime.date(2020, 4, 16),
            late_finish=datetime.date(2020, 4, 16),
            free_float=12,
            total_float=12,
            auto_update_time=1,
            milestone=1,
            start_is_early=1,
            end_is_early=1,
        )
        self.add_task_values(
            "automatically scheduled, with date and duration, early position, 1% of progress",
            start_time_fcast=datetime.date(2020, 4, 1),
            end_time_fcast=datetime.date(2020, 4, 1),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=0,
            automatic=1,
            percent_complet=1,
            status=50,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 1),
            early_finish=datetime.date(2020, 4, 1),
            late_start=datetime.date(2020, 4, 1),
            late_finish=datetime.date(2020, 4, 15),
            free_float=10,
            total_float=10,
            auto_update_time=1,
            milestone=1,
            start_is_early=1,
            end_is_early=1,
        )
        self.add_task_values(
            "automatically scheduled, with date and duration, early position, 100% of progress",
            start_time_fcast=datetime.date(2020, 4, 1),
            end_time_fcast=datetime.date(2020, 4, 1),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=0,
            automatic=1,
            percent_complet=100,
            status=200,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 1),
            early_finish=datetime.date(2020, 4, 1),
            late_start=datetime.date(2020, 4, 1),
            late_finish=datetime.date(2020, 4, 1),
            free_float=0,
            total_float=0,
            auto_update_time=1,
            milestone=1,
            start_is_early=1,
            end_is_early=1,
        )
        self.add_task_values(
            "automatically scheduled, early position, as late as possible",
            start_time_fcast=datetime.date(2020, 4, 15),
            end_time_fcast=datetime.date(2020, 4, 15),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=0,
            automatic=1,
            percent_complet=0,
            status=0,
            constraint_type="1",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 1),
            early_finish=datetime.date(2020, 4, 1),
            late_start=datetime.date(2020, 4, 15),
            late_finish=datetime.date(2020, 4, 15),
            free_float=0,
            total_float=0,
            auto_update_time=1,
            milestone=1,
            start_is_early=1,
            end_is_early=1,
        )
        self.add_task_values(
            "automatically scheduled, early position, must start on",
            start_time_fcast=datetime.date(2020, 4, 15),
            end_time_fcast=datetime.date(2020, 4, 15),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=0,
            automatic=1,
            percent_complet=0,
            status=0,
            constraint_type="2",
            constraint_date=datetime.date(2020, 4, 15),
            early_start=datetime.date(2020, 4, 15),
            early_finish=datetime.date(2020, 4, 15),
            late_start=datetime.date(2020, 4, 15),
            late_finish=datetime.date(2020, 4, 15),
            free_float=0,
            total_float=0,
            auto_update_time=1,
            milestone=1,
            start_is_early=1,
            end_is_early=1,
        )
        self.add_task_values(
            "automatically scheduled, late position, start no earlier than",
            start_time_fcast=datetime.date(2020, 4, 1),
            end_time_fcast=datetime.date(2020, 4, 1),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=0,
            automatic=1,
            percent_complet=0,
            status=0,
            constraint_type="4",
            constraint_date=datetime.date(2020, 4, 1),
            early_start=datetime.date(2020, 4, 1),
            early_finish=datetime.date(2020, 4, 1),
            late_start=datetime.date(2020, 4, 15),
            late_finish=datetime.date(2020, 4, 15),
            free_float=9,
            total_float=9,
            auto_update_time=1,
            milestone=1,
            start_is_early=0,
            end_is_early=0,
        )
        self.add_task_values(
            "automatically scheduled, late position, end no earlier than",
            start_time_fcast=datetime.date(2020, 4, 9),
            end_time_fcast=datetime.date(2020, 4, 9),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=0,
            automatic=1,
            percent_complet=0,
            status=0,
            constraint_type="6",
            constraint_date=datetime.date(2020, 4, 9),
            early_start=datetime.date(2020, 4, 9),
            early_finish=datetime.date(2020, 4, 9),
            late_start=datetime.date(2020, 4, 15),
            late_finish=datetime.date(2020, 4, 15),
            free_float=3,
            total_float=3,
            auto_update_time=1,
            milestone=1,
            start_is_early=0,
            end_is_early=0,
        )
        self.execute_and_check_import("automatically_scheduled_milestones")

    def test_import_02(self):
        "Testing automatically scheduled tasks"
        self.add_task_values(
            "automatically scheduled, as soon as possible",
            start_time_fcast=datetime.date(2020, 4, 1),
            end_time_fcast=datetime.date(2020, 4, 7),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=5,
            automatic=1,
            percent_complet=0,
            status=0,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 1),
            early_finish=datetime.date(2020, 4, 7),
            late_start=datetime.date(2020, 4, 10),
            late_finish=datetime.date(2020, 4, 16),
            free_float=7,
            total_float=7,
            auto_update_time=1,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "automatically scheduled, 1% of progress",
            start_time_fcast=datetime.date(2020, 4, 6),
            end_time_fcast=datetime.date(2020, 4, 10),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=5,
            automatic=1,
            percent_complet=1,
            status=50,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 6),
            early_finish=datetime.date(2020, 4, 10),
            late_start=datetime.date(2020, 4, 6),
            late_finish=datetime.date(2020, 4, 16),
            free_float=4,
            total_float=4,
            auto_update_time=1,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "automatically scheduled, 66% of progress",
            start_time_fcast=datetime.date(2020, 4, 6),
            end_time_fcast=datetime.date(2020, 4, 10),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=5,
            automatic=1,
            percent_complet=66,
            status=50,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 6),
            early_finish=datetime.date(2020, 4, 10),
            late_start=datetime.date(2020, 4, 6),
            late_finish=datetime.date(2020, 4, 16),
            free_float=4,
            total_float=4,
            auto_update_time=1,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "automatically scheduled, 100% of progress",
            start_time_fcast=datetime.date(2020, 4, 6),
            end_time_fcast=datetime.date(2020, 4, 10),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=5,
            automatic=1,
            percent_complet=100,
            status=200,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 6),
            early_finish=datetime.date(2020, 4, 10),
            late_start=datetime.date(2020, 4, 6),
            late_finish=datetime.date(2020, 4, 10),
            free_float=0,
            total_float=0,
            auto_update_time=1,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "automatically scheduled, must start on",
            start_time_fcast=datetime.date(2020, 4, 14),
            end_time_fcast=datetime.date(2020, 4, 16),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=3,
            automatic=1,
            percent_complet=0,
            status=0,
            constraint_type="2",
            constraint_date=datetime.date(2020, 4, 14),
            early_start=datetime.date(2020, 4, 14),
            early_finish=datetime.date(2020, 4, 16),
            late_start=datetime.date(2020, 4, 14),
            late_finish=datetime.date(2020, 4, 16),
            free_float=0,
            total_float=0,
            auto_update_time=1,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "automatically scheduled, start no earlier than",
            start_time_fcast=datetime.date(2020, 4, 15),
            end_time_fcast=datetime.date(2020, 4, 16),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=2,
            automatic=1,
            percent_complet=0,
            status=0,
            constraint_type="4",
            constraint_date=datetime.date(2020, 4, 15),
            early_start=datetime.date(2020, 4, 15),
            early_finish=datetime.date(2020, 4, 16),
            late_start=datetime.date(2020, 4, 15),
            late_finish=datetime.date(2020, 4, 16),
            free_float=0,
            total_float=0,
            auto_update_time=1,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "automatically scheduled, end no later than",
            start_time_fcast=datetime.date(2020, 4, 1),
            end_time_fcast=datetime.date(2020, 4, 9),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=7,
            automatic=1,
            percent_complet=0,
            status=0,
            constraint_type="7",
            constraint_date=datetime.date(2020, 4, 16),
            early_start=datetime.date(2020, 4, 1),
            early_finish=datetime.date(2020, 4, 9),
            late_start=datetime.date(2020, 4, 8),
            late_finish=datetime.date(2020, 4, 16),
            free_float=5,
            total_float=5,
            auto_update_time=1,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.execute_and_check_import("automatically_scheduled_tasks")

    def test_import_03(self):
        "Testing manually scheduled milestones"
        self.add_task_values(
            "manually scheduled, duration only",
            start_time_fcast=None,
            end_time_fcast=None,
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=0,
            automatic=0,
            percent_complet=0,
            status=0,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 1),
            early_finish=datetime.date(2020, 4, 1),
            late_start=datetime.date(2020, 4, 6),
            late_finish=datetime.date(2020, 4, 6),
            free_float=4,
            total_float=4,
            auto_update_time=2,
            milestone=1,
            start_is_early=0,
            end_is_early=0,
            daytime=1,
        )
        self.add_task_values(
            "manually scheduled, with date and duration, early position",
            start_time_fcast=datetime.date(2020, 4, 6),
            end_time_fcast=datetime.date(2020, 4, 6),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=0,
            automatic=0,
            percent_complet=0,
            status=0,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 6),
            early_finish=datetime.date(2020, 4, 6),
            late_start=datetime.date(2020, 4, 6),
            late_finish=datetime.date(2020, 4, 6),
            free_float=1,
            total_float=1,
            auto_update_time=2,
            milestone=1,
            start_is_early=1,
            end_is_early=1,
            daytime=0,
        )
        self.add_task_values(
            "manually scheduled, with date and duration, late position",
            start_time_fcast=datetime.date(2020, 4, 6),
            end_time_fcast=datetime.date(2020, 4, 6),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=0,
            automatic=0,
            percent_complet=0,
            status=0,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 6),
            early_finish=datetime.date(2020, 4, 6),
            late_start=datetime.date(2020, 4, 6),
            late_finish=datetime.date(2020, 4, 6),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=1,
            start_is_early=0,
            end_is_early=0,
            daytime=1,
        )
        self.add_task_values(
            "manually scheduled, 1% of progress",
            start_time_fcast=datetime.date(2020, 4, 6),
            end_time_fcast=datetime.date(2020, 4, 6),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=0,
            automatic=0,
            percent_complet=1,
            status=50,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 6),
            early_finish=datetime.date(2020, 4, 6),
            late_start=datetime.date(2020, 4, 6),
            late_finish=datetime.date(2020, 4, 6),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=1,
            start_is_early=0,
            end_is_early=0,
            daytime=1,
        )
        self.add_task_values(
            "manually scheduled, 66% of progress",
            start_time_fcast=datetime.date(2020, 4, 6),
            end_time_fcast=datetime.date(2020, 4, 6),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=0,
            automatic=0,
            percent_complet=66,
            status=50,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 6),
            early_finish=datetime.date(2020, 4, 6),
            late_start=datetime.date(2020, 4, 6),
            late_finish=datetime.date(2020, 4, 6),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=1,
            start_is_early=0,
            end_is_early=0,
            daytime=1,
        )
        self.add_task_values(
            "manually scheduled, 100% of progress",
            start_time_fcast=datetime.date(2020, 4, 6),
            end_time_fcast=datetime.date(2020, 4, 6),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=0,
            automatic=0,
            percent_complet=100,
            status=200,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 6),
            early_finish=datetime.date(2020, 4, 6),
            late_start=datetime.date(2020, 4, 6),
            late_finish=datetime.date(2020, 4, 6),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=1,
            start_is_early=0,
            end_is_early=0,
            daytime=1,
        )
        self.execute_and_check_import("manually_scheduled_milestones")

    def test_import_04(self):
        "Testing manually scheduled splitted tasks with a different duration"
        self.add_task_values(
            "A",
            start_time_fcast=datetime.date(2020, 3, 12),
            end_time_fcast=datetime.date(2020, 3, 12),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=1,
            automatic=0,
            percent_complet=56,
            status=50,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 3, 12),
            early_finish=datetime.date(2020, 3, 12),
            late_start=datetime.date(2020, 3, 12),
            late_finish=datetime.date(2020, 3, 24),
            free_float=8,
            total_float=8,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "A.1",
            start_time_fcast=datetime.date(2020, 3, 12),
            end_time_fcast=datetime.date(2020, 3, 18),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=5,
            automatic=0,
            percent_complet=100,
            status=200,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 3, 12),
            early_finish=datetime.date(2020, 3, 18),
            late_start=datetime.date(2020, 3, 12),
            late_finish=datetime.date(2020, 3, 18),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "A.2",
            start_time_fcast=datetime.date(2020, 3, 12),
            end_time_fcast=datetime.date(2020, 3, 18),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=5,
            automatic=0,
            percent_complet=100,
            status=200,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 3, 12),
            early_finish=datetime.date(2020, 3, 18),
            late_start=datetime.date(2020, 3, 12),
            late_finish=datetime.date(2020, 3, 18),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "A.3",
            start_time_fcast=datetime.date(2020, 3, 12),
            end_time_fcast=datetime.date(2020, 3, 24),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=6,
            automatic=0,
            percent_complet=27,
            status=50,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 3, 12),
            early_finish=datetime.date(2020, 3, 24),
            late_start=datetime.date(2020, 3, 12),
            late_finish=datetime.date(2020, 3, 24),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "A.4",
            start_time_fcast=None,
            end_time_fcast=None,
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=5,
            automatic=0,
            percent_complet=0,
            status=0,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 3, 12),
            early_finish=datetime.date(2020, 3, 18),
            late_start=datetime.date(2020, 3, 18),
            late_finish=datetime.date(2020, 3, 24),
            free_float=4,
            total_float=4,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.execute_and_check_import(
            "manually_scheduled_splitted_tasks_with_a_different_duration"
        )

    def test_import_05(self):
        "Testing manually scheduled tasks"
        self.add_task_values(
            "manually scheduled, duration only",
            start_time_fcast=None,
            end_time_fcast=None,
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=3,
            automatic=0,
            percent_complet=0,
            status=0,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 1),
            early_finish=datetime.date(2020, 4, 3),
            late_start=datetime.date(2020, 4, 8),
            late_finish=datetime.date(2020, 4, 10),
            free_float=5,
            total_float=5,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "manually scheduled, with date and duration",
            start_time_fcast=datetime.date(2020, 4, 6),
            end_time_fcast=datetime.date(2020, 4, 10),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=5,
            automatic=0,
            percent_complet=0,
            status=0,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 6),
            early_finish=datetime.date(2020, 4, 10),
            late_start=datetime.date(2020, 4, 6),
            late_finish=datetime.date(2020, 4, 10),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "manually scheduled, 1% of progress",
            start_time_fcast=datetime.date(2020, 4, 6),
            end_time_fcast=datetime.date(2020, 4, 10),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=5,
            automatic=0,
            percent_complet=1,
            status=50,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 6),
            early_finish=datetime.date(2020, 4, 10),
            late_start=datetime.date(2020, 4, 6),
            late_finish=datetime.date(2020, 4, 10),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "manually scheduled, 66% of progress",
            start_time_fcast=datetime.date(2020, 4, 6),
            end_time_fcast=datetime.date(2020, 4, 10),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=5,
            automatic=0,
            percent_complet=66,
            status=50,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 6),
            early_finish=datetime.date(2020, 4, 10),
            late_start=datetime.date(2020, 4, 6),
            late_finish=datetime.date(2020, 4, 10),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "manually scheduled, 100% of progress",
            start_time_fcast=datetime.date(2020, 4, 6),
            end_time_fcast=datetime.date(2020, 4, 10),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=5,
            automatic=0,
            percent_complet=100,
            status=200,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 6),
            early_finish=datetime.date(2020, 4, 10),
            late_start=datetime.date(2020, 4, 6),
            late_finish=datetime.date(2020, 4, 10),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.execute_and_check_import("manually_scheduled_tasks")

    def test_import_06(self):
        "Testing manually task group with dependencies and progress and conflict"
        self.add_task_values(
            "A",
            start_time_fcast=datetime.date(2020, 3, 12),
            end_time_fcast=datetime.date(2020, 3, 12),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=1,
            automatic=0,
            percent_complet=57,
            status=50,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 3, 12),
            early_finish=datetime.date(2020, 3, 12),
            late_start=datetime.date(2020, 3, 12),
            late_finish=datetime.date(2020, 3, 18),
            free_float=4,
            total_float=4,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "A.1",
            start_time_fcast=datetime.date(2020, 3, 12),
            end_time_fcast=datetime.date(2020, 3, 18),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=5,
            automatic=0,
            percent_complet=100,
            status=200,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 3, 12),
            early_finish=datetime.date(2020, 3, 18),
            late_start=datetime.date(2020, 3, 12),
            late_finish=datetime.date(2020, 3, 18),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "A.2",
            start_time_fcast=datetime.date(2020, 3, 12),
            end_time_fcast=datetime.date(2020, 3, 18),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=5,
            automatic=0,
            percent_complet=100,
            status=200,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 3, 12),
            early_finish=datetime.date(2020, 3, 18),
            late_start=datetime.date(2020, 3, 12),
            late_finish=datetime.date(2020, 3, 18),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "A.3",
            start_time_fcast=datetime.date(2020, 3, 12),
            end_time_fcast=datetime.date(2020, 3, 18),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=5,
            automatic=0,
            percent_complet=30,
            status=50,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 3, 12),
            early_finish=datetime.date(2020, 3, 18),
            late_start=datetime.date(2020, 3, 12),
            late_finish=datetime.date(2020, 3, 18),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "A.4",
            start_time_fcast=None,
            end_time_fcast=None,
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=5,
            automatic=0,
            percent_complet=0,
            status=0,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 3, 12),
            early_finish=datetime.date(2020, 3, 18),
            late_start=datetime.date(2020, 3, 12),
            late_finish=datetime.date(2020, 3, 18),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.execute_and_check_import(
            "manually_task_group_with_dependencies_and_progress_and_conflict"
        )

    def test_import_07(self):
        "Testing task responsible"
        self.add_task_values(
            "default: Projektmitglied",
            start_time_fcast=datetime.date(2020, 3, 18),
            end_time_fcast=datetime.date(2020, 3, 18),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=1,
            automatic=0,
            percent_complet=0,
            status=0,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 3, 18),
            early_finish=datetime.date(2020, 3, 18),
            late_start=datetime.date(2020, 3, 18),
            late_finish=datetime.date(2020, 3, 18),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "name of a person",
            start_time_fcast=datetime.date(2020, 3, 18),
            end_time_fcast=datetime.date(2020, 3, 18),
            subject_id="vendorsupport",
            subject_type="Person",
            days_fcast=1,
            automatic=0,
            percent_complet=0,
            status=0,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 3, 18),
            early_finish=datetime.date(2020, 3, 18),
            late_start=datetime.date(2020, 3, 18),
            late_finish=datetime.date(2020, 3, 18),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "id of a person",
            start_time_fcast=datetime.date(2020, 3, 18),
            end_time_fcast=datetime.date(2020, 3, 18),
            subject_id="vendorsupport",
            subject_type="Person",
            days_fcast=1,
            automatic=0,
            percent_complet=0,
            status=0,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 3, 18),
            early_finish=datetime.date(2020, 3, 18),
            late_start=datetime.date(2020, 3, 18),
            late_finish=datetime.date(2020, 3, 18),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "full-qualified person",
            start_time_fcast=datetime.date(2020, 3, 18),
            end_time_fcast=datetime.date(2020, 3, 18),
            subject_id="caddok",
            subject_type="Person",
            days_fcast=1,
            automatic=0,
            percent_complet=0,
            status=0,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 3, 18),
            early_finish=datetime.date(2020, 3, 18),
            late_start=datetime.date(2020, 3, 18),
            late_finish=datetime.date(2020, 3, 18),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "full-qualified project role",
            start_time_fcast=datetime.date(2020, 3, 18),
            end_time_fcast=datetime.date(2020, 3, 18),
            subject_id="Projektleiter",
            subject_type="PCS Role",
            days_fcast=1,
            automatic=0,
            percent_complet=0,
            status=0,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 3, 18),
            early_finish=datetime.date(2020, 3, 18),
            late_start=datetime.date(2020, 3, 18),
            late_finish=datetime.date(2020, 3, 18),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "name of a comm role",
            start_time_fcast=datetime.date(2020, 3, 18),
            end_time_fcast=datetime.date(2020, 3, 18),
            subject_id="HR-Administrator",
            subject_type="Common Role",
            days_fcast=1,
            automatic=0,
            percent_complet=0,
            status=0,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 3, 18),
            early_finish=datetime.date(2020, 3, 18),
            late_start=datetime.date(2020, 3, 18),
            late_finish=datetime.date(2020, 3, 18),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "id of a common role",
            start_time_fcast=datetime.date(2020, 3, 18),
            end_time_fcast=datetime.date(2020, 3, 18),
            subject_id="HR-Administrator",
            subject_type="Common Role",
            days_fcast=1,
            automatic=0,
            percent_complet=0,
            status=0,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 3, 18),
            early_finish=datetime.date(2020, 3, 18),
            late_start=datetime.date(2020, 3, 18),
            late_finish=datetime.date(2020, 3, 18),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "full-qualified common role",
            start_time_fcast=datetime.date(2020, 3, 18),
            end_time_fcast=datetime.date(2020, 3, 18),
            subject_id="Organizations: Manager",
            subject_type="Common Role",
            days_fcast=1,
            automatic=0,
            percent_complet=0,
            status=0,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 3, 18),
            early_finish=datetime.date(2020, 3, 18),
            late_start=datetime.date(2020, 3, 18),
            late_finish=datetime.date(2020, 3, 18),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.execute_and_check_import("task_responsible")


@pytest.mark.dependency(name="integration", depends=["cs.pcs.msp"])
class MSPImportWithReferencedObjects(MSPImport):
    maxDiff = None

    @staticmethod
    def create_checklist(project, cl_id, name):
        values = {
            "cdb_project_id": project.cdb_project_id,
            "checklist_id": cl_id,
            "rating_scheme": "RedGreenYellow",
            "type": "Checklist",
            "cdb_objektart": "cdbpcs_checklist",
            "auto": 1,
            "rating_id": "clear",
            "checklist_name": name,
            "template": 1,
            "subject_id": "caddok",
            "subject_type": "Person",
        }
        return Checklist.Create(**values)

    @staticmethod
    def add_workflow_template():
        project = create_project_ex(
            user_input_custom={"project_name": "CL Templates 101 - 200", "template": 1}
        )
        MSPImportWithReferencedObjects.create_checklist(project, 1, "CL 101")
        MSPImportWithReferencedObjects.create_checklist(project, 2, "CL 102")

        project = create_project_ex(
            user_input_custom={"project_name": "Workflow Templates", "template": 1}
        )
        create_workflow(
            {
                "title": "WF 002",
                "is_template": 1,
                "cdb_project_id": project.cdb_project_id,
            }
        )
        create_workflow(
            {
                "title": "WF 004",
                "is_template": 1,
                "cdb_project_id": project.cdb_project_id,
            }
        )

    def _import_01(self, expected_workflows):
        self.add_workflow_template()
        self.add_task_values(
            "New task with exactly one checklist and one workflow",
            start_time_fcast=datetime.date(2020, 4, 1),
            end_time_fcast=datetime.date(2020, 4, 1),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=1,
            automatic=0,
            percent_complet=0,
            status=0,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 1),
            early_finish=datetime.date(2020, 4, 1),
            late_start=datetime.date(2020, 4, 1),
            late_finish=datetime.date(2020, 4, 1),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "New task with CL and WF as duplicate",
            start_time_fcast=datetime.date(2020, 4, 1),
            end_time_fcast=datetime.date(2020, 4, 1),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=1,
            automatic=0,
            percent_complet=0,
            status=0,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 1),
            early_finish=datetime.date(2020, 4, 1),
            late_start=datetime.date(2020, 4, 1),
            late_finish=datetime.date(2020, 4, 1),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        self.add_task_values(
            "New task with two CL and WF",
            start_time_fcast=datetime.date(2020, 4, 1),
            end_time_fcast=datetime.date(2020, 4, 1),
            subject_id="Projektmitglied",
            subject_type="PCS Role",
            days_fcast=1,
            automatic=0,
            percent_complet=0,
            status=0,
            constraint_type="0",
            constraint_date=None,
            early_start=datetime.date(2020, 4, 1),
            early_finish=datetime.date(2020, 4, 1),
            late_start=datetime.date(2020, 4, 1),
            late_finish=datetime.date(2020, 4, 1),
            free_float=0,
            total_float=0,
            auto_update_time=2,
            milestone=0,
            start_is_early=1,
            end_is_early=0,
        )
        project = self.execute_and_check_import("tasks_with_checklist_and_workflows")

        workflows = [
            {
                "title": x.title,
                "is_template": x.is_template,
                "task_name": ", ".join([c.task_name for c in x.Content]),
            }
            for x in project.Processes
        ]
        self.assertEqual(workflows, expected_workflows)
        return project

    def test_import_01(self):
        "Testing tasks with checklist and workflows"
        self._import_01(
            [
                {
                    "title": "WF 002",
                    "is_template": "0",
                    "task_name": "New task with exactly one checklist and one workflow",
                },
                {
                    "title": "WF 002",
                    "is_template": "0",
                    "task_name": "New task with CL and WF as duplicate",
                },
                {
                    "title": "WF 004",
                    "is_template": "0",
                    "task_name": "New task with two CL and WF",
                },
                {
                    "title": "WF 002",
                    "is_template": "0",
                    "task_name": "New task with two CL and WF",
                },
            ]
        )

    def test_import_01_fail(self):
        "Testing tasks with checklist and workflow failure"
        from cs.workflow.briefcases import BriefcaseContentWhitelist

        # provoke error by not allowing project tasks anymore
        BriefcaseContentWhitelist.KeywordQuery(classname="cdbpcs_task").Update(
            classname="cdbpcs_time_schedule"
        )
        BriefcaseContentWhitelist.Query("classname != 'cdbpcs_time_schedule'").Delete()
        for name in [
            "New task with exactly one checklist and one workflow",
            "New task with CL and WF as duplicate",
            "New task with two CL and WF",
        ]:
            self.add_exception(
                name,
                "Es ist nicht möglich, "
                "Projektaufgaben zu einer Workflowmappe hinzuzufügen. "
                "Sie können nur Terminpläne verwenden.",
            )
        with testcase.error_logging_disabled():
            self._import_01([])


@pytest.mark.dependency(name="integration", depends=["cs.pcs.msp"])
class Add_MSP_Document(testcase.RollbackTestCase):
    def test_create_Project(self):
        project = create_project_ex(
            user_input_custom={"project_name": "NAME!", "msp_active": 1}
        )
        msp_document = project.getLastPrimaryMSPDocument()
        self.assertEqual(
            msp_document.Files.cdbf_name, [f"{msp_document.z_nummer}-.mpp"]
        )
        self.assertEqual(msp_document.titel, f"{project.cdb_project_id} NAME!")
