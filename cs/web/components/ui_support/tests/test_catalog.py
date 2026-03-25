#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import
import unittest
from cdb import sqlapi, sig
from cdb.platform.mom import getObjectHandleFromObjectID, CDBObjectHandle, SimpleArguments
from cdb.testcase import RollbackTestCase, without_error_logging
from cdbwrapc import RestCatalog
from webtest import TestApp as Client
import six
from cs.platform.web.root import Root

try:
    from cs.restgenericfixture.catalog_test import PythonDataCatalogData
    from cs.restgenericfixture import Csfixture_catalog_values
except:
    raise unittest.SkipTest("Requires cs.restgenericfixture")


class TestRestCatalogBase(RollbackTestCase):
    """
    Base class that provides the catalog values.
    """
    @classmethod
    def setUpClass(cls):
        super(TestRestCatalogBase, cls).setUpClass()
        sqlapi.SQLdelete("FROM fixture_catalog_values")
        rec = sqlapi.Record('fixture_catalog_values')
        for i in six.moves.range(11):
            for key, value in list(six.iteritems(cls.get_fixture_data(i))):
                rec[key] = value
            rec.insert()
        cls.all_data = sqlapi.RecordSet2("fixture_catalog_values")

    @classmethod
    def tearDownClass(cls):
        super(TestRestCatalogBase, cls).tearDownClass()
        sqlapi.SQLdelete("FROM fixture_catalog_values")

    @staticmethod
    def get_fixture_data(nr):
        """
        Returns a dictionary of values that can
        be used to construct an fixture_catalog_value
        object.
        """
        return {"nr": nr,
                "catalog_value_string": u"Value%d" % nr,
                "i18n_label_de": u"Value_de%d" % nr,
                "i18n_label_en": u"Value_en%d" % nr,
                "addtl_query_attr1": nr % 3}


