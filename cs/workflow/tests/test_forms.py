#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access,no-value-for-parameter

"""
Module test_forms

This is the documentation for the test_forms module.
"""

import datetime
import mock

from cdb import auth
from cdb import ElementsError
from cdb import testcase
from cdb import util
from cdb.constants import kOperationCopy
from cdb.objects.cdb_file import CDB_File
from cdb.objects.operations import operation
from cdb.platform.gui import Mask
from cdb.platform.gui import MaskAttribute

from cs.workflow import forms
from cs.workflow.briefcases import Briefcase
from cs.workflow.briefcases import FolderContent
from cs.workflow.processes import Process
from cs.workflow.tasks import ExecutionTask


def setup_module():
    testcase.run_level_setup()


class DummyContext(object):
    __internal__ = ["dialog", "set_optional"]

    def __init__(self, dialog=None, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

        self.dialog = None if dialog is None else DummyContext(**dialog)
        self.set_optional = mock.Mock()

    def __iter__(self):
        for k, v in vars(self).items():
            if k not in self.__internal__:
                yield k, v

    def __getitem__(self, key):
        return getattr(self, key)

    def get_attribute_names(self):
        return [
            k
            for k in list(vars(self))
            if k not in self.__internal__
        ]

    def set(self, key, value):
        setattr(self.dialog, key, value)

    @classmethod
    def FromKeywords(cls, dialog=None, **kwargs):
        return cls(dialog, **kwargs)


class UtilityTestCase(testcase.RollbackTestCase):
    def test_transform_key(self):
        self.assertEqual(forms.transform_key("a"), "a")
        self.assertEqual(forms.transform_key(".a"), "a")
        self.assertEqual(forms.transform_key("a.a"), "a")
        self.assertEqual(
            forms.transform_key("cdb::argument.a"), "cdb::argument.a")

    def test_transform_key_prefix(self):
        self.assertEqual(forms.transform_key("a", include_prefix=True), ".a")
        self.assertEqual(forms.transform_key(".a", include_prefix=True), ".a")
        self.assertEqual(
            forms.transform_key("a.a", include_prefix=True), "a.a")
        self.assertEqual(
            forms.transform_key("cdb::argument.a", include_prefix=True),
            "cdb::argument.a")

    def test_transform_data(self):
        self.assertEqual(forms.transform_data(
            {
                ".a": "A",
                "cdbwf_form.b": "B",
                "c": "C",
                "cdb::argument.op_ctx_object_id": "O",
                "cdb::argument.op_ctx_classname": "P",
                "cdb_object_id": "X",
                "classname": "Y",
                "prefix.date_attr": datetime.date(2020, 5, 8),
                "datetime_attr": datetime.datetime(2020, 5, 8, 15, 42, 18),
                "null_date": None,
            },
            ["date_attr", "datetime_attr", "null_date"],
        ), {
            "a": "A",
            "b": "B",
            "c": "C",
            "cdb::argument.op_ctx_object_id": "O",
            "cdb::argument.op_ctx_classname": "P",
            "classname": "Y",
            "date_attr": "2020-05-08",
            "datetime_attr": "2020-05-08T15:42:18",
            "null_date": None,
        })


class FormTemplateTestCase(testcase.RollbackTestCase):
    def test_references(self):
        m = Mask.ByKeys("mask_alignment", "public")
        t = forms.FormTemplate.Create(mask_name="mask_alignment")
        f = forms.Form.Create(
            form_template_id=t.cdb_object_id, cdb_process_id="", task_id="")
        self.assertEqual(t.Masks, [m])
        self.assertEqual(t.Forms, [f])


class FormBaseTestCase(testcase.RollbackTestCase):
    def _create_data(self, mask_name="cdb_file_base"):
        self.process = Process.Create(
            cdb_process_id="TEST",
            is_template=0,
            title="cs.workflow.tests",
            subject_id=auth.persno,
            subject_type="Person",
            cdb_objektart="cdbwf_process",
            status=10,
        )
        self.task = ExecutionTask.Create(
            cdb_process_id="TEST",
            task_id="test",
            parent_id="",  # important for relship access - NULL is ignored
            status=0,
            cdb_objektart="cdbwf_task",
            position=10,
        )
        self.template = forms.FormTemplate.Create(
            mask_name=mask_name, name_de="testform")

    def _create_preset_data(self):
        self._create_data()
        self.form = forms.Form.InitializeForm(self.task, self.template)
        self.task.Reload()
        self.t2 = forms.FormTemplate.Create(
            cdb_cdate=datetime.datetime(2017, 7, 18, 10, 57, 11),
            mask_name="mask_mask")
        self.f2 = forms.Form.Create(
            form_template_id=self.t2.cdb_object_id,
            cdb_process_id=self.task.cdb_process_id,
            task_id="C")

        self.briefcase = Briefcase.ByContent(self.form)[0]

        # non-forms are applied in-order, t2 "wins"
        for i, obj in enumerate([self.template, self.t2, self.f2]):
            FolderContent.Create(
                cdb_folder_id=self.briefcase.cdb_object_id,
                cdb_content_id=obj.cdb_object_id,
                position=i)

        # prior data is kept
        self.form.write_data({"cdb_classname": "foo"})

    def _assert_preset_data(self):
        self.assertEqual(self.form.read_data(), {
            u'cdb_cdate': '2017-07-18T10:57:11',
            u'cdb_classname': "foo"
        })


class FormTestCase(FormBaseTestCase):
    def test_references(self):
        self._create_data()
        self.form = forms.Form.Create(
            cdb_process_id=self.process.cdb_process_id,
            task_id=self.task.task_id,
            form_template_id=self.template.cdb_object_id,
        )
        self.assertEqual(self.form.Template, self.template)
        self.assertEqual([(m.name, m.role_id) for m in self.form.Masks],
                         [(m.name, m.role_id) for m in Mask.ByName(
                             "cdb_file_base")])
        self.assertEqual(self.form.Process, self.process)

    def test_data_none(self):
        f = forms.Form.Create(
            form_template_id="", cdb_process_id="", task_id="")
        self.assertEqual(f.Data, "")

    def test_data_ok(self):
        contents = '{"abc": 1}'
        f = forms.Form.Create(
            form_template_id="", cdb_process_id="", task_id="")
        f.SetText("cdbwf_form_contents_txt", contents)
        self.assertEqual(f.Data, contents)

    def test_write_non_dict_data(self):
        f = forms.Form.Create(
            form_template_id="", cdb_process_id="", task_id="")

        for bad_data in ["not a dict", None, -1]:
            with self.assertRaises(ValueError):
                f.write_data(bad_data)

    def test_write_non_serializable_dict_data(self):
        self._create_data()
        f = forms.Form.InitializeForm(self.task, self.template)

        with self.assertRaises(TypeError):
            f.write_data({"cdb_classname": self})

    def test_write_and_read_data_ok(self):
        self._create_data()
        f = forms.Form.InitializeForm(self.task, self.template)
        json_data = {
            "cdb_classname": "foo",
            "cdb_cpersno": "bar",
            "cdb_lock": "no",
            "NOT_IN_MASK": "temp",
        }
        expected = {
            "cdb_classname": "foo",
            "cdb_cpersno": "bar",
            "cdb_lock": "no",
        }
        f.write_data(json_data)
        self.assertEqual(f.read_data(), expected)

    def test_preset_data_form_only(self):
        # form's own data is preset by cdbwf_submit_form only
        f = forms.Form.Create(
            form_template_id="A", cdb_process_id="B", task_id="C")
        f.preset_data()
        self.assertEqual(f.read_data(), {})

    def test_preset_data_multiple_objs(self):
        self._create_preset_data()
        self.form.preset_data()
        self._assert_preset_data()

    def test_get_empty_mandatory_fields_explicit(self):
        m = Mask.ByName("mask_alignment")[0]
        MaskAttribute.Create(
            name=m.name,
            role_id=m.role_id,
            attribut="cdb::argument.classname",
            mussfeld=1)
        MaskAttribute.Create(
            name=m.name,
            role_id=m.role_id,
            attribut="title",
            mussfeld=1)
        self.assertEqual(
            set(a.attribut for a in m.MandatoryAttributes()),
            set(["rebuild_mask_index", "cdb::argument.classname", "title"]))
        t = forms.FormTemplate.Create(mask_name="mask_alignment")
        f = forms.Form.Create(
            form_template_id=t.cdb_object_id, cdb_process_id="", task_id="")
        f.write_data({"title":"", "cdb::argument.classname": "some Name"})
        self.assertEqual(
            set(f.get_empty_mandatory_fields()),
            set(["rebuild_mask_index", "title"]))

    def test_get_empty_mandatory_fields_from_dd_context(self):
        # cdb_file_suffix mandatories: ft_name, ft_suffix
        t = forms.FormTemplate.Create(mask_name="cdb_file_suffix")
        f = forms.Form.Create(
            form_template_id=t.cdb_object_id, cdb_process_id="", task_id="")
        self.assertEqual(f.get_empty_mandatory_fields(), [])

    def test_get_form_counter(self):
        self._create_data()
        for i in range(1, 4):
            task = ExecutionTask.Create(cdb_process_id="TEST",
                                        task_id="test{}".format(i))
            form = forms.Form.InitializeForm(task, self.template)
            self.assertEqual(form._get_form_counter(), i + 1)

    def test_InitializeForm(self):
        self._create_data()
        self.form = forms.Form.InitializeForm(self.task, self.template)
        self.assertEqual(self.form.Template, self.template)
        self.assertEqual(len(self.task.EditBriefcases), 1)
        self.assertEqual(self.task.EditBriefcases[0].name,
                         "{} 1".format(self.form.joined_template_name))
        self.assertEqual(self.task.EditContent, [self.form])
        self.task_two = ExecutionTask.Create(cdb_process_id="TEST",
                                             task_id="test2")
        self.form_two = forms.Form.InitializeForm(self.task_two, self.template)
        self.assertEqual(self.task_two.EditBriefcases[0].name,
                         "{} 2".format(self.form.joined_template_name))


class FormSaveAccessTestCase(FormBaseTestCase):
    """
    (acceptance tests, really)
    Test "save" access to forms of several users in several wf/task statuses.
    """
    admin = "caddok"
    wf_owner = "wftest_wf_owner"
    task_owner = "wftest_task_owner"

    def _create_data(self, wf_status, task_status):
        super(FormSaveAccessTestCase, self)._create_data()
        self.process.Update(
            subject_id=self.wf_owner,
            subject_type="Person",
            started_by=self.wf_owner,
            status=wf_status,
        )
        self.task.Update(
            subject_id=self.task_owner,
            subject_type="Person",
            status=task_status,
        )
        self.form = forms.Form.InitializeForm(self.task, self.template)
        self.task.BriefcaseLinks.Update(extends_rights=1)
        self.assertEqual(self.task.InfoForms, [])
        self.assertEqual(self.task.EditForms, [self.form])

    def _assert_access(self, exp_admin, exp_wf_owner, exp_task_owner):
        expected_access = [exp_admin, exp_wf_owner, exp_task_owner]
        is_access = [
            self.form.CheckAccess("save", persno=p)
            for p in [self.admin, self.wf_owner, self.task_owner]
        ]

        self.assertEqual(
            expected_access,
            is_access,
            """unexpected 'save' access:
                wf status {wf_status}, task status {task_status}
                    USER       IS   EXPECTED
                    caddok     {is_access[0]:d}     {expected_access[0]:d}
                    wf owner   {is_access[1]:d}     {expected_access[1]:d}
                    task owner {is_access[2]:d}     {expected_access[2]:d}
            """.format(
                wf_status=self.process.status,
                task_status=self.task.status,
                is_access=is_access,
                expected_access=expected_access,
            )
        )

    def test_save_access_new_task(self):
        self._create_data(10, 0)
        self._assert_access(True, True, False)

    def test_save_access_running_task(self):
        self._create_data(10, 10)
        self._assert_access(True, True, True)

    def test_save_access_completed_task(self):
        self._create_data(10, 20)
        self._assert_access(True, True, False)

    def test_save_access_completed_workflow(self):
        self._create_data(20, 20)
        # NOTE: cdbwf_task_active is independent of wf status
        self._assert_access(False, False, False)


class TaskFormTestCase(FormBaseTestCase):
    def test_references(self):
        self._create_data()
        self.form = forms.Form.InitializeForm(self.task, self.template)
        self.assertEqual(self.task.InfoForms, [])
        self.assertEqual(self.task.EditForms, [self.form])
        self.task.BriefcaseLinks.Update(iotype=0)
        self.task.Reload()
        self.assertEqual(self.task.InfoForms, [self.form])
        self.assertEqual(self.task.EditForms, [])

    def test_check_form_data_ok(self):
        self._create_data()
        self.form = forms.Form.InitializeForm(self.task, self.template)
        self.form.write_data({"rebuild_mask_index": 0})
        self.assertEqual(self.task.check_form_data(), None)

    def test_check_form_data_fail(self):
        self._create_data("mask_alignment")
        self.form = forms.Form.InitializeForm(self.task, self.template)

        with self.assertRaises(util.ErrorMessage):
            self.task.check_form_data()

    def test_check_form_data_on_op_close_task(self):
        self._create_data()
        self.form = forms.Form.InitializeForm(self.task, self.template)

        with self.assertRaises(ElementsError):
            self.task.ChangeState(
                self.task.COMPLETED.status,
                check_access=False
            )

    def test_preset_data(self):
        self._create_preset_data()
        self.task.preset_data()
        self._assert_preset_data()

    def test_preset_data_on_ready_post(self):
        self._create_preset_data()
        self.task.ChangeState(
            self.task.EXECUTION,
            check_access=False
        )
        self.assertEqual(self.task.status, self.task.EXECUTION.status)
        self._assert_preset_data()

    def test_on_cdbwf_add_task_form_now(self):
        self._create_data()

        self.assertEqual(len(self.template.Forms), 0)
        self.task.on_cdbwf_add_task_form_now(DummyContext.FromKeywords(
            {"form_template_id": self.template.cdb_object_id}))
        self.template.Reload()
        self.assertEqual(len(self.template.Forms), 1)

        for ctx in [
            DummyContext.FromKeywords({"form_template_id": "?"}),
            DummyContext.FromKeywords(None),
        ]:
            with self.assertRaises(util.ErrorMessage):
                self.task.on_cdbwf_add_task_form_now(ctx)

    def _on_cdbwf_submit_form_pre_mask(self):
        self.form = forms.Form.InitializeForm(self.task, self.template)

        self.assertEqual(self.form.read_data(), {})

        sibling = CDB_File.Create(cdbf_object_id="TEST")
        FolderContent.Create(
            cdb_folder_id=self.task.EditBriefcases[0].cdb_object_id,
            cdb_content_id=sibling.cdb_object_id)

        ctx = DummyContext.FromKeywords(
            {},
            **{"cdb::argument.form_object_id": self.form.cdb_object_id})
        self.form.on_cdbwf_submit_form_pre_mask(ctx)

        expected_form_data = {
            'cdb_classname': u'cdb_file',
            'cdbf_object_id': u'TEST',
            'mapped_cdb_lock_name': u'',
            'mapped_cpersno_name': u'',
            'mapped_mpersno_name': u'',
        }

        expected_dialog_vals = expected_form_data.copy()
        expected_dialog_vals.update({
            'cdbf_hidden': 0
        })

        self.assertEqual(dict(ctx.dialog), expected_dialog_vals)
        self.assertEqual(self.form.read_data(), expected_form_data)
        return ctx

    def test_on_cdbwf_submit_form_pre_mask_0(self):
        "new workflow: fields are optional"
        self._create_data()
        self.process.Update(is_template=0, status=0)
        ctx = self._on_cdbwf_submit_form_pre_mask()
        ctx.set_optional.assert_called_once()

    def test_on_cdbwf_submit_form_pre_mask_0(self):
        "workflow template: fields are optional"
        self._create_data()
        self.process.Update(is_template=1, status=0)
        ctx = self._on_cdbwf_submit_form_pre_mask()
        ctx.set_optional.assert_called_once()

    def test_on_cdbwf_submit_form_pre_mask_10(self):
        "running workflow: fields are mandatory"
        self._create_data()
        self.process.Update(is_template=0, status=10)
        ctx = self._on_cdbwf_submit_form_pre_mask()
        ctx.set_optional.assert_not_called()

    def test_on_cdbwf_submit_form_now(self):
        self._create_data()
        self.form = forms.Form.InitializeForm(self.task, self.template)

        self.assertEqual(self.form.read_data(), {})
        self.form.on_cdbwf_submit_form_now(DummyContext.FromKeywords(
            {},
            **{"cdb::argument.form_object_id": self.form.cdb_object_id}))
        self.assertEqual(self.form.read_data(), {})
        self.form.on_cdbwf_submit_form_now(DummyContext.FromKeywords(
            {"cdb_classname": "foo"},
            **{"cdb::argument.form_object_id": self.form.cdb_object_id}))
        self.assertEqual(self.form.read_data(), {"cdb_classname": "foo"})


class TestFormReferenceOnCopy(FormBaseTestCase):
    """
    E044793: When copying a process, briefcase content references to forms have
    to be updated to point at the form copy
    """
    def _setup_template(self):
        self._create_data()
        self.form = forms.Form.InitializeForm(self.task, self.template)
        self.assertEqual(len(self.process.AllContent), 1)
        self.assertEqual(self.process.AllContent[0].cdb_object_id,
                         self.form.cdb_object_id)
        self.assertEqual(self.process.AllContent[0].cdb_process_id,
                         self.process.cdb_process_id)

    def _assert_forms_copied(self, copy):
        def _get_form_ids(process):
            process.Reload()
            return set([
                x.cdb_object_id for x in process.AllContent
                if isinstance(x, forms.Form)
            ])

        proc_form_ids = _get_form_ids(self.process)
        copy_form_ids = _get_form_ids(copy)
        overlap = proc_form_ids.intersection(copy_form_ids)

        self.assertEqual(len(proc_form_ids), len(copy_form_ids))
        self.assertEqual(overlap, set())

    def test_copy_process(self):
        self._setup_template()
        copy = operation(kOperationCopy, self.process)
        self._assert_forms_copied(copy)
