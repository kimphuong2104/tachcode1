#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

"""
Module test_systemtasks

This is the documentation for the test_systemtasks module.
"""

import datetime
import mock
import unittest
from cdb import auth, rte, sqlapi, testcase, ElementsError
from cdb.objects import ByID
from cdb.objects.org import User
from cdb.platform.mom.operations import OperationConfig
from cs.workflow import briefcases, forms, misc, processes, systemtasks, tasks

COPY_OBJECTS = "91dd3340-ea12-11e2-8ad1-082e5f0d3665"
STATUS_CHANGE = "4daadbb0-e57a-11e2-9a44-082e5f0d3665"
GENERATE_INFO = "7f87cf00-f838-11e2-b1b5-082e5f0d3665"
ABORT_PROCESS = "a73d9cc0-ea12-11e2-baf4-082e5f0d3665"
RUN_OPERATION = "f16b8b40-706e-11e7-9aef-68f7284ff046"
RUN_LOOP = "2df381c0-1416-11e9-823e-605718ab0986"

try:
    # only soft-require to make tests runnable in cs.all env
    from cs.workflowtest import cs_workflow_test_meta_operation
except ImportError:
    cs_workflow_test_meta_operation = None

only_with_cs_workflowtest = unittest.skipIf(
    not cs_workflow_test_meta_operation,
    "Skipped because cs.workflowtest."
    "cs_workflow_test_meta_operation is required"
)


def setup_module():
    testcase.run_level_setup()


class DummyContext:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class SystemTaskDefinitionTestCase(testcase.RollbackTestCase):
    def test_references(self):
        systask_def = ByID("4daadbb0-e57a-11e2-9a44-082e5f0d3665")
        self.assertEqual(
            systask_def.Parameters.name,
            [
                "target_state"
            ]
        )
        self.assertEqual(
            systask_def.Images.cdbf_name,
            ['4daadbb0-e57a-11e2-9a44-082e5f0d3665.png']
        )
        self.assertEqual(
            systask_def.Image.cdbf_name,
            '4daadbb0-e57a-11e2-9a44-082e5f0d3665.png'
        )
        self.assertEqual(
            systask_def.Name["de"],
            'Status\xe4nderung'
        )


class ParameterDefinitionTestCase(testcase.RollbackTestCase):
    def test_references(self):
        param_def = ByID("d0dfdb40-e960-11e2-b40b-082e5f0d3665")
        self.assertEqual(
            param_def.SystemTaskDefinition.cdb_object_id,
            '4daadbb0-e57a-11e2-9a44-082e5f0d3665'
        )


class UtilityTestCase(testcase.RollbackTestCase):
    def test_get_status_change_unlock_param(self):
        for classname, expected in [
                ("document", 2),
                ("model", 2),
                ("cdb_wsp", 2),
                ("part", None),
        ]:
            self.assertEqual(
                systemtasks.get_status_change_unlock_param(classname),
                expected)

        with self.assertRaises(ValueError):
            systemtasks.get_status_change_unlock_param(None)

        with self.assertRaises(TypeError):
            systemtasks.get_status_change_unlock_param(1)

    __op_name__ = "TEST_OPERATION"

    def test_get_operation_config(self):
        def _op_config(applicability, classname, delete=True):
            if delete:
                OperationConfig.KeywordQuery(name=self.__op_name__).Delete()
            OperationConfig.Create(name=self.__op_name__,
                                   applicability=applicability,
                                   classname=classname)

        def _test(expected):
            self.assertEqual(
                systemtasks.get_operation_config(self.__op_name__),
                expected)

        OperationConfig.KeywordQuery(name=self.__op_name__).Delete()
        _test((False, set(), set()))

        _op_config("Meta", "")
        _test((True, set(), set()))

        _op_config("Meta", "X")
        _test((True, set(), set()))

        _op_config("Class", "X")
        _test((False, set(["X"]), set()))

        _op_config("whatever", "X")
        _op_config("whatever", "cdbwf_form", delete=0)
        _test((False, set(), set(["X"])))

        _op_config("Meta", "Z")
        _op_config("Class", "X", delete=0)
        _op_config("whatever", "cdbwf_form", delete=0)
        _op_config("SingleObject", "Y", delete=0)
        _op_config("MultipleObjects", "", delete=0)
        _test((True, set(["X"]), set(["Y", ""])))

    def test_index_content_by_classname(self):
        for value in [None, 1]:
            with self.assertRaises(TypeError):
                systemtasks.index_content_by_classname(value)

        for value in ["test", [1], [None], ["test"]]:
            with self.assertRaises(AttributeError):
                systemtasks.index_content_by_classname(value)

        self.assertEqual(
            systemtasks.index_content_by_classname([]),
            (set(), {}))

        form = forms.Form.Create(
            cdb_process_id="",
            task_id="",
            form_template_id="1"
        )
        wf_one = processes.Process.Create(cdb_process_id="TEST_ONE")
        wf_two = processes.Process.Create(cdb_process_id="TEST_TWO")

        self.assertEqual(
            systemtasks.index_content_by_classname([wf_one, form, wf_two]),
            (set(["cdbwf_form", "cdbwf_process"]), {
                "cdbwf_form": [form],
                "cdbwf_process": [wf_one, wf_two],
            }))