class TestRestCatalogAPI(TestRestCatalogBase):
    """
    Tests for the REST API of catalogs.
    """

    def test_query_form_fires_pre_mask(self):
        class NonLocal(object):
            user_exit_called = False
            uses_webui = False

        @sig.connect(Csfixture_catalog_values, 'query_catalog', 'pre_mask')
        def query_catalog_ue(obj, ctx):
            NonLocal.user_exit_called = True
            NonLocal.uses_webui = ctx.uses_webui

        try:
            c = Client(Root())
            para = {"catalog_field": "input_field",
                    "form_data": {"nr_out": "=1 or =3 or =5",
                                  "input_field": ""}}
            response = c.post_json(
                '/internal/uisupport/catalog/restcatalog_test/query_form', para)

            self.assertTrue(NonLocal.user_exit_called)
            self.assertTrue(NonLocal.uses_webui)

        finally:
            sig.disconnect(query_catalog_ue)

    def test_query_form_fires_pre(self):
        class NonLocal(object):
            user_exit_called = False
            uses_webui = False

        @sig.connect(Csfixture_catalog_values, 'query_catalog', 'pre')
        def query_catalog_ue(obj, ctx):
            NonLocal.user_exit_called = True
            NonLocal.uses_webui = ctx.uses_webui

        try:
            c = Client(Root())
            para = {"catalog_field": "input_field"}
            response = c.post_json(
                '/internal/uisupport/catalog/restcatalog_test/tabular_with_values', para)

            self.assertTrue(NonLocal.user_exit_called)
            self.assertTrue(NonLocal.uses_webui)

        finally:
            sig.disconnect(query_catalog_ue)

    def test_query_form_fires_final(self):
        class NonLocal(object):
            user_exit_called = False
            uses_webui = False

        @sig.connect(Csfixture_catalog_values, 'query_catalog', 'final')
        def query_catalog_ue(obj, ctx):
            NonLocal.user_exit_called = True
            NonLocal.uses_webui = ctx.uses_webui

        try:
            c = Client(Root())
            para = {"catalog_field": "input_field"}
            response = c.post_json(
                '/internal/uisupport/catalog/restcatalog_test/tabular_with_values', para)

            self.assertTrue(NonLocal.user_exit_called)
            self.assertTrue(NonLocal.uses_webui)

        finally:
            sig.disconnect(query_catalog_ue)

    def test_basic_onecolumn_browse(self):
        """
        Just call the catalog without any formular parameters.
        We expect that all catalog values are returned.
        """
        c = Client(Root())
        para = {"catalog_field": "input_field"}
        response = c.post_json('/internal/uisupport/catalog/restcatalog_test/items?as_strings',
                               para)
        self.assertIn("items", response)
        result_list = response.json_body["items"]
        for rec in self.all_data:
            self.assertIn(rec.catalog_value_string, result_list)

    def test_basic_onecolumn_select(self):
        """
        We select the first record and expect that input_field is filled
        with the value.
        """
        c = Client(Root())
        para = {"catalog_field": "input_field",
                "selected_string": self.all_data[0].catalog_value_string,
                "input_field": ""
                }
        response = c.post_json('/internal/uisupport/catalog/restcatalog_test/selected_values',
                               para)
        self.assertIn("selected_values", response)
        result = response.json_body["selected_values"]
        self.assertIn("input_field", result)
        self.assertEqual(result["input_field"], self.all_data[0].catalog_value_string)

    def test_onecolumn_browse_with_search_cond(self):
        """
        Check if a search condition from the dialog is evaluated by the catalog.
        """
        c = Client(Root())
        para = {"catalog_field": "input_field",
                "form_data": {"nr_out": "=1 or =3 or =5",
                              "input_field": ""}}
        response = c.post_json('/internal/uisupport/catalog/restcatalog_test/items?as_strings',
                               para)
        self.assertIn("items", response)
        result_list = response.json_body["items"]
        # Wegen E034035: Comboboxen sollten ggf.grundsätzlich einen "leeren"
        # Eintrag zur Auswahl anbieten. Gibt es hier auch einen zusätzlichen
        # Empty Value
        self.assertEqual(['Value1', 'Value3', 'Value5', ''], result_list)

    def test_basic_onecolumn_items_with_values(self):
        """
        Retrieve items and values with one REST-Call
        """
        c = Client(Root())
        para = {"catalog_field": "input_field",
                "form_data": {"input_field": ""}
                }
        response = c.post_json('/internal/uisupport/catalog/restcatalog_test/items_with_values',
                               para)
        self.assertIn("items_with_values", response)
        result = response.json_body["items_with_values"]
        # Each row has to be part of the result
        for rec in self.all_data:
            self.assertIn(rec.catalog_value_string, [data[0] for data in result])
        # Each item of the list is the result that has to be set for input_field
        for data in result:
            self.assertIn("input_field", data[1])
            self.assertEqual(data[1]["input_field"], data[0])

    def test_basic_object_browse(self):
        """
        Just call the catalog without any formular parameters.
        We expect that all catalog values are returned as objects
        because we set kArgumetnsCatalogWantObjects.
        """
        c = Client(Root())
        para = {"catalog_field": "input_field"}
        response = c.post_json('/internal/uisupport/catalog/restcatalog_test/items?as_objects=',
                               para)
        self.assertIn("items", response)
        result_list = response.json_body["items"]
        obj_uuids = [CDBObjectHandle(o["oid"]).getUUID() for o in result_list]
        for rec in self.all_data:
            self.assertIn(rec.cdb_object_id, obj_uuids)

    def test_basic_object_select(self):
        """
        We select the first record and expect that input_field is filled
        with the value.
        """
        c = Client(Root())
        oh = getObjectHandleFromObjectID(self.all_data[0].cdb_object_id)
        para = {"catalog_field": "input_field",
                "selected_objects": [oh.get_object_id()],
                "form_data": {"input_field": ""}
                }
        response = c.post_json('/internal/uisupport/catalog/restcatalog_test/selected_values',
                               para)
        self.assertIn("selected_values", response)
        result = response.json_body["selected_values"]
        self.assertIn("input_field", result)
        self.assertEqual(result["input_field"], self.all_data[0].catalog_value_string)

    def test_basic_table_browse(self):
        """
        Just call the catalog without any formular parameters.
        We expect that all catalog values are returned as a table.
        """
        c = Client(Root())
        para = {"catalog_field": "input_field"}
        response = c.post_json('/internal/uisupport/catalog/restcatalog_test/tabular_with_values',
                               para)
        for key in ["rows", "icon_url", "label", "multiselect", "help_url", "tabledef"]:
            self.assertIn(key, response)
        result_list = response.json_body["rows"]
        self.assertEqual(len(result_list), len(self.all_data))

    def test_basic_table_browse_select_as_object(self):
        """
        Select the object in the first row and retrieve the result as object
        """
        c = Client(Root())
        para = {"catalog_field": "input_field"}
        response = c.post_json('/internal/uisupport/catalog/restcatalog_test/tabular_with_values',
                               para)
        row_index = 0
        for col in response.json_body["tabledef"]["columns"]:
            if col["attribute"] == "catalog_value_string":
                break
            else:
                row_index += 1

        result_list = response.json_body["rows"]
        para["selected_ids"] = [selrow["id"] for selrow in result_list]
        expected = [selrow["columns"][row_index] for selrow in result_list]
        para["form_data"] = {"input_field": ""}
        response = c.post_json('/internal/uisupport/catalog/restcatalog_test/selected_values?as_objects=1',
                               para)
        self.assertIn("selected_objects", response)
        result = response.json_body["selected_objects"]
        for obj, expected_val in zip(result, expected):
            self.assertEqual(obj["catalog_value_string"], expected_val)

    def test_type_ahead(self):
        """
        Call type ahead
        """
        c = Client(Root())
        para = {"catalog_field": "input_field",
                "user_input": "Value1",
                "form_data": {"input_field": ""}
                }
        response = c.post_json('/internal/uisupport/catalog/restcatalog_test/typeAhead',
                               para)
        self.assertIn("proposals", response)
        result = response.json_body["proposals"]
        # We expect 2 proposals - value1 and value10
        self.assertEqual(len(result), 2)
        self.assertIn("value", result[0])

    def test_value_check_ok(self):
        """
        Call type ahead
        """
        c = Client(Root())
        my_value = self.all_data[0].catalog_value_string
        para = {"catalog_field": "input_field",
                "form_data": {"input_field": my_value}
                }
        response = c.post_json('/internal/uisupport/catalog/restcatalog_test/valueCheck',
                               para)
        self.assertIn("result", response)
        result = response.json_body["result"]
        self.assertEqual(result, 1)
        self.assertIn("new_values", response)
        new_values = response.json_body["new_values"]
        self.assertEqual(new_values["input_field"], my_value)

    def test_value_check_fails(self):
        """
        Call type ahead
        """
        c = Client(Root())
        para = {"catalog_field": "input_field",
                "form_data": {"input_field": "This value does not exist"}
                }
        response = c.post_json('/internal/uisupport/catalog/restcatalog_test/valueCheck',
                               para)
        self.assertIn("result", response)
        result = response.json_body["result"]
        self.assertEqual(result, 0)
        self.assertIn("message", response)

    @without_error_logging
    def test_undefined_catalog(self):
        """
        Test if we get the status 403 (HttpForbidden) for an unknown
        catalog.
        """
        c = Client(Root())
        c.post_json('/internal/uisupport/catalog/unknown_catalog_name/items', {}, status=403)


