#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access,no-value-for-parameter

import mock
from cdb import auth
from cdb import i18n
from cdb import testcase
from cdb import ue
from cdb.objects.org import CommonRole
from cdb.objects.org import User

from cs.workflow import systemtasks
from cs.workflow.briefcases import Briefcase
from cs.workflow.briefcases import BriefcaseLink
from cs.workflow.constraints import Constraint
from cs.workflow.designer import wfinterface
from cs.workflow.processes import Process
from cs.workflow.tasks import FilterParameter
from cs.workflow.tasks import Task
from cs.workflow.taskgroups import TaskGroup


def setup_module():
    testcase.run_level_setup()


class WFInterfaceTestCase(testcase.RollbackTestCase):
    def test_is_pcs_enabled(self):
        self.assertEqual(
            wfinterface._is_pcs_enabled(),
            False
        )

    @mock.patch.object(wfinterface.logging, "error")
    @mock.patch.object(wfinterface.logging, "exception")
    def _get_obj_id_from_url_fails(self, url, exc_args, err_args,
                                   exception, error):
        self.assertIsNone(
            wfinterface.get_obj_id_from_url(url),
        )
        if exc_args:
            exception.assert_called_once_with(*exc_args)
        else:
            exception.assert_not_called()
        if err_args:
            error.assert_called_once_with(*err_args)
        else:
            error.assert_not_called()

    def test_get_obj_id_from_url_no_class(self):
        url = "http://host:port/info/no_class"
        self._get_obj_id_from_url_fails(
            url,
            [],
            ["invalid URL: %s (path length %s)", url, 3],
        )

    def test_get_obj_id_from_url_no_key(self):
        url = "http://host:port/info/no_class/no_key"
        self._get_obj_id_from_url_fails(
            url,
            ["cannot get object from url '%s'", url],
            [],
        )

    def test_get_obj_id_from_url_no_relship(self):
        url = "http://host:port/info/no_class/no_key/relship/no_relship"
        self._get_obj_id_from_url_fails(
            url,
            ["cannot get object from url '%s'", url],
            [],
        )

    def test_get_obj_id_from_url_no_file(self):
        self._get_obj_id_from_url_fails(
            "http://host:port/api/v1/collection/no_class/no_key/files/"
            "no_file",
            [],
            ["obj does not exist or is not readable: %s", None],
        )

    def _get_obj_id_from_url(self, url):
        self.assertIsNotNone(
            wfinterface.get_obj_id_from_url(url),
        )

    def test_get_obj_id_from_url_caddok(self):
        self._get_obj_id_from_url(
            "http://host:port/info/person/caddok",
        )

    def test_get_obj_id_from_url_caddok_relship(self):
        self._get_obj_id_from_url(
            "A://B/info/person/caddok@",
        )

    def test_get_obj_id_from_url_org(self):
        self._get_obj_id_from_url(
            "http://host:port/info/person/caddok/relship/Organization",
        )

    def test_get_obj_id_from_url_file(self):
        self._get_obj_id_from_url(
            "http://host/api/v1/collection/person/caddok/files/"
            "3365cfa0-c22c-11e8-ac1e-5cc5d4123f3b",
        )

    def test_GetSubjectCandidates(self):
        def _get_subjects(process, condition=None):
            return set([x.subject_name
                        for x in process.GetSubjectCandidates(condition)])

        CommonRole.Query().Update(is_org_role=0)
        CommonRole.KeywordQuery(
            role_id=["Documentation", "Engineering"]).Update(is_org_role=1)
        subjects = set([
            u'Administrator',
            u'Dokumentation',
            u'Entwicklung',
            u'Owner, Workflow',
            u'Owner, Task',
            u'Bystander, Innocent',
        ])

        User.Query("name NOT IN ('{}')".format(
            "', '".join(subjects)
        )).Delete()

        CommonRole.Query("name_de NOT IN ('{}')".format(
            "', '".join(subjects)
        )).Delete()

        for process in [
                Process.Create(cdb_process_id="WFINTERFACE_TEST"),
                Process.Create(
                    cdb_process_id="WFINTERFACE_TEST2",
                    cdb_project_id="SOME PROJECT",
                ),
        ]:
            self.assertEqual(
                _get_subjects(process),
                subjects
            )
            self.assertEqual(_get_subjects(process, "subject_id LIKE 'ca%%'"),
                             set([u'Administrator']))

    def test_get_system_task_definitions(self):
        self.assertEqual(
            wfinterface.get_system_task_definitions().name,
            [
                u'Information',
                u'Kopie',
                u'RunOperation',
                u'Statuswechsel',
                u'Schleife',
                u'Workflowabbruch',
                u'CompleteWorkflow',  # german OP name is 'Workflow abschließen'
            ]
        )

    @mock.patch.object(systemtasks.SystemTaskDefinition, "KeywordQuery")
    def test_get_system_task_definitions_language(self, systemTaskQuery):
        """
        Returns SystemTaskDefinitions ordered by given language's name field.
        """
        # Overwriting system default language for this test
        with mock.patch.object(i18n, "default", return_value="en"):
            wfinterface.get_system_task_definitions()
        systemTaskQuery.assert_called_once_with(order_by=u'name_en')

    def test_get_picture_url(self):
        process = Process.ByKeys("JSON_TEST")
        self.assertEqual(
            wfinterface.get_picture_url(process, "/APPROOT/"),
            "/APPROOT/powerscript/cdb.apps.preview/pic?cdb_file_id="
            "42507da1-c86a-11e8-b50b-5cc5d4123f3b"
        )

    def test_get_possible_task_types(self):
        self.maxDiff = None
        self.assertEqual(
            wfinterface.get_possible_task_types(),
            {
                'heading': u'Aufgabe',
                'heading_systemtask': u'Systemaufgabe',
                'systemtask_types': [
                    {
                        'id': u'7f87cf00-f838-11e2-b1b5-082e5f0d3665',
                        'label': u'Information',
                        'type': 'cdbwf_system_task',
                    }, {
                        'id': u'91dd3340-ea12-11e2-8ad1-082e5f0d3665',
                        'label': u'Kopie',
                        'type': 'cdbwf_system_task',
                    }, {
                        'id': u'f16b8b40-706e-11e7-9aef-68f7284ff046',
                        'label': u'Operation ausf\xfchren',
                        'type': 'cdbwf_system_task',
                    }, {
                        'id': u'4daadbb0-e57a-11e2-9a44-082e5f0d3665',
                        'label': u'Status\xe4nderung',
                        'type': 'cdbwf_system_task',
                    }, {
                        'id': u'2df381c0-1416-11e9-823e-605718ab0986',
                        'label': u'Untergeordneter Workflow/Schleife',
                        'type': 'cdbwf_system_task',
                    }, {
                        'id': u'a73d9cc0-ea12-11e2-baf4-082e5f0d3665',
                        'label': u'Workflow abbrechen',
                        'type': 'cdbwf_system_task',
                    }, {
                        'id': u'1dd0542d-98a9-11e9-b598-5cc5d4123f3b',
                        'label': u'Workflow abschlie\xdfen',
                        'type': 'cdbwf_system_task',
                    },
                ],
                'task_types': [
                    {
                        'extensions': [],
                        'label': u'Pr\xfcfung',
                        'type': 'cdbwf_task_examination',
                    }, {
                        'extensions': [
                            {
                                'label': u'Extension for Tests',
                                'type': u'cs_workflowtest_task_extension',
                            },
                        ],
                        'label': u'Genehmigung',
                        'type': 'cdbwf_task_approval',
                    }, {
                        'extensions': [],
                        'label': u'Erledigung',
                        'type': 'cdbwf_task_execution',
                    },
                ],
            }
        )


