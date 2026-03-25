from cdb.testcase import RollbackTestCase
from cs.platform.web.root import Root
from webtest import TestApp as Client
from cs.web.components.ui_support.dialog_hooks import DialogHook
from cdb import sqlapi
from cdb import ElementsError

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch


def find_fields(form_settings, attribute):
    for reg in form_settings['registers']:
        for field in reg['fields']:
            if attribute == field['attribute']:
                yield field


class TestDialogHookPreDisplay(RollbackTestCase):
    def test_readonly(self):
        c = Client(Root())
        response = c.get('/internal/uisupport/form/classdef/cswebtest_dialog_hook/cswebtest_dialog_hook')
        form_settings = response.json
        fields = list(find_fields(form_settings, 'cswebtest_dialog_hook.text3'))
        self.assertEquals(len(fields), 1,
                          'Expected one field for attribute cswebtest_dialog_hook.text3')
        self.assertTrue(all(map(lambda f: f['readonly'], fields)),
                        'Expected readonly to be set on all fields for attribute cswebtest_dialog_hook.text3')

    def test_mandatory(self):
        c = Client(Root())
        response = c.get('/internal/uisupport/form/classdef/cswebtest_dialog_hook/cswebtest_dialog_hook')
        form_settings = response.json
        fields = list(find_fields(form_settings, 'cswebtest_dialog_hook.text4'))
        self.assertEquals(len(fields), 1,
                          'Expected one field for attribute cswebtest_dialog_hook.text4')
        self.assertTrue(all(map(lambda f: f['mandatory'], fields)),
                        'Expected mandatory to be set on all fields cswebtest_dialog_hook.text4')

    def test_to_python_rep(self):
        with patch.object(DialogHook, 'get_fieldtype', return_value=sqlapi.SQL_DATE):
            dh = DialogHook()
            self.assertRaises(ElementsError, dh._to_python_rep, {'foo': 123})

class TestDialogHook(RollbackTestCase):
    def test_ue_exception(self):
        payload = {"ids":["raise_ue_exception"]}
        c = Client(Root())
        response = c.post_json('/internal/uisupport/form/hook', params=payload)
        self.assertTrue("raise_ue_exception" in response.json['errors'][0]['title'])