class TestTableCatalog(RollbackTestCase):
    """
    Test REST-API of table catalogs
    """
    def setUp(self):
        try:
            from cs.restgenericfixture import Csfixture_catalog_values
        except ImportError:
            raise unittest.SkipTest("this test needs cs.restgenericfixture")
        super(TestTableCatalog, self).setUp()
        # Move away other toplevel nodes to avoid test failures because of
        # data added by other tests
        sqlapi.SQLupdate("fixture_catalog_values set parent_cdb_object_id = '-' WHERE parent_cdb_object_id is NULL or parent_cdb_object_id = ''")
        # Create a structure for the catalog
        self.nr_of_nodes = 2
        Csfixture_catalog_values.create_catalog_value_struct(3,
                                                             self.nr_of_nodes)

    def _getCatalogConfig(self, c, attr):
        """
        Returns a tuple containing catalog configuration for the given `attr`
        and the para you need if you post to a catalog url.
        """
        response = c.get('/internal/uisupport/form/classdef/csfixture_catalog_tests/csfixture_catalog_tests')
        fields = response.json_body["registers"][0]["fields"]
        self.assertTrue(fields)
        mask_vals = {f["attribute"]: "" for f in fields}
        catalog_config = None
        for f in fields:
            if f["attribute"] == attr:
                catalog_config = f["config"]
                break
        para = {"catalog_field": attr,
                "form_data": mask_vals}
        return (catalog_config, para)

    def test_table_catalog(self):
        """
        Test retrieving a table catalog from a form
        and selecting an entry
        """
        c = Client(Root())
        catalog_config, para = self._getCatalogConfig(c, ".test_field4")
        self.assertTrue(catalog_config)
        self.assertTrue("catalogTableURL" in catalog_config)
        url = catalog_config["catalogTableURL"]
        self.assertTrue(url)

        response = c.post_json(url, para)
        self.assertTrue("rows" in response.json_body)

        # The catalog shows entries without parent ==> nr_of_nodes
        rows = response.json_body["rows"]
        self.assertEqual(len(rows), self.nr_of_nodes)

        # We know the catalog fills catalog_value_string, so find the
        # position in the table
        pos = 0
        cols = response.json_body["tabledef"]["columns"]
        for col in cols:
            if col["attribute"] == "catalog_value_string":
                break
            pos += 1
        # Now emulate a selection
        select_url = catalog_config["selectURL"]
        self.assertTrue(select_url)
        for row in rows:
            sel_para = para.copy()
            sel_para["selected_ids"] = [row["id"]]
            resp_sel = c.post_json(select_url, sel_para)
            self.assertTrue("selected_values" in resp_sel)
            selection = resp_sel.json_body["selected_values"]
            expected_value = {".test_field4": row["columns"][pos]}
            self.assertEqual(selection, expected_value)

    def test_table_catalog_form(self):
        """
        Test retrieving the search form of a table catalog
        """
        c = Client(Root())
        catalog_config, para = self._getCatalogConfig(c, ".test_field4")
        self.assertTrue("queryFormURL" in catalog_config)
        url = catalog_config["queryFormURL"]
        self.assertTrue(url)

        response = c.post_json(url, para)
        self.assertTrue("registers" in response.json_body)
        self.assertTrue("values" in response.json_body)
        self.assertTrue("activate_search_form" in response.json_body)
        self.assertFalse(response.json_body["activate_search_form"])
        maskitems = response.json_body["registers"][0]["fields"]
        attrs = [m["attribute"] for m in maskitems]
        expected = [("fixture_catalog_values.catalog_value_string", ''),
                    ("fixture_catalog_values.nr", ''),
                    ("fixture_catalog_values.addtl_query_attr1", ''),
                    ("fixture_catalog_values.parent_cdb_object_id", '=""')]
        dlgvals = response.json_body["values"]
        for attr, value in expected:
            self.assertTrue(attr in attrs,
                            "Missing attr %s in dialog" % attr)
            self.assertTrue(attr in dlgvals,
                            "Missing attr %s in values" % attr)
            self.assertEqual(value, dlgvals[attr])

    def test_table_catalog_query(self):
        """
        Test retrieving the search form of a table catalog and provide
        extra query args.
        """
        c = Client(Root())
        try:
            from cs.restgenericfixture import Csfixture_catalog_values
        except ImportError:
            raise unittest.SkipTest("this test needs cs.restgenericfixture")

        catalog_config, para = self._getCatalogConfig(c, ".test_field4")
        url = catalog_config["queryFormURL"]
        response = c.post_json(url, para)

        self.assertTrue("json_field_types" in response.json_body)
        ft = response.json_body["json_field_types"]
        Csfixture_catalog_values.Create(nr=5793,
                                        parent_cdb_object_id="",
                                        catalog_value_string="Find me")
        url = catalog_config["catalogTableURL"]
        para["query_data"] = {"json_field_types": ft,
                              "values": {"fixture_catalog_values.catalog_value_string": "Find%"}}
        response = c.post_json(url, para)
        self.assertTrue("rows" in response.json_body)

        # The catalog shows entries without parent ==> nr_of_nodes
        rows = response.json_body["rows"]
        self.assertEqual(len(rows), 1)

    def test_proposal_catalog(self):
        """
        Basic test for table catalog configured for test_field4
        """
        # Clear old proposals
        sqlapi.SQLdelete("FROM fixture_catalog_values_proposa")
        c = Client(Root())
        catalog_config, para = self._getCatalogConfig(c, ".test_field4")
        self.assertTrue(catalog_config)
        self.assertTrue("proposalCatalogURL" in catalog_config)
        self.assertTrue("proposalLabel" in catalog_config)
        self.assertTrue(catalog_config["proposalLabel"])
        proposal_url = catalog_config["proposalCatalogURL"]
        self.assertTrue(proposal_url)
        presponse = c.post_json(proposal_url, para)
        self.assertTrue("rows" in presponse.json_body)
        prows = presponse.json_body["rows"]
        # No proposal yet
        self.assertEqual(len(prows), 0)

        # select an entry
        url = catalog_config["catalogTableURL"]
        response = c.post_json(url, para)
        rows = response.json_body["rows"]
        select_url = catalog_config["selectURL"]
        sel_para = para.copy()
        sel_para["selected_ids"] = [rows[1]["id"]]
        resp_sel = c.post_json(select_url, sel_para)
        tabdef_selection = resp_sel.json_body["selected_values"]

        # Now there should be a proposal - the last selction
        presponse = c.post_json(proposal_url, para)
        prows = presponse.json_body["rows"]
        # No proposal yet
        self.assertEqual(len(prows), 1)
        sel_para = para.copy()
        sel_para["selected_ids"] = [prows[0]["id"]]
        resp_sel = c.post_json(select_url, sel_para)
        proposal_selection = resp_sel.json_body["selected_values"]
        self.assertEqual(proposal_selection, tabdef_selection)