class SystemTaskBaseTest(testcase.RollbackTestCase):
    @classmethod
    def setUpClass(cls):
        super(SystemTaskBaseTest, cls).setUpClass()
        briefcases.BriefcaseContentWhitelist.Query().Delete()

    def _create_systask(self, definition):
        self.process = processes.Process.Create(
            cdb_process_id="TEST-SYSTASK",
            subject_id=auth.persno,
            subject_type="Person",
            status=0,
            cdb_objektart="cdbwf_process",
            is_template=0,
        )
        self.task = tasks.SystemTask.Create(
            cdb_process_id=self.process.cdb_process_id,
            task_id="TEST1",
            title="TEST1",
            task_definition_id=definition,
            position=10,
            parent_id="",
            subject_id=auth.persno,
            subject_type="Person",
            status=0,
            cdb_objektart="cdbwf_task",
            uses_global_maps=1)

        if definition == STATUS_CHANGE:
            tasks.FilterParameter.Create(
                cdb_process_id=self.task.cdb_process_id,
                task_id=self.task.task_id,
                name="target_state")

    def _create_briefcase(self, link_to, iotype, task_id=None):
        briefcase = briefcases.Briefcase.Create(**{
            "briefcase_id": briefcases.Briefcase.new_briefcase_id(),
            "cdb_process_id": link_to.cdb_process_id,
            "name": "Test",
        })
        briefcases.BriefcaseLink.Create(**{
            "briefcase_id": briefcase.briefcase_id,
            "cdb_process_id": link_to.cdb_process_id,
            "task_id": task_id if task_id is not None else getattr(link_to, "task_id", ""),
            "iotype": briefcases.IOType[iotype].value,
            "extends_rights": 0,
        })
        return briefcase


class TaskPreconditionsTestCase(testcase.RollbackTestCase):
    def test_get_violated_process_start_preconditions_systask(self):
        systask = tasks.SystemTask(cdb_process_id="TEST", task_id="TEST")
        no_subject = systask.get_violated_process_start_preconditions()
        self.assertEqual(
            no_subject,
            "Für die Systemaufgabe ': ' kann keine Definition "
            "gefunden werden."
        )

        # make systask a "status_change" task
        systask.Update(
            subject_id="caddok",
            subject_type="Person",
            task_definition_id=STATUS_CHANGE)
        systask.Reload()
        errors = systask.get_violated_process_start_preconditions()
        self.assertEqual(
            errors,
            'Die Aufgabe ": " enthält keine lokale Mappe und '
            "greift nicht auf globale Mappen zu. / "
            "Die Aufgabe ': ' braucht die folgenden fehlenden "
            "Parameter: 'target_state'"
        )

        tasks.FilterParameter.Create(cdb_process_id=systask.cdb_process_id,
                                     task_id=systask.task_id,
                                     name="target_state")
        systask.Update(uses_global_maps=1)
        systask.Reload()
        ok = systask.get_violated_process_start_preconditions()
        self.assertEqual(ok, "")

        # create persistent briefcases to make refs work
        local_briefcase = briefcases.Briefcase.Create(
            cdb_process_id=systask.cdb_process_id,
            task_id=systask.task_id,
            briefcase_id=99)
        briefcases.BriefcaseLink.Create(
            cdb_process_id=systask.cdb_process_id,
            task_id=systask.task_id,
            briefcase_id=local_briefcase.briefcase_id,
            iotype=0)
        systask.Update(uses_global_maps=0)
        systask.Reload()
        ok = systask.get_violated_process_start_preconditions()
        self.assertEqual(ok, "")


