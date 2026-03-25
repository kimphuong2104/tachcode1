# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from __future__ import print_function
import collections
from cdb import util
from cdb.objects import operations
from cdb.validationkit.SwitchRoles import run_with_roles
from cs.classification import api as classification_api
from cs.requirements import RQMSpecObject, RQMSpecification
from cs.requirements.exceptions import (
    InvalidVariableValueTypeError,
    InvalidRichTextAttributeValueType,
    MissingVariableValueError
)
from cs.requirements.richtext import (XHTML_NAMESPACES_DICT,
                                      RichTextModifications, RichTextVariables)
from cs.requirements.tests.utils import RequirementsTestCase


class TestRichTextVariables(RequirementsTestCase):

    def __init__(self, *args, **kwargs):
        super(TestRichTextVariables, self).__init__(
            *args, need_uberserver=False, **kwargs
        )

    def test_valid_variable_id_serialization(self):
        variable_id = "valid_variable_id"
        self.assertEqual(
            RichTextVariables.get_variable_xhtml(variable_id),
            u"<xhtml:object type=\"text/plain\"><xhtml:param name=\"variable_id\" value=\"{}\"></xhtml:param></xhtml:object>".format(
                variable_id
            )
        )

    def test_invalid_variable_id_serialization(self):
        variable_id = "invalid.variable.id"
        with self.assertRaises(ValueError):
            RichTextVariables.get_variable_xhtml(variable_id)