class TestStructureCatalog(RollbackTestCase):
    """
    Test REST-API of structure catalogs
    """
    def setUp(self):
        try:
            from cs.restgenericfixture import Csfixture_catalog_values
        except ImportError:
            raise unittest.SkipTest("this test needs cs.restgenericfixture")
        super(TestStructureCatalog, self).setUp()
        # Move away other toplevel nodes to avoid test failures because of
        # data added by other tests
        sqlapi.SQLupdate("fixture_catalog_values set parent_cdb_object_id = '-' WHERE parent_cdb_object_id is NULL or parent_cdb_object_id = ''")
        # Create a structure for the catalog
        self.nr_of_nodes = 2
        Csfixture_catalog_values.create_catalog_value_struct(3,
                                                             self.nr_of_nodes)

    def _common_struct_test(self, c):
        response = c.get('/internal/uisupport/form/classdef/csfixture_catalog_tests/csfixture_catalog_tests')
        fields = response.json_body["registers"][0]["fields"]
        self.assertTrue(fields)
        mask_vals = {f["attribute"]: "" for f in fields}
        struct_config = None
        for f in fields:
            if f["attribute"] == ".test_field3":
                struct_config = f["config"]
                break
        self.assertTrue(struct_config)
        self.assertTrue("structureRootURL" in struct_config)
        root_url = struct_config["structureRootURL"]
        self.assertTrue(root_url)
        para = {"catalog_field": ".test_field3",
                "form_data": mask_vals}
        response = c.post_json(root_url, para)
        # We expect one root node representing the structure
        self.assertEqual(len(response.json_body), 1)

        # We have generated a structure with nr_of_nodes
        # objects per level and 3 levels. Navigate to the
        # bottom
        expected_result_attrs = [".test_field", ".test_field2", ".test_field3"]
        expected_result = {}
        for hier_level in six.moves.range(0, 3):
            expand_url = response.json_body[0]["expand_url"]
            self.assertTrue(expand_url)
            response = c.post_json(expand_url, {})
            self.assertEqual(len(response.json_body),
                             self.nr_of_nodes)
            expected_result[expected_result_attrs[hier_level]] = response.json_body[0]["label"]
        # Now call select
        select_url = response.json_body[0]["selectURL"]
        self.assertTrue(select_url)
        return (select_url, expected_result)

    def test_struct_catalog(self):
        """
        Test retrieving a structure catalog from a form, expanding the nodes
        and selecting an entry
        """
        c = Client(Root())
        select_url, expected_result = self._common_struct_test(c)
        response = c.post_json(select_url, {})
        self.assertTrue("selected_values" in response)
        selection = response.json_body["selected_values"]
        self.assertEqual(len(selection), 3)
        self.assertEqual(selection, expected_result)

    def test_struct_catalog_obj_result(self):
        """
        Test retrieving a structure catalog from a form, expanding the nodes,
        selecting an entry and retrieving the result as object
        """
        c = Client(Root())
        select_url, expected = self._common_struct_test(c)
        # Basic test for object selection
        select_url += "&as_objects=1"
        response = c.post_json(select_url, {})
        self.assertTrue("selected_objects" in response, select_url)
        objs = response.json_body["selected_objects"]
        self.assertEqual(len(objs), 1)
        self.assertEqual(expected[".test_field3"], objs[0]["catalog_value_string"])