class ObjectInterfaceTestCase(testcase.RollbackTestCase):
    def _get_obj(self, **kwargs):
        vals = dict(self.__obj_defaults__)
        vals.update(kwargs)
        return self.__obj_class__.Create(**vals)


class TaskInterfaceTestCase(ObjectInterfaceTestCase):
    __obj_class__ = Task
    __obj_defaults__ = {
        "cdb_process_id": "JSON_TEST",
        "task_id": "TEST",
        "cdb_classname": "cdbwf_task_execution",
    }

    def test_DeleteTask(self):
        task = self._get_obj(status=1)

        with self.assertRaises(ue.Exception):
            task.DeleteTask()

        task.Update(status=0)
        self.assertEqual(
            task.DeleteTask(),
            task.Process
        )

        parent = self._get_obj(task_id="TEST_PARENT")
        task = self._get_obj(status=0, parent_id=parent.task_id)

        self.assertEqual(
            task.DeleteTask().task_id,
            parent.task_id
        )

    def test_ModifyTask(self):
        task = self._get_obj()
        task.ModifyTask(position=1, status=1)
        self.assertEqual(task.position, 1)
        self.assertEqual(task.status, 1)

    def test_AddParameters(self):
        task = self._get_obj(cdb_classname="cdbwf_system_task")
        task.AddParameters("RULE", a="A", b="B")
        self.assertEqual(task.AllParameters.rule_name, ["RULE", "RULE"])
        self.assertEqual(task.AllParameters.name, ["a", "b"])
        self.assertEqual(task.AllParameters.value, ["A", "B"])

    def test_GetResponsiblePersonInfo(self):
        self.maxDiff = None
        task = self._get_obj()
        self.assertEqual(
            task.GetResponsiblePersonInfo("/APPROOT/"),
            {
                'id1': None,
                'id2': '',
                'name': u'',
                'picture': None,
                'subject_type': None,
            }
        )
        task.Update(subject_id="caddok", subject_type="Person")
        self.assertEqual(
            task.GetResponsiblePersonInfo("/APPROOT/"),
            {
                'id1': u'caddok',
                'id2': '',
                'name': u'Administrator',
                'picture': None,
                'subject_type': u'Person',
            }
        )
        task.Update(subject_id="Administrator", subject_type="Common Role")
        self.assertEqual(
            task.GetResponsiblePersonInfo("/APPROOT/"),
            {
                'id1': u'Administrator',
                'id2': '',
                'name': u'Administrator',
                'picture': None,
                'subject_type': u'Common Role',
            }
        )

    def test_CloseTask(self):
        self.skipTest("fails")
        task = self._get_obj(
            status=10,
            subject_id=auth.persno,
            subject_type="Person",
        )
        task.CloseTask()

    def test_RefuseTask(self):
        self.skipTest("fails")
        task = self._get_obj(
            cdb_classname="cdbwf_task_examination",
            status=10,
            subject_id=auth.persno,
            subject_type="Person",
        )
        task.RefuseTask(remark="not ok")

    def test_ForwardTask(self):
        self.skipTest("fails because operation is unavailable")
        task = self._get_obj(
            status=10,
            subject_id=auth.persno,
            subject_type="Person",
        )
        task.ForwardTask()


