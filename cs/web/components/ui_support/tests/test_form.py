#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tests for the form REST-API.
"""

from __future__ import absolute_import
import six
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb.platform.mom.entities import CDBClassDef
from cdb import sqlapi
from cdb.testcase import RollbackTestCase, error_logging_disabled
from cs.platform.web.rest import support
from cs.platform.web.rest.generic import convert
from cs.platform.web.root import Root
from webtest import TestApp as Client
import datetime
import unittest
from cs.restgenericfixture import BarBaz
from cs.webtest import RestReferer, RestRefererNM, RestRefererNMLink, RestReferenceChild


CLASS_FORM_URL_PATTERN = \
    "/internal/uisupport/form/operation/class/%(op_name)s/%(clazz)s"


RELSHIP_FORM_URL_PATTERN = \
    "/internal/uisupport/form/operation/relship" \
    "/%(referer_class)s/%(rest_keys)s/%(relship_name)s/%(op_name)s/%(target_class)s"


class TestFormAPI(RollbackTestCase):
    """
    Tests for the form REST API.
    """
    def setUp(self):
        self.maxDiff = None
        try:
            from cs.webtest import OpActivation
        except ImportError:
            raise unittest.SkipTest("this test needs cs.webtest")

        super(TestFormAPI, self).setUp()
        self.obj = OpActivation.Create(attr_int=42,
                                       label="Test",
                                       attr_date=datetime.datetime.utcnow())
        self.subclass_obj = BarBaz.Create(
            name='BarBaz',
            description='One bar a day keeps the baz away.')


    def _check_result(self, response, has_classdef):
        """
        Check dialog info for dialog cswebtest_op_activation.
        """
        self.assertIn("registers", response)
        register_list = response.json_body["registers"]
        self.assertIsInstance(register_list, list,
                              "Should return a list of registers")
        self.assertEqual(len(register_list), 1, "Should return single register")
        register = register_list[0]
        self.assertIsInstance(register, dict,
                              "Register should be a dictionary")
        self.assertEqual(register["label"], "Datenblatt")
        self.assertIn("fields", register)
        field_list = register["fields"]
        self.assertEqual(len(field_list), 3, "Register should have three fields")
        form_field = field_list[0]
        self.assertIsInstance(form_field, dict,
                              "Mask field should be a dictionary")
        label = u" "
        origin_label = u""
        attribute_label = u""
        data_type = 0
        attribute = u".attr_int"
        textlimit = -1
        if has_classdef:
            label = u"Integer"
            origin_label = label
            attribute_label = label
            data_type = 1
            attribute = u"cswebtest_op_activation.attr_int"
            textlimit = 20

        try:
            self.assertDictContainsSubset({
                u"attribute": attribute,
                u"data_type": data_type,
                u"display_hints": {},
                u"row": 0,
                u"fieldtype": u"text",
                u"column": 0,
                u"label": label,
                u"hidden": False,
                u"config": {},
                u"mandatory": False,
                u"origin_attribute": attribute,
                u"origin_label": origin_label,
                u"origin_mandatory": False,
                u"origin_readonly": 0,
                u"readonly": 0,
                u"textlimit": textlimit,
                u"span": 12,
                u"attribute_label": attribute_label}, form_field)
        except AssertionError:
            self.assertDictContainsSubset({
                u"attribute": attribute,
                u"data_type": data_type,
                u"display_hints": {},
                u"row": 0,
                u"fieldtype": u"text",
                u"column": 0,
                u"label": label,
                u"hidden": False,
                u"config": {u'monospaced_font': False},
                u"mandatory": False,
                u"origin_attribute": attribute,
                u"origin_label": origin_label,
                u"origin_mandatory": False,
                u"origin_readonly": 0,
                u"readonly": 0,
                u"textlimit": textlimit,
                u"span": 12,
                u"attribute_label": attribute_label}, form_field)

        # since 15.6 (E063518) tooltip ends with \n instead of space
        self.assertTrue(form_field["tooltip"].startswith(attribute))

        date_field = field_list[2]
        self.assertIsInstance(date_field, dict,
                              "Mask field should be a dictionary")
        self.assertEqual(date_field["fieldtype"], "calendar")

    def test_simple_form(self):
        """
        Request a form without any context.
        """
        c = Client(Root())
        response = c.get('/internal/uisupport/form/info/cswebtest_op_activation')
        self._check_result(response, False)

    def test_simple_form_with_classdef(self):
        """
        Request a form without any context.
        """
        c = Client(Root())
        response = c.get('/internal/uisupport/form/classdef/cswebtest_op_activation/cswebtest_op_activation')
        self._check_result(response, True)

    def _check_result_values(self, response, expected_label=None, expected_date=None):
        if expected_label is None:
            expected_label = self.obj.label
        if expected_date is None:
            expected_date = convert.dump_datetime(self.obj.attr_date)
        vals = response.json["values"]
        self.assertTrue(vals)
        self.assertTrue("cswebtest_op_activation.label" in vals)
        self.assertEqual(vals["cswebtest_op_activation.label"], expected_label)
        if expected_date:
            self.assertTrue("cswebtest_op_activation.attr_date" in vals)
            self.assertEqual(vals["cswebtest_op_activation.attr_date"], expected_date)

    def test_simple_form_with_classdef_and_some_non_key_values(self):
        """
        Request a form with a classdef context. We expect the result to
        contain the values where the rest name ``label`` is converted to
        ``cswebtest_op_activation.label``.
        """
        c = Client(Root())
        para = {"obj_values": {"label": self.obj.label}}
        response = c.post_json('/internal/uisupport/form/classdef/cswebtest_op_activation/cswebtest_op_activation',
                               para)
        # Check the form
        self._check_result(response, True)
        # Check the values - but not the date becaus we do not provide one
        self._check_result_values(response, None, "")

        # Call again and provide a date to ensure it stays in ISO-Format
        dt = datetime.datetime.now().replace(microsecond=0)
        mydate = convert.dump_datetime(dt)
        para["obj_values"]["attr_date"] = mydate
        response = c.post_json('/internal/uisupport/form/classdef/cswebtest_op_activation/cswebtest_op_activation',
                               para)
        # Check the form
        self._check_result(response, True)
        # Check the values - but not the date becaus we do not provide one
        self._check_result_values(response, None, mydate)

    def _get_rest_info(self, c):
        """
        Returns the response.json for the REST collection call of
        self.obj as suitable parameter for the form call.
        `c` is the test client.
        """
        # Retrieve the rest values
        rest_id = "/api/v1/collection/webtest_op_activation/%s" % (support.rest_key(self.obj))
        return {"obj_values": c.get(rest_id).json}

    def test_simple_form_with_classdef_and_obj_rest_values(self):
        """
        Request a form with a classdef context. We expect the result to
        contain a value dict with the dialog identifiers and the values
        provided by the objects rest call.
        """
        c = Client(Root())
        para = self._get_rest_info(c)
        response = c.post_json('/internal/uisupport/form/classdef/cswebtest_op_activation/cswebtest_op_activation',
                               para)
        # Check the form
        self._check_result(response, True)
        # Check the values
        self._check_result_values(response)

    def test_simple_form_with_classdef_no_refresh_and_obj_rest_values(self):
        """
        Request a form with a classdef context. We expect the result to
        contain a value dict with the dialog identifiers and the *outdated* values
        provided by the objects rest call.
        """
        c = Client(Root())
        para = self._get_rest_info(c)

        # Change a value
        expected = self.obj.label
        self.obj.label = "New"
        response = c.post_json('/internal/uisupport/form/classdef/cswebtest_op_activation/cswebtest_op_activation',
                               para)
        # Check the form
        self._check_result(response, True)
        # Check the values
        self._check_result_values(response, expected)

    def test_simple_form_with_classdef_refresh_and_obj_rest_values(self):
        """
        Request a form with a classdef context. We expect the result to
        contain a value dict with the dialog identifiers and actual values.
        """
        c = Client(Root())
        para = self._get_rest_info(c)

        # Change a value
        self.obj.label = "New"
        response = c.post_json('/internal/uisupport/form/classdef/cswebtest_op_activation/cswebtest_op_activation?refresh=1',
                               para)
        # Check the form
        self._check_result(response, True)
        # Check the values
        self._check_result_values(response)

    def test_form_basic_request(self):
        """
        Requests a simple form.
        """
        c = Client(Root())
        response = c.get('/internal/uisupport/form/operation/class/CDB_Create/cswebtest_op_activation')
        self._check_result(response, True)

    def test_form_values(self):
        """
        Requests a simple form.
        """
        c = Client(Root())
        nav_id = support.rest_key(self.obj)
        response = c.get('/internal/uisupport/form/operation/class/CDB_Modify/cswebtest_op_activation?object_navigation_id=%s' % nav_id)
        self.assertIn("values", response)
        values = response.json_body["values"]
        self.assertTrue(values)
        cdef = CDBClassDef("cswebtest_op_activation")
        register_list = response.json_body["registers"]
        # We need a value for every maskitem
        for field in register_list[0]["fields"]:
            attr_id = field["attribute"]
            self.assertIn(attr_id, values)
            # This is a modify operation so the data type of each attribute
            # is the same as in the cdb.objects.framework for all object attrs
            adef = cdef.getAttributeDefinition(attr_id)
            if adef:
                form_value = values[attr_id]
                if adef.is_text():
                    obj_value = self.obj.GetText(adef.getName())
                else:
                    obj_value = self.obj[adef.getName()]
                if field["data_type"] == sqlapi.SQL_DATE:
                    obj_value = six.text_type(obj_value.isoformat())
                elif field["data_type"] == sqlapi.SQL_INTEGER:
                    form_value = int(form_value)
                    obj_value = int(obj_value)
                self.assertEqual(form_value, obj_value,
                                 "The value of '%s' differs: %s != %s" % (attr_id,
                                                                          form_value,
                                                                          obj_value))
                # The type should be equal, too
                self.assertEqual(type(form_value), type(obj_value),
                                 "The type of '%s' differs: %s != %s" % (attr_id,
                                                                         type(form_value),
                                                                         type(obj_value)))

    def test_undefined_form_identifier(self):
        """
        Test if we get the status 404 (HttpNotFound) for an unknown
        form name.
        """
        c = Client(Root())
        with error_logging_disabled():
            c.get('/internal/uisupport/form/operation/class/CDB_ShowObject/unknownForm', status=404)

    def test_form_for_non_activated_op(self):
        """
        Check if the webui specific activation of the forms work.
        """
        c = Client(Root())
        nav_id = support.rest_key(self.obj)
        with error_logging_disabled():
            # There is no entry for CDB_Search in the Web UI configuration
            # but an entry for CDB_Search in the general op configuration
            c.get('/internal/uisupport/form/operation/class/CDB_Search/cswebtest_op_activation',
                  status=403)
            # The entry for CDB_ShowObject in the Web UI configuration
            # is deactivated. There is a general op configuration
            c.get('/internal/uisupport/form/operation/class/CDB_ShowObject/cswebtest_op_activation?object_navigation_id=%s' % nav_id,
                  status=403)
            # This op is neither in the operation configuration nor in
            # the WEB UI configuration activated for the user.
            c.get('/internal/uisupport/form/operation/class/CDB_CreateWithSearchConditions/cswebtest_op_activation?object_navigation_id=%s' % nav_id,
                  status=404)

    def test_subclass_op_on_parent(self):
        """
        Get form for operation that is only defined on child class
        """
        c = Client(Root())
        url = CLASS_FORM_URL_PATTERN % {
            "clazz": "rest_bar",
            "op_name": "fixture_op_on_subclass",
        }
        response = c.post_json(
            url,
            dict(object_navigation_id=[self.subclass_obj.cdb_object_id]),
            status=404
        ).json

    def test_subclass_op_on_child(self):
        """
        Get form for operation that is only defined on child class
        """
        c = Client(Root())
        url = CLASS_FORM_URL_PATTERN % {
            "clazz": "rest_bar_baz",
            "op_name": "fixture_op_on_subclass",
        }
        response = c.post_json(
            url,
            dict(object_navigation_id=[self.subclass_obj.cdb_object_id])
        ).json

        self.assertIn("operation_state", response)
        self.assertIn("classname", response["operation_state"])
        self.assertEqual(response["operation_state"]["classname"], "rest_bar_baz")



class TestFormsInRelship(RollbackTestCase):
    """
    Tests for the form REST API in relationship context.
    """
    maxDiff = None

    def setUp(self):
        try:
            from cs.restgenericfixture import RelshipParent, RelshipChild
        except ImportError:
            raise unittest.SkipTest("this test needs cs.restgenericfixture")

        super(TestFormsInRelship, self).setUp()
        self.c = Client(Root())
        self.parent = RelshipParent.Create(id=42, name="parent")
        self.child = RelshipChild.Create(child_id=4242, parent_id=self.parent.id, txt="child")

    def test_info_form(self):
        """
        Test that a form in a relationship context contains the relationship info,
        as well as the target object info
        """
        url = ("/internal/uisupport/form/operation/relship/rest_rel_parent/%d"
               "/DD_Children/CDB_ShowObject/rest_rel_child?object_navigation_id=%d") % (self.parent.id, self.child.child_id)
        response = self.c.get(url).json
        self.assertIn("operation_state", response)
        self.assertIn("objects", response["operation_state"])
        self.assertEqual(len(response["operation_state"]["objects"]), 1)
        self.assertTrue(response["operation_state"]["objects"][0].startswith("rest_rel_child:rest_rel_child\\at4242\\at@CDBRelship:rest_rel_parent2child"),
                        "Unexpected value for object in operation_state: %s" % response["operation_state"]["objects"][0])

    def test_create_form(self):
        """
        Test that a create form in a relationship context contains the needed values
        to create a dependent object.
        """
        url = ("/internal/uisupport/form/operation/relship/rest_rel_parent/%d"
               "/DD_Children/CDB_Create/rest_rel_child") % self.parent.id
        response = self.c.get(url).json
        self.assertIn("operation_state", response)
        self.assertNotIn("objects", response["operation_state"])
        raise unittest.SkipTest("Need interface to check operation values.")
        # self.assertEqual(response["operation_state"]["arg_list"], {"rest_rel_child.parent_id": "42"})


class TestFormsInRelshipSubclassing(RollbackTestCase):
    def setUp(self):
        try:
            from cs.restgenericfixture import RelshipParent, RelshipChild
        except ImportError:
            raise unittest.SkipTest("this test needs cs.restgenericfixture")

        super(TestFormsInRelshipSubclassing, self).setUp()
        self.c = Client(Root())

    def test_abc(self):
        """
        Try to create an object of an abstract base class, this should give 404.
        """
        url = RELSHIP_FORM_URL_PATTERN % {
            "referer_class": "cdb_class",
            "rest_keys": "cdb_person",
            "relship_name": "Attribute",
            "op_name": "CDB_Create",
            "target_class": "cdbdd_field",
        }
        self.c.get(url, status=404)

    def test_child_of_abc(self):
        """
        Create an object of a subclass of an abstract base class,
        this should yield the correct operation_state.
        """
        url = RELSHIP_FORM_URL_PATTERN % {
            "referer_class": "cdb_class",
            "rest_keys": "cdb_person",
            "relship_name": "Attribute",
            "op_name": "CDB_Create",
            "target_class": "cdbdd_char_field",
        }
        response = self.c.get(url, status=200).json
        self.assertIn("operation_state", response)
        self.assertIn("classname", response["operation_state"])
        self.assertEqual(response["operation_state"]["classname"], "cdbdd_char_field")

    def test_subclass_op_on_parent(self):
        """
        Get form for operation that is only defined on child class on parent class.
        This should raise a 404.
        """
        self.referer_obj = RestReferer.Create()
        self.subclass_obj = RestReferenceChild.Create(
            referer_id=self.referer_obj.cdb_object_id,
        )

        url = RELSHIP_FORM_URL_PATTERN % {
            "referer_class": "rest_referer",
            "rest_keys": self.referer_obj.cdb_object_id,
            "relship_name": "RestReferer2RestReference",
            "op_name": "fixture_op_on_subclass",
            "target_class": "rest_reference_base",
        }
        response = self.c.post_json(
            url,
            dict(object_navigation_id=[self.subclass_obj.cdb_object_id]),
            status=404,
        ).json

    def test_subclass_op_on_child(self):
        """
        Get form for operation that is only defined on child class on child class.
        This should correctly get the form for the operation.
        """
        self.referer_obj = RestReferer.Create()
        self.subclass_obj = RestReferenceChild.Create(
            referer_id=self.referer_obj.cdb_object_id,
        )

        url = RELSHIP_FORM_URL_PATTERN % {
            "referer_class": "rest_referer",
            "rest_keys": self.referer_obj.cdb_object_id,
            "relship_name": "RestReferer2RestReference",
            "op_name": "fixture_op_on_subclass",
            "target_class": "rest_reference_child",
        }
        response = self.c.post_json(
            url,
            dict(object_navigation_id=[self.subclass_obj.cdb_object_id])
        ).json

        self.assertIn("operation_state", response)
        self.assertIn("classname", response["operation_state"])
        self.assertEqual(response["operation_state"]["classname"], "rest_reference_child")


class TestFormsInNMRelship(RollbackTestCase):
    maxDiff = None

    def setUp(self):
        try:
            from cs.restgenericfixture import Fixture_nm_parent, Fixture_nm_target, Fixture_nm_link
        except ImportError:
            raise unittest.SkipTest("this test needs cs.restgenericfixture")

        super(TestFormsInNMRelship, self).setUp()
        self.c = Client(Root())
        self.parent = Fixture_nm_parent.Create(parent_label="parent")
        self.child1 = Fixture_nm_target.Create(label="child1")
        self.link1 = Fixture_nm_link.Create(parent_cdb_object_id=self.parent.cdb_object_id,
                                            child_cdb_object_id=self.child1.cdb_object_id,
                                            link_attr_c="link1")
        self.child2 = Fixture_nm_target.Create(label="child2")
        self.link2 = Fixture_nm_link.Create(parent_cdb_object_id=self.parent.cdb_object_id,
                                            child_cdb_object_id=self.child2.cdb_object_id,
                                            link_attr_c="link2")

    def test_delete_single_link(self):
        url = ("/internal/uisupport/form/operation/relship/fixture_nm_parent/%s"
               "/Children/CDB_Delete$RelshipFromReference/fixture_nm_target"
               "?object_navigation_id=%s") % (self.parent.cdb_object_id,
                                              self.child1.cdb_object_id)
        response = self.c.get(url).json
        self.assertIn("operation_state", response)
        self.assertDictContainsSubset({"classname": "fixture_nm_link_class",
                                       "opname": "CDB_Delete",
                                       "objects": ["fixture_nm_link_class:fixture_nm_link_class\\at%s\\at%s\\at@@"
                                                   % (self.parent.cdb_object_id, self.child1.cdb_object_id)]},
                                      response["operation_state"])

    def test_delete_multi_links(self):
        url = ("/internal/uisupport/form/operation/relship/fixture_nm_parent/%s"
               "/Children/CDB_Delete$RelshipFromReference/fixture_nm_target"
               "?object_navigation_id=%s&object_navigation_id=%s") % (
                   self.parent.cdb_object_id,
                   self.child1.cdb_object_id,
                   self.child2.cdb_object_id)
        response = self.c.get(url).json
        self.assertIn("operation_state", response)
        self.assertDictContainsSubset({"classname": "fixture_nm_link_class",
                                       "opname": "CDB_Delete",
                                       "objects": ["fixture_nm_link_class:fixture_nm_link_class\\at%s\\at%s\\at@@"
                                                   % (self.parent.cdb_object_id, self.child1.cdb_object_id),
                                                   "fixture_nm_link_class:fixture_nm_link_class\\at%s\\at%s\\at@@"
                                                   % (self.parent.cdb_object_id, self.child2.cdb_object_id)]},
                                      response["operation_state"])


class TestFormWithDisplayContext(RollbackTestCase):
    """
    Tests for the form REST API in a display context
    """
    maxDiff = None

    def setUp(self):
        try:
            from cs.restgenericfixture import Complex
        except ImportError:
            raise unittest.SkipTest("this test needs cs.restgenericfixture")

        super(TestFormWithDisplayContext, self).setUp()
        self.c = Client(Root())
        self.obj = Complex.Create(attr_int=99,
                                  attr_c10="abc",
                                  attr_cre="allowed",
                                  attr_datetime=datetime.datetime(1968, 12, 16),
                                  url="http://www.contact-software.com")

    def _get_rest_info(self):
        """
        Returns the response.json for the REST collection call of
        self.obj as suitable parameter for the form call.
        `c` is the test client.
        """
        # Retrieve the rest values
        rest_id = "/api/v1/collection/restcomplex/%s" % (support.rest_key(self.obj))
        return {"obj_values": self.c.get(rest_id).json}

    def test_object_header_with_attributes_missing_in_obj_values(self):
        """
        Retrieve the object header form.
        """
        c = Client(Root())
        para = {"obj_values": {"attr_int": self.obj.attr_int}}
        response = c.post_json('/internal/uisupport/display_context/object_header/rest_complex',
                               para)

        result = response.json
        self.assertTrue(result)

        # We expect one register that contains the mask we have configured
        self.assertEqual(len(result["registers"]), 1)
        self.assertEqual(result["registers"][0]["mask_name"],
                         "rest_complex_object_header")

        # We expect other form vals to be set
        self.assertEqual(result["values"]["rest_complex.attr_int"],
                         self.obj.attr_int)
        self.assertEqual(result["values"]["rest_complex.url"],
                         self.obj.url)
        # not configured in form
        self.assertNotIn("rest_complex.attr_c10", result["values"])

    def test_object_header_with_pre_display_hook(self):
        """
        Retrieve the object header form. Check the value set by the
        ``::PRE_DISPLAY::`` hook.
        """
        para = self._get_rest_info()
        response = self.c.post_json('/internal/uisupport/display_context/object_header/rest_complex',
                                    para)
        result = response.json
        self.assertTrue(result)

        # The ::PRE_DISPLAY::-Hook should not be part of the answer
        self.assertFalse(result["dialog_hooks"])

        # We expect one register that contains the mask we have configured
        self.assertEqual(len(result["registers"]), 1)
        self.assertEqual(result["registers"][0]["mask_name"],
                         "rest_complex_object_header")

        # We expect the ::PRE_DISPLAY:: hook to set a (typed) calculated value
        self.assertEqual(result["values"][".attr_calculated"],
                         self.obj.attr_int + 1)
        self.assertEqual(result["values"][".attr_calculated_date"],
                         "1968-12-17T00:00:00")
        # We expect other form vals to be set
        self.assertEqual(result["values"]["rest_complex.url"],
                         self.obj.url)


class TestFormsInNMRelshipSubclassing(RollbackTestCase):
    def setUp(self):
        try:
            from cs.restgenericfixture import Complex
        except ImportError:
            raise unittest.SkipTest("this test needs cs.restgenericfixture")

        super(TestFormsInNMRelshipSubclassing, self).setUp()
        self.c = Client(Root())
        self.referer = RestRefererNM.Create()
        self.reference = RestReferenceChild.Create()
        self.link = RestRefererNMLink.Create(
            referer_id=self.referer.cdb_object_id,
            reference_id=self.reference.cdb_object_id,
        )

    def test_remove_link(self):
        """
        Delete a link between referer and subclass of reference in a relationship.
        """
        url = RELSHIP_FORM_URL_PATTERN % {
            "referer_class": "rest_referer_nm",
            "rest_keys": self.referer.cdb_object_id,
            "relship_name": "RestReferer2RestReference",
            "op_name": "CDB_Delete$RelshipFromReference",
            "target_class": "rest_reference_child",
        }
        response = self.c.post_json(
            url,
            dict(object_navigation_id=[self.reference.cdb_object_id])
        ).json
        self.assertIn("operation_state", response)
        self.assertIn("classname", response["operation_state"])
        self.assertEqual(response["operation_state"]["classname"], "rest_referer_nm_link")

    def test_remove_reference(self):
        """
        Delete an object that is a subclass of reference in a relationship.
        """
        url = RELSHIP_FORM_URL_PATTERN % {
            "referer_class": "rest_referer_nm",
            "rest_keys": self.referer.cdb_object_id,
            "relship_name": "RestReferer2RestReference",
            "op_name": "CDB_Delete",
            "target_class": "rest_reference_child",
        }
        response = self.c.post_json(
            url,
            dict(object_navigation_id=[self.reference.cdb_object_id])
        ).json
        self.assertIn("operation_state", response)
        self.assertIn("classname", response["operation_state"])
        self.assertEqual(response["operation_state"]["classname"], "rest_reference_child")


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