class TestPythonDataCatalog(RollbackTestCase):
    """
    Test for a catalog that fills the table using
    powerscript.
    """
    def test_table_browse(self):
        """
        Just call the catalog without any formular parameters.
        We expect that all catalog values are returned in a TabularData.
        """
        # Retrieve the table definition
        c = RestCatalog("FixtureTestPythonDataCatalog", "result_attr",
                        SimpleArguments(result_attr=""))
        t = c.do_table_browse([])
        tdef = t.getTabDefinition()

        # Now start the test
        PythonDataCatalogData.reset()
        expected_data = PythonDataCatalogData()
        # Reset the offset to have equal data
        PythonDataCatalogData.reset()
        c = Client(Root())
        para = {"catalog_field": "result_attr"}
        response = c.post_json('/internal/uisupport/catalog/FixtureTestPythonDataCatalog/tabular_with_values',
                               para)
        for key in ["rows", "icon_url", "label", "multiselect", "help_url", "tabledef"]:
            self.assertIn(key, response)
        result_list = response.json_body["rows"]
        self.assertEqual(len(result_list), expected_data.getNumberOfRows())
        for row in six.moves.range(0, expected_data.getNumberOfRows()):
            self.assertEqual(result_list[row]["columns"],
                             expected_data.getRowDataFromTabdef(row, tdef, show_hidden=False))

    def test_selection_id_select(self):
        """
        We select a row. We check if the value returned is the value
        displayed in the row (E042590)
        """
        c = Client(Root())
        para = {"catalog_field": "result_attr",
                "form_data": {"result_attr": ""}}
        response = c.post_json('/internal/uisupport/catalog/FixtureTestPythonDataCatalog/tabular_with_values',
                               para)
        result_list = response.json_body["rows"]
        catalog_id = response.json_body["catalog_id"]
        # Retrieve the selection_id of the second object
        selrow = 1
        para = {"catalog_field": "result_attr",
                "selected_ids": [result_list[selrow]["id"]],
                "form_data": {"result_attr": ""},
                "catalog_id": catalog_id
                }
        # The value resides in the first column
        expected_val = result_list[selrow]["columns"][0]
        response = c.post_json('/internal/uisupport/catalog/FixtureTestPythonDataCatalog/selected_values',
                               para)
        self.assertIn("selected_values", response)
        result = response.json_body["selected_values"]
        self.assertIn("result_attr", result)
        # The selected value is the
        self.assertEqual(result["result_attr"], expected_val)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