class StatusChangeTestCase(SystemTaskBaseTest):
    def test_status_change_no_int(self):
        for target in ["a", "", "1.0"]:
            with self.assertRaises(ValueError):
                systemtasks.status_change(None, None, target)

        with self.assertRaises(TypeError):
            systemtasks.status_change(None, None, None)

    def test_status_change_no_content(self):
        for content in [None, ""]:
            with self.assertRaises(TypeError):
                systemtasks.status_change(None, content, 1)

        for content in [{"info": []}, {"edit": []}]:
            with self.assertRaises(KeyError):
                systemtasks.status_change(None, content, 1)

    def test_status_change_ok(self):
        self._create_systask(STATUS_CHANGE)
        self.process.activate_process()
        self.task.Reload()
        self.assertEqual(self.task.status, 10)
        systemtasks.status_change(self.task, {
            "info": [self.task],
            "edit": [],
        }, 20)
        self.assertEqual(self.task.status, 20)

    def test_status_change_list(self):
        self._create_systask(STATUS_CHANGE)
        self.process.activate_process()
        self.task.Reload()
        self.assertEqual(self.task.status, 10)
        systemtasks.status_change(self.task, {
            "info": [self.task],
            "edit": [],
        }, [20, -1])
        self.assertEqual(self.task.status, 20)

    def test_status_change_error(self):
        self._create_systask(STATUS_CHANGE)
        self.assertEqual(self.task.status, 0)
        with self.assertRaises(RuntimeError) as error:
            with testcase.error_logging_disabled():
                systemtasks.status_change(self.task, {
                    "info": [self.task],
                    "edit": [],
                }, [20, -1])

        self.assertEqual(
            str(error.exception),
            "Eine Statusänderung kann nicht durchgeführt werden.\n"
            "Entweder es gibt keinen Zielstatus"
            " oder Sie haben keine Berechtigung einen Statuswechsel vorzunehmen.\n"
            "\n"
            "- 10,0: TEST1"
        )


class CopyObjectsTestCase(SystemTaskBaseTest):
    def test_copy_objects_no_edit_briefcase(self):
        self._create_systask(COPY_OBJECTS)
        with self.assertRaises(RuntimeError):
            systemtasks.copy_objects(self.task, None)

    def test_copy_objects_no_info_content(self):
        self._create_systask(COPY_OBJECTS)
        self._create_briefcase(self.task, "edit")
        for content in [None, ""]:
            with self.assertRaises(TypeError):
                systemtasks.copy_objects(self.task, content)

        for content in [{"edit": []}]:
            with self.assertRaises(KeyError):
                systemtasks.copy_objects(self.task, content)

    def test_copy_objects(self):
        self._create_systask(COPY_OBJECTS)
        edit = self._create_briefcase(self.task, "edit")
        self.assertEqual(len(edit.Content), 0)
        systemtasks.copy_objects(self.task, {"info": [self.process]})
        self.assertEqual(len(edit.Content), 1)

    def test_copy_objects_and_unlock_copy(self):
        self.skipTest("to be implemented")


class CreateIndexTestCase(SystemTaskBaseTest):
    def test_create_new_index_no_edit_briefcase(self):
        self._create_systask(COPY_OBJECTS)
        with self.assertRaises(RuntimeError):
            systemtasks.create_new_index(self.task, None)

    def test_create_new_index_no_info_content(self):
        self._create_systask(COPY_OBJECTS)
        self._create_briefcase(self.task, "edit")
        for content in [None, ""]:
            with self.assertRaises(TypeError):
                systemtasks.create_new_index(self.task, content)

        for content in [{"edit": []}]:
            with self.assertRaises(KeyError):
                systemtasks.create_new_index(self.task, content)

    def test_create_new_index(self):
        self.skipTest("to be implemented")