class TestRichTextModifications(RequirementsTestCase):

    def __init__(self, *args, **kwargs):
        super(TestRichTextModifications, self).__init__(
            *args, need_uberserver=True, **kwargs
        )
        self.cb_called = False

    def test_patch_xhtml_empty(self):
        xhtml = ""
        self.cb_called = False

        def track_cb_calls(tree):
            self.cb_called = True
        patched_xhtml = RichTextModifications.change_partial_xhtml(
            xhtml_text=xhtml, change_cbs=[track_cb_calls]
        )
        self.assertEqual(patched_xhtml, xhtml)
        self.assertEqual(self.cb_called, False)

    def test_patch_xhtml_with_plaintext(self):
        xhtml = "some plain text"
        self.cb_called = False

        def track_cb_calls(tree):
            self.cb_called = True
        patched_xhtml = RichTextModifications.change_partial_xhtml(
            xhtml_text=xhtml, change_cbs=[track_cb_calls]
        )
        self.assertEqual(patched_xhtml, xhtml)
        self.assertEqual(self.cb_called, False)

    def test_patch_xhtml_simple(self):
        xhtml = "<xhtml:div><xhtml:b></xhtml:b></xhtml:div>"
        self.cb_called = False

        def say_hello_world(tree):
            self.cb_called = True
            for b in tree.xpath(
                "//xhtml:b",
                namespaces=XHTML_NAMESPACES_DICT
            ):
                b.text = "Hello World"

        patched_xhtml = RichTextModifications.change_partial_xhtml(
            xhtml_text=xhtml, change_cbs=[say_hello_world]
        )
        self.assertEqual(patched_xhtml, "<xhtml:div><xhtml:b>Hello World</xhtml:b></xhtml:div>")
        self.assertEqual(self.cb_called, True)

    def test_patch_xhtml_complex(self):
        xhtml = """<xhtml:div><xhtml:div>Some Text<xhtml:b>Hello Bob<xhtml:i>test1 test2</xhtml:i>test3</xhtml:b>test4<xhtml:b>Hello Alice</xhtml:b></xhtml:div><xhtml:div>test5</xhtml:div></xhtml:div>"""

        def say_hello_world(tree):
            for b in tree.xpath(
                "//xhtml:b",
                namespaces=XHTML_NAMESPACES_DICT
            ):
                b.text = "Hello World"

        patched_xhtml = RichTextModifications.change_partial_xhtml(
            xhtml_text=xhtml, change_cbs=[say_hello_world]
        )
        expected = """<xhtml:div><xhtml:div>Some Text<xhtml:b>Hello World<xhtml:i>test1 test2</xhtml:i>test3</xhtml:b>test4<xhtml:b>Hello World</xhtml:b></xhtml:div><xhtml:div>test5</xhtml:div></xhtml:div>"""
        self.assertEqual(patched_xhtml, expected)

        def say_only_hello_world(tree):
            for b in tree.xpath(
                "//xhtml:b",
                namespaces=XHTML_NAMESPACES_DICT
            ):
                b.text = "Hello World"
                for elem in b:
                    b.remove(elem)

        patched_xhtml = RichTextModifications.change_partial_xhtml(
            xhtml_text=xhtml, change_cbs=[say_only_hello_world]
        )
        expected = """<xhtml:div><xhtml:div>Some Text<xhtml:b>Hello World</xhtml:b>test4<xhtml:b>Hello World</xhtml:b></xhtml:div><xhtml:div>test5</xhtml:div></xhtml:div>"""
        self.assertEqual(patched_xhtml, expected)

    def test_force_serializations(self):
        before_xhtml = """<xhtml:div><xhtml:b></xhtml:b></xhtml:div>"""
        expected_xhtml = """<xhtml:div><xhtml:b></xhtml:b></xhtml:div>"""
        keys = ["cdbrqm_spec_object_desc_de", "cdbrqm_spec_object_desc_en"]
        patched_attributes = RichTextModifications.force_serializations({k: before_xhtml for k in keys})
        for k in keys:
            self.assertEqual(patched_attributes.get(k), expected_xhtml)

    def test_get_richtexts_by_iso_code_with_no_variables(self):
        spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        req = spec.Requirements[0]
        req_text_de = req.GetText('cdbrqm_spec_object_desc_de')
        req_text_en = req.GetText('cdbrqm_spec_object_desc_en')
        if not req_text_en:
            req_text_en = RichTextModifications.EMPTY_DIV
        richtexts = RichTextModifications.get_richtexts_by_iso_code(obj=req)
        self.assertEqual(req_text_de, richtexts.get('de'))
        self.assertEqual(req_text_en, richtexts.get('en'))

    def test_get_richtexts_by_iso_code_with_variables_and_values(self):
        spec = RQMSpecification.KeywordQuery(name=u"report-test-specification")[0]
        req = spec.Requirements[0]
        variable_id = 'RQM_RATING_RQM_COMMENT_EXTERN'
        variable_richtext = """<xhtml:div>{}</xhtml:div>""".format(
            RichTextVariables.get_variable_xhtml(variable_id=variable_id)
        )
        req.SetText("cdbrqm_spec_object_desc_de", variable_richtext)
        req.SetText("cdbrqm_spec_object_desc_en", variable_richtext)
        classification_data = classification_api.get_new_classification(
            ["RQM_RATING"], narrowed=False
        )
        variable_value = '### test comment ###'
        classification_data['properties']['RQM_RATING_RQM_COMMENT_EXTERN'][0]['value'] = variable_value
        classification_api.update_classification(req, classification_data)

        richtexts = RichTextModifications.get_richtexts_by_iso_code(obj=req)
        richtext_with_values = """<xhtml:div><xhtml:object type="text/plain"><xhtml:param name="variable_id" value="{vid}"></xhtml:param>{val}</xhtml:object></xhtml:div>""".format(
            vid=variable_id,
            val=variable_value
        )
        self.assertEqual(richtexts.get('de'), richtext_with_values)
        self.assertEqual(richtexts.get('en'), richtext_with_values)

    def test_replace_filled_variables_with_text_nodes_empty_variable_value(self):
        obj_xhtml = RichTextVariables.get_variable_xhtml(variable_id='RQM_TEST_VARIABLE_001')
        xhtml_text = "<xhtml:div>{}</xhtml:div>".format(obj_xhtml)
        patched_xhtml = RichTextModifications.replace_filled_variables_with_text_nodes(xhtml_text)
        expected = """<xhtml:div><xhtml:span class="variables variables-without-value" title="RQM_TEST_VARIABLE_001"></xhtml:span></xhtml:div>"""
        self.assertEqual(patched_xhtml, expected)
        patched_xhtml = RichTextModifications.replace_filled_variables_with_text_nodes(
            xhtml_text.replace('xhtml:', ''),
            ns_prefix=''
        )
        expected = expected.replace('xhtml:', '')
        self.assertEqual(patched_xhtml, expected)

    def test_replace_filled_variables_with_text_nodes_empty_variable_value_old_serialization(self):
        obj_xhtml = """<xhtml:object type="text/plain" data=""><xhtml:param name="variable_id" value="RQM_TEST_VARIABLE_001"></xhtml:param></xhtml:object>"""
        xhtml_text = "<xhtml:div>{}</xhtml:div>".format(obj_xhtml)
        patched_xhtml = RichTextModifications.replace_filled_variables_with_text_nodes(xhtml_text)
        expected = """<xhtml:div><xhtml:span class="variables variables-without-value" title="RQM_TEST_VARIABLE_001"></xhtml:span></xhtml:div>"""
        self.assertEqual(patched_xhtml, expected)
        patched_xhtml = RichTextModifications.replace_filled_variables_with_text_nodes(
            xhtml_text.replace('xhtml:', ''),
            ns_prefix=''
        )
        expected = expected.replace('xhtml:', '')
        self.assertEqual(patched_xhtml, expected)

    def test_replace_filled_variables_with_text_nodes_non_empty_variable_value_old_serialization(self):
        obj_xhtml = """<xhtml:object type="text/plain" data="Some Text Value"><xhtml:param name="variable_id" value="RQM_TEST_VARIABLE_001"></xhtml:param>Some Text Value</xhtml:object>"""
        xhtml_text = "<xhtml:div>{}</xhtml:div>".format(obj_xhtml)
        patched_xhtml = RichTextModifications.replace_filled_variables_with_text_nodes(xhtml_text)
        expected = """<xhtml:div><xhtml:span class="variables" title="RQM_TEST_VARIABLE_001">Some Text Value</xhtml:span></xhtml:div>"""
        self.assertEqual(patched_xhtml, expected)
        patched_xhtml = RichTextModifications.replace_filled_variables_with_text_nodes(
            xhtml_text.replace('xhtml:', ''),
            ns_prefix=''
        )
        expected = """<div><span class="variables" title="RQM_TEST_VARIABLE_001">Some Text Value</span></div>"""
        expected = expected.replace('xhtml:', '')
        self.assertEqual(patched_xhtml, expected)

    def test_replace_filled_variables_with_text_nodes_non_empty_variable_value(self):
        obj_xhtml = RichTextVariables.get_variable_xhtml(variable_id='RQM_TEST_VARIABLE_001').replace(
            '</xhtml:object>', 'Some Text Value</xhtml:object>'
        )
        xhtml_text = "<xhtml:div>{}</xhtml:div>".format(obj_xhtml)
        patched_xhtml = RichTextModifications.replace_filled_variables_with_text_nodes(xhtml_text)
        expected = """<xhtml:div><xhtml:span class="variables" title="RQM_TEST_VARIABLE_001">Some Text Value</xhtml:span></xhtml:div>"""
        self.assertEqual(patched_xhtml, expected)
        patched_xhtml = RichTextModifications.replace_filled_variables_with_text_nodes(
            xhtml_text.replace('xhtml:', ''),
            ns_prefix=''
        )
        expected = """<div><span class="variables" title="RQM_TEST_VARIABLE_001">Some Text Value</span></div>"""
        expected = expected.replace('xhtml:', '')
        self.assertEqual(patched_xhtml, expected)

    def test_set_variables_simple_filled_variable(self):
        obj_xhtml = RichTextVariables.get_variable_xhtml(variable_id='RQM_TEST_VARIABLE_001')
        xhtml_text = "<xhtml:div>{}</xhtml:div>".format(obj_xhtml)
        variable_values = {'RQM_TEST_VARIABLE_001': 'Some Test Value'}
        patched_xhtml = RichTextModifications.set_variables(
            xhtml_text=xhtml_text,
            variable_values=variable_values
        )
        expected = "<xhtml:div>{}</xhtml:div>".format(obj_xhtml.replace('</xhtml:object>', 'Some Test Value</xhtml:object>'))
        self.assertEqual(patched_xhtml, expected)

    def test_set_variables_complex_filled_variable(self):
        obj_xhtml = RichTextVariables.get_variable_xhtml(variable_id='RQM_TEST_VARIABLE_001')
        base_text = "<xhtml:div>Some Text Before{}Some Text behind</xhtml:div>"
        xhtml_text = base_text.format(obj_xhtml)
        variable_values = {'RQM_TEST_VARIABLE_001': 'Some Test Value'}
        patched_xhtml = RichTextModifications.set_variables(
            xhtml_text=xhtml_text,
            variable_values=variable_values
        )
        expected = base_text.format(obj_xhtml.replace('</xhtml:object>', 'Some Test Value</xhtml:object>'))
        self.assertEqual(patched_xhtml, expected)

    def test_set_variables_simple_filled_variable_replace(self):
        obj_xhtml = RichTextVariables.get_variable_xhtml(variable_id='RQM_TEST_VARIABLE_001')
        xhtml_text = "<xhtml:div>{}</xhtml:div>".format(obj_xhtml)
        variable_values = {'RQM_TEST_VARIABLE_001': 'Some Test Value'}
        patched_xhtml = RichTextModifications.set_variables(
            xhtml_text=xhtml_text,
            variable_values=variable_values,
            replace_variable_nodes_with_values=True
        )
        expected = "<xhtml:div>{}</xhtml:div>".format('Some Test Value')
        self.assertEqual(patched_xhtml, expected)

    def test_set_variables_complex_filled_variable_replace(self):
        obj_xhtml = RichTextVariables.get_variable_xhtml(variable_id='RQM_TEST_VARIABLE_001')
        base_text = "<xhtml:div>Some Text Before{}Some Text behind</xhtml:div>"
        xhtml_text = base_text.format(obj_xhtml)
        variable_values = {'RQM_TEST_VARIABLE_001': 'Some Test Value'}
        patched_xhtml = RichTextModifications.set_variables(
            xhtml_text=xhtml_text,
            variable_values=variable_values,
            replace_variable_nodes_with_values=True
        )
        expected = base_text.format('Some Test Value')
        self.assertEqual(patched_xhtml, expected)

    def test_set_variables_complex2_filled_variable_replace(self):
        obj_xhtml = RichTextVariables.get_variable_xhtml(variable_id='RQM_TEST_VARIABLE_001')
        base_text = "<xhtml:div><xhtml:b>Some Tag with Content</xhtml:b>Some Text Before{}Some Text behind</xhtml:div>"
        xhtml_text = base_text.format(obj_xhtml)
        variable_values = {'RQM_TEST_VARIABLE_001': 'Some Test Value'}
        patched_xhtml = RichTextModifications.set_variables(
            xhtml_text=xhtml_text,
            variable_values=variable_values,
            replace_variable_nodes_with_values=True
        )
        expected = base_text.format('Some Test Value')
        self.assertEqual(patched_xhtml, expected)

    def test_set_variables_simple_missing_variable_replace(self):
        obj_xhtml = RichTextVariables.get_variable_xhtml(variable_id='RQM_TEST_VARIABLE_001')
        xhtml_text = "<xhtml:div>{}</xhtml:div>".format(obj_xhtml)
        variable_values = {}
        patched_xhtml = RichTextModifications.set_variables(
            xhtml_text=xhtml_text,
            variable_values=variable_values
        )
        self.assertEqual(patched_xhtml, xhtml_text.format(''))

    def test_set_variables_simple_missing_variable(self):
        obj_xhtml = RichTextVariables.get_variable_xhtml(variable_id='RQM_TEST_VARIABLE_001')
        xhtml_text = "<xhtml:div>{}</xhtml:div>".format(obj_xhtml)
        variable_values = {}
        patched_xhtml = RichTextModifications.set_variables(
            xhtml_text=xhtml_text,
            variable_values=variable_values
        )
        self.assertEqual(patched_xhtml, xhtml_text)

    def test_set_variables_complex_missing_variable(self):
        obj_xhtml = RichTextVariables.get_variable_xhtml(variable_id='RQM_TEST_VARIABLE_001')
        base_text = "<xhtml:div>Some Text Before{}Some Text behind</xhtml:div>"
        xhtml_text = base_text.format(obj_xhtml)
        variable_values = {}
        patched_xhtml = RichTextModifications.set_variables(
            xhtml_text=xhtml_text,
            variable_values=variable_values
        )
        self.assertEqual(patched_xhtml, xhtml_text)

    def test_set_variables_simple_missing_variable_raise(self):
        obj_xhtml = RichTextVariables.get_variable_xhtml(variable_id='RQM_TEST_VARIABLE_001')
        xhtml_text = "<xhtml:div>{}</xhtml:div>".format(obj_xhtml)
        variable_values = {}
        with self.assertRaises(MissingVariableValueError):
            RichTextModifications.set_variables(
                xhtml_text=xhtml_text,
                variable_values=variable_values,
                raise_for_empty_value=True
            )

    def test_set_variables_only_modify_variable_object_tags(self):
        base_text = """<xhtml:div><xhtml:object data="/some_path_to_image" type="image/png"></xhtml:object>Some Text Before{}Some Text behind{}</xhtml:div>"""
        obj_xhtml = RichTextVariables.get_variable_xhtml(variable_id='RQM_TEST_VARIABLE_001')
        xhtml_video_fake_tag = """<xhtml:object data="/path" type="video/mp4"><xhtml:param name="some_other" value="also"></xhtml:param>Some Description</xhtml:object>"""
        xhtml_text = base_text.format(obj_xhtml, xhtml_video_fake_tag)
        variable_values = {'RQM_TEST_VARIABLE_001': 'Some Test Value'}
        patched_xhtml = RichTextModifications.set_variables(
            xhtml_text=xhtml_text,
            variable_values=variable_values
        )
        expected = base_text.format(
            obj_xhtml.replace('</xhtml:object>', 'Some Test Value</xhtml:object>'), xhtml_video_fake_tag
        )
        self.assertEqual(patched_xhtml, expected)

    def test_set_variables_and_file_links_modify_only_known_file_links_and_variables_from_db(self):
        base_text = """<xhtml:div><xhtml:object data="/path_to_file" type="image/png"></xhtml:object>Some Text Before{}Some Text behind{}</xhtml:div>"""
        obj_xhtml = RichTextVariables.get_variable_xhtml(variable_id='RQM_TEST_VARIABLE_001')
        xhtml_video_fake_tag = """<xhtml:object data="/path" type="video/mp4"><xhtml:param name="some_other" value="also"></xhtml:param>Some Description</xhtml:object>"""
        xhtml_text = base_text.format(obj_xhtml, xhtml_video_fake_tag)
        variable_values = {'RQM_TEST_VARIABLE_001': 'Some Test Value'}
        object_data_replacements = {'/path_to_file': '/path_to_rest_api'}
        patched_xhtml = RichTextModifications.set_variables_and_file_links(
            xhtml_text,
            object_data_replacements,
            variable_values,
            serialization_method=None,
            raise_for_empty_value=True,
            language='de'
        )
        expected = base_text.format(
            obj_xhtml.replace('</xhtml:object>', 'Some Test Value</xhtml:object>'), xhtml_video_fake_tag
        ).replace('/path_to_file', '/path_to_rest_api')
        self.assertEqual(patched_xhtml, expected)

    def test_set_variables_and_file_links_modify_only_known_file_links_and_variables_to_db(self):
        base_text = """<xhtml:div><xhtml:object data="/path_to_rest_api" type="image/png"></xhtml:object>Some Text Before{}Some Text behind{}</xhtml:div>"""
        obj_xhtml = RichTextVariables.get_variable_xhtml(variable_id='RQM_TEST_VARIABLE_001')
        obj_xhtml_with_value = obj_xhtml.replace('</xhtml:object>', 'Some Test Value</xhtml:object>')
        xhtml_video_fake_tag = """<xhtml:object data="/path" type="video/mp4"><xhtml:param name="some_other" value="also"></xhtml:param>Some Description</xhtml:object>"""
        xhtml_text = base_text.format(obj_xhtml_with_value, xhtml_video_fake_tag)
        object_data_replacements = {'/path_to_rest_api': '/path_to_file'}
        patched_xhtml = RichTextModifications.set_variables_and_file_links(
            xhtml_text,
            object_data_replacements,
            variable_values=None,
            serialization_method=None,
            raise_for_empty_value=False,
            language='de'
        )
        expected = base_text.format(
            obj_xhtml, xhtml_video_fake_tag
        ).replace('/path_to_rest_api', '/path_to_file')
        self.assertEqual(patched_xhtml, expected)

    def test_patch_xhtml_simple_utf8(self):
        xhtml = "<xhtml:div><xhtml:b>Hello Wörld</xhtml:b></xhtml:div>".encode('utf-8')
        self.cb_called = False

        def say_hello_world(tree):
            self.cb_called = True
            for b in tree.xpath(
                "//xhtml:b",
                namespaces=XHTML_NAMESPACES_DICT
            ):
                b.text = "Hello Würld"

        patched_xhtml = RichTextModifications.change_partial_xhtml(
            xhtml_text=xhtml, change_cbs=[say_hello_world]
        )
        self.assertEqual(patched_xhtml, "<xhtml:div><xhtml:b>Hello Würld</xhtml:b></xhtml:div>")
        self.assertEqual(self.cb_called, True)

    def test_get_variable_modified_attribute_values_utf8_variable_value(self):
        variable_id = 'RQM_RICHTEXT_MODIFICATION_VARIABLE_001'
        obj_xhtml = RichTextVariables.get_variable_xhtml(variable_id=variable_id)
        xhtml_text = "<xhtml:div>RichTextModifications Req 001 öäü {}</xhtml:div>".format(obj_xhtml)
        @run_with_roles(["public", "Requirements: Manager"])
        def _prepare_data():
            self.copied_spec_id = None
            self.spec = operations.operation(
                'CDB_Create', RQMSpecification, name='Test RichTextModifications'
            )
            self.req1 = operations.operation(
                'CDB_Create',
                RQMSpecObject,
                specification_object_id=self.spec.cdb_object_id,
                cdbrqm_spec_object_desc_en=xhtml_text
            )
        _prepare_data()
        attribute_values = {}
        for k in ['cdbrqm_spec_object_desc_en']:
            attribute_values[k] = self.req1.GetText(k)
        with self.assertRaises(InvalidVariableValueTypeError):
            modifications = RichTextModifications.get_variable_modified_attribute_values(
                objs=self.req1,
                attribute_values=attribute_values,
                from_db=True,
                raise_for_empty_value=True,
                variable_values_by_id={
                    self.req1.cdb_object_id: {
                        variable_id: 'Hello Wörld'.encode('utf-8')
                    }
                }
            )
            self.assertIn('Hello Wörld', modifications['cdbrqm_spec_object_desc_en'])

    def test_get_variable_modified_attribute_values_utf8_attribute_value(self):
        variable_id = 'RQM_RICHTEXT_MODIFICATION_VARIABLE_001'
        obj_xhtml = RichTextVariables.get_variable_xhtml(variable_id=variable_id)
        xhtml_text = "<xhtml:div>RichTextModifications Req 001 öäü {}</xhtml:div>".format(obj_xhtml)
        @run_with_roles(["public", "Requirements: Manager"])
        def _prepare_data():
            self.copied_spec_id = None
            self.spec = operations.operation(
                'CDB_Create', RQMSpecification, name='Test RichTextModifications'
            )
            self.req1 = operations.operation(
                'CDB_Create',
                RQMSpecObject,
                specification_object_id=self.spec.cdb_object_id,
                cdbrqm_spec_object_desc_en=xhtml_text
            )
        _prepare_data()
        attribute_values = {}
        for k in ['cdbrqm_spec_object_desc_en']:
            attribute_values[k] = self.req1.GetText(k).encode('utf-8')
        with self.assertRaises(InvalidRichTextAttributeValueType):
            modifications = RichTextModifications.get_variable_modified_attribute_values(
                objs=self.req1,
                attribute_values=attribute_values,
                from_db=True,
                raise_for_empty_value=True,
                variable_values_by_id={
                    self.req1.cdb_object_id: {
                        variable_id: 'Hello Wörld'
                    }
                }
            )
            self.assertIn('Hello Wörld', modifications['cdbrqm_spec_object_desc_en'])

    def test_get_variable_modified_attribute_values_single(self):
        variable_id = 'RQM_RICHTEXT_MODIFICATION_VARIABLE_001'
        obj_xhtml = RichTextVariables.get_variable_xhtml(variable_id=variable_id)
        xhtml_text = "<xhtml:div>RichTextModifications Req 001 öäü {}</xhtml:div>".format(obj_xhtml)
        @run_with_roles(["public", "Requirements: Manager"])
        def _prepare_data():
            self.copied_spec_id = None
            self.spec = operations.operation(
                'CDB_Create', RQMSpecification, name='Test RichTextModifications'
            )
            self.req1 = operations.operation(
                'CDB_Create',
                RQMSpecObject,
                specification_object_id=self.spec.cdb_object_id,
                cdbrqm_spec_object_desc_en=xhtml_text
            )
        _prepare_data()
        attribute_values = {}
        for k in ['cdbrqm_spec_object_desc_en']:
            attribute_values[k] = self.req1.GetText(k)
        modifications = RichTextModifications.get_variable_modified_attribute_values(
            objs=self.req1,
            attribute_values=attribute_values,
            from_db=True,
            raise_for_empty_value=True,
            variable_values_by_id={
                self.req1.cdb_object_id: {
                    variable_id: 'Hello Wörld'
                }
            }
        )
        self.assertIn('Hello Wörld', modifications['cdbrqm_spec_object_desc_en'])
    
    def test_get_variable_modified_attribute_values_multiple(self):
        variable_id = 'RQM_RICHTEXT_MODIFICATION_VARIABLE_001'
        obj_xhtml = RichTextVariables.get_variable_xhtml(variable_id=variable_id)
        xhtml_text1 = "<xhtml:div>RichTextModifications Req 001 öäü {}</xhtml:div>".format(obj_xhtml)
        xhtml_text2 = "<xhtml:div>RichTextModifications Req 002 öäü {}</xhtml:div>".format(obj_xhtml)
        @run_with_roles(["public", "Requirements: Manager"])
        def _prepare_data():
            self.copied_spec_id = None
            self.spec = operations.operation(
                'CDB_Create', RQMSpecification, name='Test RichTextModifications'
            )
            self.req1 = operations.operation(
                'CDB_Create',
                RQMSpecObject,
                specification_object_id=self.spec.cdb_object_id,
                cdbrqm_spec_object_desc_en=xhtml_text1
            )
            self.req2 = operations.operation(
                'CDB_Create',
                RQMSpecObject,
                specification_object_id=self.spec.cdb_object_id,
                cdbrqm_spec_object_desc_en=xhtml_text2
            )
        _prepare_data()
        attribute_values = collections.defaultdict(dict)
        objs = [self.req1, self.req2]
        for obj in objs:
            for k in ['cdbrqm_spec_object_desc_en']:
                attribute_values[obj.cdb_object_id][k] = self.req1.GetText(k)
        modifications = RichTextModifications.get_variable_modified_attribute_values(
            objs=objs,
            attribute_values=attribute_values,
            from_db=True,
            raise_for_empty_value=True,
            variable_values_by_id={
                self.req1.cdb_object_id: {
                    variable_id: 'Hello Wörld Req1'
                },
                self.req2.cdb_object_id: {
                    variable_id: 'Hello Wärld Req2'
                }
            }
        )
        self.assertIn('Hello Wörld Req1', modifications[0]['cdbrqm_spec_object_desc_en'])
        self.assertIn('Hello Wärld Req2', modifications[1]['cdbrqm_spec_object_desc_en'])

    def test_patch_richtext_with_inner_namespace_attribute_for_xhtml(self):
        xhtml = """<xhtml:div><xhtml:div><xhtml:span xmlns:xhtml="http://www.w3.org/1999/xhtml">test</xhtml:span></xhtml:div></xhtml:div>"""
        self.cb_called = False

        def track_cb_calls(tree):
            self.cb_called = True
        patched_xhtml = RichTextModifications.change_partial_xhtml(
            xhtml_text=xhtml, change_cbs=[track_cb_calls]
        )
        self.assertEqual(patched_xhtml, """<xhtml:div><xhtml:div><xhtml:span>test</xhtml:span></xhtml:div></xhtml:div>""")
        self.assertEqual(self.cb_called, True)