class TaskGroupInterfaceTestCase(ObjectInterfaceTestCase):
    __obj_class__ = TaskGroup
    __obj_defaults__ = {
        "cdb_process_id": "JSON_TEST",
        "task_id": "TEST",
        "cdb_classname": "cdbwf_aggregate_parallel",
    }

    def test_SimplifyStructure(self):
        group = self._get_obj(position=42)
        group.SimplifyStructure()
        self.skipTest("construct test cases...")

    def test_delete_taskgroup(self):
        group = self._get_obj()

        with self.assertRaises(TypeError):
            group._delete_taskgroup()

        group.Update(position=111)
        group._delete_taskgroup()
        self.assertEqual(group.IsDeleted(), True)

    def test_CreateTask(self):
        group = self._get_obj()
        task = group.CreateTask(
            "examination",
            "Title",
            subject_id="caddok",
            parameters={"a": "A", "b": "B"},
            additional={"c": "C", "d": "D"},
        )
        self.assertEqual(task.cdb_classname, "cdbwf_task_examination")
        self.assertEqual(task.title, "Title")
        self.assertEqual(task.subject_id, "caddok")


class SchemaComponentInterfaceTestCase(ObjectInterfaceTestCase):
    def test_AppendTask(self):
        self.skipTest("construct test cases...")

    def test_ReplaceTaskWithCycle(self):
        self.skipTest("construct test cases...")

    def test_MoveToPosition(self):
        self.skipTest("construct test cases...")

    def test_AddConstraint(self):
        self.skipTest("construct test cases...")

    def test_ensure_parent_has_the_right_type(self):
        self.skipTest("construct test cases...")

    def test_create_task_group_and_add_me_to_it(self):
        self.skipTest("construct test cases...")

    def test_shift_siblings(self):
        self.skipTest("construct test cases...")

    def test_create_task_for_elink(self):
        self.skipTest("construct test cases...")