class InfoMessageTestCase(SystemTaskBaseTest):
    def test_InfoMessage_references(self):
        self._create_systask(GENERATE_INFO)
        info = systemtasks.InfoMessage.Create(
            cdb_process_id=self.process.cdb_process_id,
            task_id=self.task.task_id)
        self.assertEqual(info.Process, self.process)
        self.assertEqual(info.RootProcess, self.process)
        self.assertEqual(info.Task, self.task)

    def test_InfoMessage_getNotificationTitle(self):
        self._create_systask(GENERATE_INFO)
        info = systemtasks.InfoMessage.Create(
            cdb_process_id=self.process.cdb_process_id,
            task_id=self.task.task_id)
        self.assertEqual(
            info.getNotificationTitle(None),
            "Notification from Workflow: None")

    def test_InfoMessage_getNotificationTemplateName(self):
        self._create_systask(GENERATE_INFO)
        info = systemtasks.InfoMessage.Create(
            cdb_process_id=self.process.cdb_process_id,
            task_id=self.task.task_id)
        self.assertEqual(
            info.getNotificationTemplateName(None), "cdbwf_info_message.html")

    def test_InfoMessage_getNotificationReceiver_no_subject(self):
        self._create_systask(GENERATE_INFO)
        info = systemtasks.InfoMessage.Create(
            cdb_process_id=self.process.cdb_process_id,
            task_id=self.task.task_id)
        with self.assertRaises(AttributeError):
            info.getNotificationReceiver(None)

    def test_InfoMessage_getNotificationReceiver(self):
        self._create_systask(GENERATE_INFO)
        info = systemtasks.InfoMessage.Create(
            cdb_process_id=self.process.cdb_process_id,
            task_id=self.task.task_id,
            subject_id=auth.persno,
            subject_type="Person")
        user = User.ByKeys(auth.persno)
        user.Update(e_mail="")
        self.assertEqual(info.getNotificationReceiver(None), [{"to": []}])
        user.Update(e_mail="abc@def.org", name="username")
        sqlapi.SQLupdate(
            "cdb_usr_setting SET value = 1 "
            "WHERE setting_id = 'user.email_wf_info'"
        )
        self.assertEqual(
            info.getNotificationReceiver(None),
            [{"to": [("abc@def.org", "username")]}])

    @mock.patch.dict(
        rte.environ,
        {
            "CADDOK_PREFER_LEGACY_URLS": None,
            "CADDOK_WWWSERVICE_URL": "BASE",
        }
    )
    def test_InfoMessage_setNotificationContext(self):
        misc.prefer_web_urls.cache_clear()
        self._create_systask(GENERATE_INFO)
        global_edit = self._create_briefcase(self.process, "edit")
        local_edit = self._create_briefcase(self.task, "edit")
        info = systemtasks.InfoMessage.Create(
            cdb_process_id=self.process.cdb_process_id,
            task_id=self.task.task_id)

        notification_ctx = DummyContext()
        info.setNotificationContext(notification_ctx)

        self.assertEqual(
            notification_ctx.task_manager_url,
            f"BASE/info/workflow_info/{info.cdb_object_id}",
        )

        with self.assertRaises(AttributeError):
            _ = notification_ctx.briefcases

        briefcases.FolderContent.Create(
            cdb_folder_id=global_edit.cdb_object_id,
            cdb_content_id=self.process.cdb_object_id)
        briefcases.FolderContent.Create(
            cdb_folder_id=local_edit.cdb_object_id,
            cdb_content_id=self.task.cdb_object_id)
        global_edit.Reload()

        info.setNotificationContext(notification_ctx)
        self.assertEqual(
            notification_ctx.briefcases, [local_edit, global_edit])

    def test_generate_info_message_no_subject(self):
        self._create_systask(GENERATE_INFO)
        for kwargs in [{"subject_id": "caddok"}, {"subject_type": "Person"}]:
            with self.assertRaises(KeyError):
                systemtasks.generate_info_message(self.task, None, **kwargs)

    def test_generate_info_message(self):
        self._create_systask(GENERATE_INFO)
        self.assertEqual(
            systemtasks.InfoMessage.KeywordQuery(
                cdb_process_id=self.process.cdb_process_id),
            [])
        systemtasks.generate_info_message(
            self.task, None, subject_id=auth.persno, subject_type="Person")
        self.assertEqual(
            len(systemtasks.InfoMessage.KeywordQuery(
                cdb_process_id=self.process.cdb_process_id,
                subject_id=auth.persno,
                subject_type="Person",
                is_active=1)),
            1)


class RunLoopTestCase(SystemTaskBaseTest):
    def test_run_loop(self):
        self.skipTest("tbd")
        self._create_systask(RUN_LOOP)
        systemtasks.run_loop(
            self.task,
            {
                "info": [],
                "edit": []
            },
        )


