#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

"""
Module test_webforms_rest_app

This is the documentation for the test_webforms_rest_app module.
"""

from urllib.parse import urljoin
from webtest import TestApp as Client

from cdb import testcase

from cs.platform.web.root import Root
from cs.workflow import forms
from cs.workflow.briefcases import FolderContent
from cs.workflow.tasks import ExecutionTask
from cs.workflow.webforms import rest_app
from cs.workflow.webforms.main import MOUNTEDPATH


def setup_module():
    testcase.run_level_setup()


class TaskFormsModelBase(testcase.RollbackTestCase):
    def _create_data(self):
        self.task = ExecutionTask.Create(cdb_process_id="TEST", task_id="TEST")
        self.model = rest_app.TaskFormsModel(self.task.cdb_object_id)
        self.assertEqual(self.task, self.model.task)
        self.assertEqual(self.model.indexed_forms, {"edit": {}, "info": {}})

    def _create_form(self, mask_name=None):
        self.template = forms.FormTemplate.Create(
            mask_name=mask_name or "mask_mask")
        self.form = forms.Form.InitializeForm(self.task, self.template)
        self.task.Reload()
        self.model.indexed_forms = self.model._get_indexed_forms()


class TaskFormsModelTestCase(TaskFormsModelBase):
    def test_indexed_forms(self):
        self._create_data()
        self._create_form()
        self.assertEqual(
            self.model._get_indexed_forms(),
            {"edit": {self.form.cdb_object_id: self.form}, "info": {}})
        self.task.BriefcaseLinks[0].Update(iotype=0)
        self.task.Reload()
        self.assertEqual(
            self.model._get_indexed_forms(),
            {"info": {self.form.cdb_object_id: self.form}, "edit": {}})

    def test_read_data(self):
        self._create_data()
        self._create_form()
        self.assertEqual(self.model._read_data(self.form), {
            'dialog_name': u'mask_mask',
            'cdb_object_id': self.form.cdb_object_id,
            'data': {},
            'name': u' 1 - ',
            'system:navigation_id': u'{}'.format(
                self.form.cdb_object_id),
            'system:classname': u'cdbwf_form',
        })

    def test_read_data_no_form(self):
        self._create_data()
        self._create_form()

        for bad_val in [None, self.task, "X", -1]:
            with self.assertRaises(AttributeError):
                self.model._read_data(bad_val)

    def test_getFormsData(self):
        self._create_data()
        self._create_form()
        self.temp_one = self.template
        self.form_one = self.form
        self._create_form("cs_tasks_class")
        both_forms = sorted(
            [self.form.cdb_object_id, self.form_one.cdb_object_id])

        self.assertEqual(
            sorted(
                [x["cdb_object_id"] for x in self.model.getFormsData(
                    None)["edit"]]),
            both_forms)
        self.assertEqual(
            sorted(
                [x["cdb_object_id"] for x in self.model.getFormsData(
                    [self.form_one.cdb_object_id,
                     self.form.cdb_object_id])["edit"]]),
            both_forms)
        self.assertEqual(
            [x["cdb_object_id"] for x in self.model.getFormsData(
                [self.form.cdb_object_id])["edit"]],
            [self.form.cdb_object_id])


class HTTPError(Exception):
    def __init__(self, errno, reason):
        super(HTTPError, self).__init__()
        self.errno = errno
        self.reason = reason

    def __str__(self):
        return "{} ({})".format(self.errno, self.reason)


class JSONAPITestCase(TaskFormsModelBase):
    url = "/internal{}/".format(MOUNTEDPATH)

    def setUp(self):
        super(JSONAPITestCase, self).setUp()
        self.client = Client(Root())

    def _get_url(self, relative_url=None):
        return urljoin(self.url, relative_url)

    def get(self, url, params=None):
        response = self.client.get(url, expect_errors=True, params=params)
        if response.status_code != 200:
            raise HTTPError(response.status_code, response.status)
        return response.json

    def post(self, url, json):
        response = self.client.post_json(url, json, expect_errors=True)
        if response.status_code != 200:
            raise HTTPError(response.status_code, response.status)
        return response.json

    def fail_get(self, url, status):
        with self.assertRaises(HTTPError) as ctx:
            self.get(url)
        self.assertEqual(ctx.exception.errno, status)

    def fail_post(self, url, json, status):
        with self.assertRaises(HTTPError) as ctx:
            self.post(url, json)
        self.assertEqual(ctx.exception.errno, status)

    def test_get_task_forms_no_task(self):
        self.fail_get(self._get_url("abc"), 404)

    def test_get_task_forms_ok(self):
        self.maxDiff = None
        self._create_data()
        self.assertEqual(self.get(self._get_url(self.task.cdb_object_id)), {
            u'info': [],
            u'edit': [],
        })
        self._create_form()

        # make sure preset oid overwrites form's oid
        FolderContent.Create(
            cdb_folder_id=self.task.BriefcaseLinks[0].Briefcase.cdb_object_id,
            cdb_content_id=self.template.cdb_object_id)

        form_data = {
            u'info': [],
            u'edit': [{
                u'dialog_name': u'mask_mask',
                u'cdb_object_id': self.form.cdb_object_id,
                u'data': {
                    u'.joined_status_name': u'',
                    u'.joined_status_name_de': u'',
                    u'.joined_status_name_en': u'',
                    u'.mapped_cpersno': u'',
                    u'.mapped_mpersno': u'',
                    u'.mask_name': u'mask_mask',
                    u'.name': u'',
                },
                u'name': u' 1 - ',
                u'system:navigation_id': u'{}'.format(
                    self.form.cdb_object_id),
                u'system:classname': u'cdbwf_form',
            }],
        }

        self.assertEqual(
            self.get(self._get_url(self.task.cdb_object_id)), form_data)
        self.assertEqual(
            self.get(self._get_url(self.task.cdb_object_id),
                     params={"forms": [self.form.cdb_object_id]}),
            form_data)
        self.assertEqual(
            self.get(self._get_url(self.task.cdb_object_id),
                     params={"forms": ["test"]}),
            {"info": [], "edit": []})