class BriefcaseInterfaceTestCase(ObjectInterfaceTestCase):
    __obj_class__ = Briefcase
    __obj_defaults__ = {}

    def test_DeleteBriefcase(self):
        self.skipTest("tbd")

    def test_ModifyBriefcase(self):
        self.skipTest("tbd")

    def test_SetGlobalMeaning(self):
        self.skipTest("tbd")

    def test_SetTaskMeaning(self):
        self.skipTest("tbd")

    def test_RemoveTaskMeaning(self):
        self.skipTest("tbd")

    def test_ChangeTaskMeaning(self):
        self.skipTest("tbd")

    def test_AddObject(self):
        self.skipTest("tbd")

    def test_RemoveObject(self):
        self.skipTest("tbd")

    def test_set_meaning(self):
        self.skipTest("tbd")

    def test_AddObjectFromCmsg(self):
        self.skipTest("tbd")

    def test_AddObjectFromLink(self):
        self.skipTest("tbd")


class BriefcaseLinkInterfaceTestCase(ObjectInterfaceTestCase):
    __obj_class__ = BriefcaseLink
    __obj_defaults__ = {}

    def test_show_checkbox(self):
        link = self._get_obj()
        self.assertEqual(
            link.show_checkbox(),
            True
        )
        self.skipTest("tbd")

    def test_DeleteBriefcaseLink(self):
        self.skipTest("fails")
        link = self._get_obj()
        link.DeleteBriefcaseLink()


class ConstraintInterfaceTestCase(ObjectInterfaceTestCase):
    __obj_class__ = Constraint
    __obj_defaults__ = {}


class ProcessInterfaceTestCase(ObjectInterfaceTestCase):
    __obj_class__ = Process
    __obj_defaults__ = {
        "cdb_process_id": "TEST",
    }

    def test_AddAttachment(self):
        self.skipTest("tbd")

    def test_RemoveAttachment(self):
        self.skipTest("tbd")

    def test_AddConstraint(self):
        self.skipTest("tbd")

    def test_SaveAsTemplate(self):
        self.skipTest("tbd")

    def test_CreateTask(self):
        self.skipTest("tbd")

    def test_CreateProcess(self):
        self.skipTest("tbd")

    def test_DeleteProcess(self):
        self.skipTest("tbd")

    def test_ModifyProcess(self):
        self.skipTest("tbd")

    def test_ActivateProcess(self):
        self.skipTest("tbd")

    def test_OnHoldProcess(self):
        self.skipTest("tbd")

    def test_CancelProcess(self):
        self.skipTest("tbd")

    def test_DismissProcess(self):
        self.skipTest("tbd")

    def test_CreateBriefcase(self):
        self.skipTest("tbd")

    def test_AllowedOperationsForSelection(self):
        self.skipTest("tbd")

    def test_AppendTaskToSelection(self):
        self.skipTest("tbd")

    def test_ReplaceSelectionWithCycle(self):
        self.skipTest("tbd")

    def test_SimplifyStructure(self):
        self.skipTest("tbd")

    def test__create_task_group_for_elink(self):
        self.skipTest("tbd")

    def test__find_outer_context(self):
        self.skipTest("tbd")

    def test__find_extremal_task(self):
        self.skipTest("tbd")

    def test__get_selected_components(self):
        self.skipTest("tbd")

    def test_GetGlobalBriefcases(self):
        self.skipTest("tbd")

    def test_GetLocalBriefcases(self):
        self.skipTest("tbd")

    def test_isActivatable(self):
        self.skipTest("tbd")

    def test_isHoldableOrCancelable(self):
        self.skipTest("tbd")

    def test_isDismissable(self):
        self.skipTest("tbd")

    def test_GetSubjectCandidates(self):
        self.skipTest("tbd")

    def test_GetRoleCandidates(self):
        self.skipTest("tbd")


class FilterParameterInterfaceTestCase(ObjectInterfaceTestCase):
    __obj_class__ = FilterParameter
    __obj_defaults__ = {
        "cdb_process_id": "TEST",
    }

    def test_DeleteParameter(self):
        self.skipTest("tbd")

    def test_ModifyParameter(self):
        self.skipTest("tbd")