class RunOperationTestCase(SystemTaskBaseTest):
    def test_get_form_data_none(self):
        for invalid_content in [None, 1, "test"]:
            with self.assertRaises(TypeError):
                systemtasks.get_form_data(invalid_content)

        with self.assertRaises(KeyError):
            systemtasks.get_form_data({"info": []})

        result = systemtasks.get_form_data({"info": [], "edit": []})
        self.assertEqual(result, {})

    def _create_form(self, vals, json_data):
        templ = {"mask_name": "cdbwf_system_task"}
        templates = forms.FormTemplate.KeywordQuery(**templ)
        if templates:
            template = templates[0]
        else:
            template = forms.FormTemplate.Create(**templ)
        vals["form_template_id"] = template.cdb_object_id

        form = forms.Form.Create(**vals)
        form.write_data(json_data)
        form.Reload()
        self.assertEqual(form.read_data(), json_data)
        return form

    def test_get_form_data_edit_overwriting_info(self):
        info = self._create_form(
            {"cdb_process_id": "", "task_id": "1"},
            {
                "cdb_project_id": "project_val",
                "position": "position_val",
            })
        edit = self._create_form(
            {"cdb_process_id": "", "task_id": "2"},
            {
                "title": "title_val",
                "position": "position_val2",
                "cdb_classname": "X",
            })

        result = systemtasks.get_form_data({
            "info": [info],
            "edit": [edit],
        })
        self.assertEqual(result, {
            "cdb_classname": "X",
            "cdb_project_id": "project_val",
            "position": "position_val2",
            "title": "title_val",
        })

    def test_convert_form_data(self):
        with self.assertRaises(TypeError):
            systemtasks.convert_form_data("cdb_organization", None)

        with self.assertRaises(ValueError):
            systemtasks.convert_form_data(None, {})

        self.assertEqual(
            systemtasks.convert_form_data("cdb_organization", {}),
            {}
        )

        self.assertEqual(
            systemtasks.convert_form_data(
                "cdb_organization",
                {
                    "cdb_mdate": None,
                    "cdb_cdate": datetime.datetime(2019, 7, 25, 14, 44, 1),
                    "name": None,
                }
            ),
            {
                "cdb_cdate": "25.07.2019 14:44:01",
                "name": None,
            }
        )

        self.assertEqual(
            systemtasks.convert_form_data(
                "cdb_organization",
                {
                    "cdb_mdate": None,
                    "cdb_cdate": datetime.date(2019, 7, 25),
                    "name": None,
                }
            ),
            {
                "cdb_cdate": "25.07.2019 00:00:00",
                "name": None,
            }
        )

        self.assertEqual(
            systemtasks.convert_form_data(
                "cdb_organization",
                {
                    "cdb_mdate": "2019-07-25T10:11:12",
                    "cdb_cdate": "2019-07-25T00:00:00",
                    "name": None,
                }
            ),
            {
                "cdb_mdate": "25.07.2019 10:11:12",
                "cdb_cdate": "25.07.2019 00:00:00",
                "name": None,
            }
        )

    def test_run_operation_obj_no_form(self):
        self._create_systask(RUN_OPERATION)
        original_values = dict(self.task)

        result = systemtasks.run_operation(
            self.task,
            {"info": [], "edit": [self.task]},
            "CDB_ShowObject"
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(dict(result[0]), original_values)

    def _test_run_operation_obj(self, date_form_value):
        self._create_systask(RUN_OPERATION)
        json_data = {
            "title": "changed",
            "position": self.task.position,
            "deadline": date_form_value,
            "not_in_mask": "foo"
        }
        expected_data = {
            "title": "changed",
            "position": self.task.position,
            "deadline": date_form_value,
        }
        form = self._create_form_date(
            {
                "cdb_process_id": self.process.cdb_process_id,
                "task_id": self.task.task_id,
            },
            json_data,
            "deadline",
            expected_data
        )

        systemtasks.run_operation(
            self.task,
            {"info": [], "edit": [form, self.task]},
            "CDB_Modify"
        )
        self.assertEqual(self.task.title, "changed")

    def test_run_operation_obj_date(self):
        self._test_run_operation_obj(
            datetime.date(2019, 7, 26)
        )
        self.assertEqual(
            self.task.deadline,
            datetime.date(2019, 7, 26)
        )

    def test_run_operation_obj_empty_str(self):
        self._test_run_operation_obj("")
        self.assertEqual(self.task.deadline, None)

    def test_run_operation_obj_no_date(self):
        self._test_run_operation_obj(None)
        self.assertEqual(self.task.deadline, None)

    def test_run_operation_obj_empty_date_str(self):
        self._test_run_operation_obj("")
        self.assertEqual(self.task.deadline, None)

    def test_run_operation_cls_no_form(self):
        self._create_systask(RUN_OPERATION)

        result = systemtasks.run_operation(
            self.task,
            {"info": [], "edit": []},
            "CDB_Create"
        )
        self.assertEqual(len(result), 0)

        # CDB_Create /wo pkeys always fails - find a better test case
        with self.assertRaises(ElementsError):
            with testcase.error_logging_disabled():
                systemtasks.run_operation(
                    self.task,
                    {"info": [], "edit": [self.task]},
                    "CDB_Create"
                )

    def _create_form_date(self, vals, json_data, date_attr, expected_result):
        templ = {"mask_name": "test_run_operation"}
        templates = forms.FormTemplate.KeywordQuery(**templ)
        if templates:
            template = templates[0]
        else:
            template = forms.FormTemplate.Create(**templ)
        vals["form_template_id"] = template.cdb_object_id

        form = forms.Form.Create(**vals)
        form.write_data(json_data)
        form.Reload()

        if isinstance(json_data[date_attr],
                      (datetime.date, datetime.datetime)):
            expected_result[date_attr] = json_data[date_attr].isoformat()

        self.assertEqual(form._get_date_attrs(), set([date_attr]))
        self.assertDictEqual(form.read_data(), expected_result)

        return form

    def _test_run_operation_cls(self, date_form_value):
        self._create_systask(RUN_OPERATION)
        self._create_briefcase(self.task, "edit")

        self.json_data = {
            "cdb_process_id": self.process.cdb_process_id,
            "position": 20.0,
            "task_definition_id": COPY_OBJECTS,
            "deadline": date_form_value,
        }
        self.info = self._create_form_date(
            {
                "cdb_process_id": self.process.cdb_process_id,
                "task_id": self.task.task_id,
            },
            self.json_data,
            "deadline",
            self.json_data
        )

        result = systemtasks.run_operation(
            self.task,
            {"info": [self.info], "edit": []},
            "CDB_Create"
        )
        self.assertEqual(len(self.process.AllTasks), 1)
        self.assertEqual(len(result), 0)

        result = systemtasks.run_operation(
            self.task,
            {"info": [self.info], "edit": [self.task]},
            "CDB_Create"
        )
        self.assertEqual(
            set(self.process.AllTasks.task_definition_id),
            set([RUN_OPERATION, COPY_OBJECTS])
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].position, 20)
        self.assertEqual(result[0].task_definition_id, COPY_OBJECTS)
        return result[0]

    def test_run_operation_cls_date(self):
        new_task = self._test_run_operation_cls(
            datetime.date(2019, 7, 26)
        )
        self.assertEqual(
            new_task.deadline,
            datetime.date(2019, 7, 26)
        )
        self.json_data["deadline"] = datetime.date(2019, 7, 26)
        self.assertEqual(
            self.info.read_data(convert_dates=True),
            self.json_data
        )

    def test_run_operation_cls_iso_str(self):
        new_task = self._test_run_operation_cls("2019-07-26T00:00:00")
        self.assertEqual(
            new_task.deadline,
            datetime.date(2019, 7, 26)
        )
        self.json_data["deadline"] = datetime.datetime(2019, 7, 26)
        self.assertEqual(
            self.info.read_data(convert_dates=True),
            self.json_data
        )

    def test_run_operation_cls_legacy_str(self):
        new_task = self._test_run_operation_cls("26.07.2019 00:00:00")
        self.assertEqual(
            new_task.deadline,
            datetime.date(2019, 7, 26)
        )
        self.json_data["deadline"] = datetime.datetime(2019, 7, 26)
        self.assertEqual(
            self.info.read_data(convert_dates=True),
            self.json_data
        )

    def test_run_operation_cls_empty_str(self):
        new_task = self._test_run_operation_cls("")
        self.assertEqual(new_task.deadline, None)
        self.assertEqual(
            self.info.read_data(convert_dates=True),
            self.json_data
        )

    def test_run_operation_cls_no_date(self):
        new_task = self._test_run_operation_cls(None)
        self.assertEqual(new_task.deadline, None)
        self.assertEqual(
            self.info.read_data(convert_dates=True),
            self.json_data
        )

    def test_run_operation_cls_localbf_attachment(self):
        self._create_systask(RUN_OPERATION)

        self._create_briefcase(self.task, "edit")

        info = self._create_form(
            {
                "cdb_process_id": self.process.cdb_process_id,
                "task_id": self.task.task_id,
            },
            {
                "cdb_process_id": self.process.cdb_process_id,
                "position": 20.0,
                "task_definition_id": COPY_OBJECTS,
                "deadline": "2020-05-05",
            }
        )

        self.assertEqual(len(self.process.Briefcases), 0)
        for bf in self.task.Briefcases:
            self.assertEqual(len(bf.Content), 0)

        systemtasks.run_operation(
            self.task,
            {"info": [info], "edit": [self.task]},
            "CDB_Create"
        )

        for bf in self.task.Briefcases:
            self.assertEqual(len(bf.Content), 1)

    def test_run_operation_cls_globalbf_attachment(self):
        self._create_systask(RUN_OPERATION)

        self._create_briefcase(self.task, "edit", "")

        info = self._create_form(
            {
                "cdb_process_id": self.process.cdb_process_id,
                "task_id": self.task.task_id,
            },
            {
                "cdb_process_id": self.process.cdb_process_id,
                "position": 20.0,
                "task_definition_id": COPY_OBJECTS,
                "deadline": "2020-05-05T00:00:00",
            }
        )

        self.assertEqual(len(self.task.Briefcases), 0)
        self.assertEqual(len(self.process.Briefcases[0].Content), 0)

        systemtasks.run_operation(
            self.task,
            {"info": [info], "edit": [self.task]},
            "CDB_Create"
        )

        self.assertEqual(len(self.process.Briefcases[0].Content), 1)

    @only_with_cs_workflowtest
    def test_run_operation_meta_no_form(self):
        self._create_systask(RUN_OPERATION)
        test_process = processes.Process.ByKeys("JSON_TEST")
        original_tasks = len(test_process.AllTasks)
        result = systemtasks.run_operation(
            self.task,
            {"info": [], "edit": []},
            "cs_workflow_test_meta_operation"
        )

        self.assertEqual(result, None)
        self.assertEqual(len(test_process.AllTasks), 1 + original_tasks)

    def _test_run_operation_meta(self, date_form_value):
        self._create_systask(RUN_OPERATION)
        json_data = {
            "cdb_process_id": self.process.cdb_process_id,
            "task_id": "TEST_META_OP",
            "position": 20.0,
            "task_definition_id": COPY_OBJECTS,
            "deadline": date_form_value,
        }

        form = self._create_form_date(
            {
                "cdb_process_id": self.process.cdb_process_id,
                "task_id": self.task.task_id,
            },
            json_data,
            "deadline",
            json_data
        )
        self.assertEqual(len(self.process.AllTasks), 1)
        result = systemtasks.run_operation(
            self.task,
            {"info": [form], "edit": []},
            "cs_workflow_test_meta_operation"
        )

        self.assertEqual(result, None)
        self.assertEqual(
            set(self.process.AllTasks.task_definition_id),
            set([RUN_OPERATION, COPY_OBJECTS])
        )
        return tasks.Task.ByKeys(
            cdb_process_id=self.process.cdb_process_id,
            task_id="TEST_META_OP",
        )

    @only_with_cs_workflowtest
    def test_run_operation_meta_date(self):
        self._test_run_operation_meta(
            datetime.date(2019, 7, 26),
        )

    @only_with_cs_workflowtest
    def test_run_operation_meta_no_date(self):
        new_task = self._test_run_operation_meta(None)
        self.assertEqual(new_task.deadline, None)

    @only_with_cs_workflowtest
    def test_run_operation_meta_empty_date_str(self):
        new_task = self._test_run_operation_meta("")
        self.assertEqual(new_task.deadline, None)


class ConversionTestCase(SystemTaskBaseTest):
    def test_convert_files(self):
        self.skipTest("to be implemented")

    def test_convert_files_done(self):
        self.skipTest("to be implemented")

    def test_convert_files_failed(self):
        self.skipTest("to be implemented")
