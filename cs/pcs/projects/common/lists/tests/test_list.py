#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access,no-value-for-parameter

import unittest

from cdb import testcase
from cdb.platform import mom
from cdbwrapc import CDBClassDef
from mock import MagicMock, Mock, patch

from cs.pcs.projects.common import lists
from cs.pcs.projects.common.lists.list import (
    ListConfig,
    ListDataProvider,
    ListItemConfig,
    ListItemConfigEntry,
)


class TestListConfig(testcase.RollbackTestCase):
    def test_combineDisplayConfigsAndListOfItems_empty(self):
        list_config = MagicMock(
            spec=ListConfig,
            ListDataProviderReference=[],
        )
        self.assertEqual(
            ListConfig.combineDisplayConfigsAndListOfItems(
                list_config, "request", "restKey"
            ),
            ({}, [], None, ""),
        )

    def test_combineDisplayConfigsAndListOfItems_heterogenous(self):
        provider_a = MagicMock()
        provider_a.generateDisplayConfigAndListItems.return_value = [
            "a",
            "b",
            "c",
            None,
            None,
        ]
        provider_b = MagicMock()
        provider_b.generateDisplayConfigAndListItems.return_value = [
            "A",
            "B",
            "C",
            None,
            None,
        ]
        list_config = MagicMock(
            spec=ListConfig,
            HETEROGENOUS="HET",
            ListDataProviderReference=[
                Mock(ListDataProvider=provider_a),
                Mock(ListDataProvider=provider_b),
            ],
        )
        self.assertEqual(
            ListConfig.combineDisplayConfigsAndListOfItems(
                list_config, "request", "restKey"
            ),
            ({"a": "b", "A": "B"}, ["c", "C"], "HET", ""),
        )
        provider_a.generateDisplayConfigAndListItems.assert_called_once_with(
            "request", "restKey"
        )
        provider_b.generateDisplayConfigAndListItems.assert_called_once_with(
            "request", "restKey"
        )

    def test_combineDisplayConfigsAndListOfItems_homogenous(self):
        provider_a = MagicMock(rolename="foo")
        provider_a.generateDisplayConfigAndListItems.return_value = [
            "a",
            "b",
            "c",
            None,
            None,
        ]
        provider_b = MagicMock(rolename="foo")
        provider_b.generateDisplayConfigAndListItems.return_value = [
            "A",
            "B",
            "C",
            None,
            None,
        ]
        list_config = MagicMock(
            spec=ListConfig,
            HETEROGENOUS="HET",
            ListDataProviderReference=[
                Mock(ListDataProvider=provider_a),
                Mock(ListDataProvider=provider_b),
            ],
        )
        self.assertEqual(
            ListConfig.combineDisplayConfigsAndListOfItems(
                list_config, "request", "restKey"
            ),
            ({"a": "b", "A": "B"}, ["c", "C"], "foo", ""),
        )
        provider_a.generateDisplayConfigAndListItems.assert_called_once_with(
            "request", "restKey"
        )
        provider_b.generateDisplayConfigAndListItems.assert_called_once_with(
            "request", "restKey"
        )

    @patch("cs.pcs.projects.common.lists.list.util")
    @patch("cs.pcs.projects.common.lists.list.logging")
    @patch("cs.pcs.projects.common.lists.list.sorted")
    def test_combineDisplayConfigsAndListOfItems_provider_error(
        self, _sorted, logging, util
    ):
        # mock request
        request = Mock()
        request.app.root = "https://www.example.org"

        # mock data provider Ref
        dataProviderRef = Mock()
        dataProvider = Mock()
        dataProvider.classname = "temp1"
        dataProvider.generateDisplayConfigAndListItems = Mock()
        dataProvider.generateDisplayConfigAndListItems.return_value = (
            "",
            {},
            [],
            True,
            "",
        )
        dataProviderRef.ListDataProvider = dataProvider

        # test error message for error during generating display config
        # and list of items
        with patch(
            "cs.pcs.projects.common.lists.list.ListConfig.ListDataProviderReference",
            new=[dataProviderRef],
        ):
            listConfig = ListConfig()
            listConfig.combineDisplayConfigsAndListOfItems(request)
        util.get_label.assert_called_with(
            "cs.pcs.projects.common.lists.list.config_error_data_provider"
        )

    @patch("cs.pcs.projects.common.lists.list.util")
    @patch(
        "cs.pcs.projects.common.lists.list.ListConfig."
        "combineDisplayConfigsAndListOfItems",
        return_value=[{}, [], "", False],
    )
    def test_generateListJSON(self, combineDisplayConfigsAndListOfItems, util):
        # mock request
        request = Mock()
        request.app.root = "https://www.example.org"

        # mock label_id
        label_id = Mock()

        with patch(
            "cs.pcs.projects.common.lists.list.ListConfig.label_id", new=label_id
        ):
            listConfig = ListConfig()
            listConfig.generateListJSON(request)

        combineDisplayConfigsAndListOfItems.assert_called_with(request, None)
        util.get_label.assert_called_with(label_id)


class TestListDataProvider(testcase.RollbackTestCase):
    def test_get_sql_statement(self):
        expected_result = (
            "SELECT cdb_object_id, key1, key2 "
            "FROM foo_table "
            "WHERE foo_where AND key1='val1' AND key2='val2' "
            "foo_order_by"
        )
        source = MagicMock(spec=lists.list.DataSource)
        source.get_table.return_value = "foo_table"
        source.get_where.return_value = "foo_where"
        source.get_order_by.return_value = "foo_order_by"
        provider = MagicMock(
            spec=ListDataProvider,
            DataSource=source,
        )
        self.assertEqual(
            ListDataProvider.get_sql_statement(
                provider,
                ["key1", "key2"],
                ["val1", "val2"],
            ),
            expected_result,
        )

    def test__get_sql_stmt_no_rest_name(self):
        provider = lists.list.ListDataProvider()
        self.assertIsNone(provider._get_sql_stmt(None, "P1@B1"))

    def test__get_sql_stmt_no_rest_key(self):
        provider = lists.list.ListDataProvider()
        self.assertIsNone(provider._get_sql_stmt("any", None))

    def test__get_sql_stmt_unsupported(self):
        provider = lists.list.ListDataProvider()
        self.assertIsNone(provider._get_sql_stmt("unsupported", "P1@B1"))

    @patch.object(lists.list.ListDataProvider, "get_sql_statement")
    def test__get_sql_stmt_project_old(self, get_sql_statement):
        provider = lists.list.ListDataProvider()
        self.assertEqual(
            provider._get_sql_stmt("project", "P1@"),
            get_sql_statement.return_value,
        )
        get_sql_statement.assert_called_once_with(
            ["cdb_project_id"],
            ["P1"],
        )

    @patch.object(lists.list.ListDataProvider, "get_sql_statement")
    def test__get_sql_stmt_project(self, get_sql_statement):
        self.skipTest("replaces test above after primary key change")
        provider = lists.list.ListDataProvider()
        self.assertEqual(
            provider._get_sql_stmt("project", "P1@B1"),
            get_sql_statement.return_value,
        )
        get_sql_statement.assert_called_once_with(
            ("cdb_project_id", "ce_baseline_id"),
            ["P1", "B1"],
        )

    def test__get_sql_stmt_project_invalid(self):
        provider = lists.list.ListDataProvider()
        with self.assertRaises(ValueError):
            provider._get_sql_stmt("project", "A@B@C")

    @patch.object(lists.list.ListDataProvider, "get_sql_statement")
    def test__get_sql_stmt_task_old(self, get_sql_statement):
        provider = lists.list.ListDataProvider()
        self.assertEqual(
            provider._get_sql_stmt("project_task", "P1@T1@"),
            get_sql_statement.return_value,
        )
        get_sql_statement.assert_called_once_with(
            ["cdb_project_id", "task_id"],
            ["P1", "T1"],
        )

    @patch.object(lists.list.ListDataProvider, "get_sql_statement")
    def test__get_sql_stmt_task(self, get_sql_statement):
        self.skipTest("replaces test above after primary key change")
        provider = lists.list.ListDataProvider()
        self.assertEqual(
            provider._get_sql_stmt("project_task", "P1@T1@B1"),
            get_sql_statement.return_value,
        )
        get_sql_statement.assert_called_once_with(
            ("cdb_project_id", "task_id", "ce_baseline_id"),
            ["P1", "T1", "B1"],
        )

    def test__get_sql_stmt_task_invalid(self):
        provider = lists.list.ListDataProvider()
        with self.assertRaises(ValueError):
            provider._get_sql_stmt("project_task", "A@B@C@D")

    @patch.object(lists.list.gui.Message, "GetMessage")
    @patch.object(lists.list.logging, "exception")
    def test__resolveDataSourceSQL_ds_invalid_classname(self, logExp, guiMsg):
        dataSource = Mock(data_source_id="foo", resulting_classname="table_1")

        with patch(
            "cs.pcs.projects.common.lists.list.ListDataProvider.DataSource",
            new=dataSource,
        ):
            dataProvider = ListDataProvider(classname="table_2", name="bar")
            dataProvider._resolveDataSourceSQL()

        guiMsg.assert_called_once_with(
            "cdbpcs_list_ds_not_match_dp_classname", "foo", "table_2", "bar"
        )
        logExp.assert_called_once_with(guiMsg.return_value)

    @patch.object(lists.list.gui.Message, "GetMessage")
    @patch.object(lists.list.logging, "exception")
    def test__resolveDataSourceSQL_ds_rest_name_invalid(self, logExp, guiMsg):
        dataSource = Mock(
            data_source_id="foo",
            resulting_classname="table",
            rest_visible_name="invalid_rest_name",
        )

        with patch(
            "cs.pcs.projects.common.lists.list.ListDataProvider.DataSource",
            new=dataSource,
        ):
            dataProvider = ListDataProvider(classname="table", name="bar")
            dataProvider._resolveDataSourceSQL()

        guiMsg.assert_called_once_with(
            "cdbpcs_list_ds_rest_name_invalid", "foo", "invalid_rest_name", "bar"
        )
        logExp.assert_called_once_with(guiMsg.return_value)

    @patch.object(lists.list.ListDataProvider, "_get_sql_stmt")
    @patch.object(lists.list, "sqlapi")
    def test__resolveDataSourceSQL(self, sqlapi, _get_sql_stmt):
        dataSource = Mock(
            data_source_id="foo",
            resulting_classname="table",
            rest_visible_name="project",
        )

        sqlapi.RecordSet2 = Mock(
            return_value=[Mock(cdb_object_id=1), Mock(cdb_object_id=2)]
        )
        with patch(
            "cs.pcs.projects.common.lists.list.ListDataProvider.DataSource",
            new=dataSource,
        ):
            dataProvider = ListDataProvider(classname="table", name="bar")
            self.assertTupleEqual(
                ([1, 2], False), dataProvider._resolveDataSourceSQL("foo_pid")
            )

        sqlapi.RecordSet2.assert_called_once_with(sql=_get_sql_stmt.return_value)

    @patch.object(mom, "getObjectHandlesFromObjectIDs")
    @patch.object(ListDataProvider, "_resolveDataSourceSQL")
    def test_getObjectHandlesFromDataSource(self, resolveFunc, retrieveFunc):
        returned_obj_ids = ["a", "b", "c"]
        resolveFunc.return_value = [returned_obj_ids, False]
        retrieveFunc.return_value = {"a": "foo_obj_handle_1", "b": "foo_obj_handle_2"}

        dataProvider = ListDataProvider()
        handles_dict, obj_ids, isError = dataProvider.getObjectHandlesFromDataSource(
            "foo_rest_key"
        )

        resolveFunc.assert_called_with("foo_rest_key")
        retrieveFunc.assert_called_with(returned_obj_ids, False, True)
        self.assertEqual(isError, False)
        self.assertListEqual(obj_ids, ["a", "b"])
        self.assertDictEqual(handles_dict, retrieveFunc.return_value)

    @patch.object(mom, "getObjectHandlesFromObjectIDs")
    @patch.object(ListDataProvider, "_resolveDataSourceSQL")
    def test_getObjectHandlesFromDataSource_no_oids(self, resolveFunc, retrieveFunc):
        returned_obj_ids = []
        resolveFunc.return_value = [returned_obj_ids, False]

        dataProvider = ListDataProvider()
        handles_dict, obj_ids, isError = dataProvider.getObjectHandlesFromDataSource(
            "foo_rest_key"
        )

        resolveFunc.assert_called_with("foo_rest_key")
        retrieveFunc.assert_not_called()
        self.assertEqual(isError, False)
        self.assertListEqual(obj_ids, [])
        self.assertDictEqual(handles_dict, {})

    @patch("cs.pcs.projects.common.lists.list.gui")
    @patch("cs.pcs.projects.common.lists.list.logging")
    def test_generateDisplayConfigAndListItems_ListItemConfig_invalid(
        self, logging, gui
    ):
        # mock request
        request = Mock()
        # mock attributes
        listItemConfig = Mock()
        # mock functions
        isValid = Mock()
        isValid.return_value = False
        listItemConfig.name = Mock()
        listItemConfig.isValid = isValid
        with patch(
            "cs.pcs.projects.common.lists.list.ListDataProvider.ListItemConfig",
            new=listItemConfig,
        ):
            dataProvider = ListDataProvider()
            dataProvider.generateDisplayConfigAndListItems(request)
        isValid.assert_called_once()
        logging.exception.assert_called_once()
        gui.Message.GetMessage.assert_called_with(
            "cdbpcs_list_list_item_config_invalid", listItemConfig.name
        )

    @patch.object(lists.list, "_generateDisplayConfig")
    def test_generateDisplayConfigAndListItems_display_config_error(
        self, _generateDisplayConfig
    ):
        # mock request
        request = Mock()
        # mock attributes
        listItemConfig = Mock()
        listItemConfig.isValid = Mock(return_value=True)
        listOfEntries = Mock()
        listItemConfig.AllListItemConfigEntries = listOfEntries
        displayConfig = Mock()
        dictAttributeFunc = Mock()
        # mock functions
        _generateDisplayConfig.return_value = [displayConfig, dictAttributeFunc, True]
        # mock provider
        provider = MagicMock(
            spec=ListDataProvider, ListItemConfig=listItemConfig, classname="classname"
        )
        ListDataProvider.generateDisplayConfigAndListItems(provider, request)

        _generateDisplayConfig.assert_called_once_with(listOfEntries, "classname")

    @patch.object(lists.list, "_generateListItems")
    @patch.object(lists.list, "_generateDisplayConfig")
    def test_generateDisplayConfigAndListItems_list_of_items_error(
        self, _generateDisplayConfig, _generateListItems
    ):
        # mock request
        request = Mock()
        # mock attributes
        dictOfAttrFunc = Mock()
        dictOfObjHandles = Mock()
        sortedKeys = Mock()
        dataSource = Mock()
        listItemConfig = MagicMock()
        listItemConfig.isValid = Mock(return_value=True)
        listItemConfig.AllListItemConfigEntries = Mock()

        # mock functions
        getObjectHandlesFromDataSource = Mock(
            return_value=[dictOfObjHandles, sortedKeys, False]
        )
        _generateDisplayConfig.return_value = [None, dictOfAttrFunc, False]
        _generateListItems.return_value = [None, True]
        # mock provider
        provider = MagicMock(
            spec=ListDataProvider,
            data_source_id="foo",
            classname="classname",
            ListItemConfig=listItemConfig,
            DataSource=dataSource,
            getObjectHandlesFromDataSource=getObjectHandlesFromDataSource,
        )
        ListDataProvider.generateDisplayConfigAndListItems(provider, request)
        _generateDisplayConfig.assert_called_once_with(
            listItemConfig.AllListItemConfigEntries, "classname"
        )
        _generateListItems.assert_called_once_with(
            listItemConfig.name, dictOfAttrFunc, dictOfObjHandles, sortedKeys, request
        )

    @patch("cs.pcs.projects.common.lists.list.logging.exception")
    @patch("cs.pcs.projects.common.lists.list.auth", persno="foo_user")
    def test_getObjectHandlesFromRelship_valid(self, auth, exception):
        classdef = MagicMock(autospec=CDBClassDef)
        classdef.getKeyNames.return_value = ["cdb_project_id"]
        objecthndl = MagicMock(autospec=mom.CDBObjectHandle)
        objecthndl.getAccessInfo.return_value = {"read": (True,)}
        rsobjhndl = MagicMock(autospec=mom.CDBObjectHandle)
        rsobjhndl.cdb_object_id = "object_id"
        rsobjhndl.getAccessInfo.return_value = {"read": (True,)}
        rsdef = MagicMock()
        rsdef.is_valid.return_value = True
        rsdef.get_label.return_value = "Relship Name"
        rsdef.get_identifier.return_value = "foo"
        objecthndl.navigate_Relship.return_value = [rsobjhndl]
        classdef.getRelationshipByRolename.return_value = rsdef
        restkey = "bar"
        with patch(
            "cs.pcs.projects.common.lists.list.CDBClassDef", return_value=classdef
        ):
            with patch(
                "cs.pcs.projects.common.lists.list.mom.CDBObjectHandle",
                return_value=objecthndl,
            ):
                with patch(
                    "cs.pcs.projects.common.lists.list.mom.SimpleArgumentList",
                    return_value=[],
                ):
                    with patch(
                        "cs.pcs.projects.common.lists.list.mom.SimpleArgument",
                        return_value={"cdb_object_id": "bar"},
                    ):
                        dataProvider = ListDataProvider()
                        dataProvider.referer = "bar"
                        dataProvider.rolename = "Relship"

                        (
                            objhndl_dict,
                            objids,
                            error,
                            label,
                        ) = dataProvider.getObjectHandlesFromRelship(restkey)

                        classdef.getKeyNames.assert_called_once_with()
                        classdef.getRelationshipByRolename.assert_called_once_with(
                            dataProvider.rolename
                        )
                        rsdef.is_valid.assert_called_once_with()
                        rsdef.get_identifier.assert_called_once_with()
                        objecthndl.navigate_Relship.assert_called_once_with("foo")
                        objecthndl.getAccessInfo.assert_called_once_with("foo_user")
                        rsobjhndl.getAccessInfo.assert_called_once_with("foo_user")
                        exception.assert_not_called()
                        self.assertEqual(objhndl_dict, {"object_id": rsobjhndl})
                        self.assertEqual(objids, ["object_id"])
                        self.assertEqual(error, False)
                        self.assertEqual(label, "Relship Name")

    @patch("cs.pcs.projects.common.lists.list.logging.warning")
    @patch("cs.pcs.projects.common.lists.list.auth", persno="foo_user")
    def test_getObjectHandlesFromRelship_no_access_on_referer(self, auth, warning):
        classdef = MagicMock(autospec=CDBClassDef)
        classdef.getKeyNames.return_value = ["cdb_project_id"]
        objecthndl = MagicMock(autospec=mom.CDBObjectHandle)
        objecthndl.getAccessInfo.return_value = {"read": (False,)}

        restkey = "bar"
        with patch(
            "cs.pcs.projects.common.lists.list.CDBClassDef", return_value=classdef
        ):
            with patch(
                "cs.pcs.projects.common.lists.list.mom.CDBObjectHandle",
                return_value=objecthndl,
            ):
                with patch(
                    "cs.pcs.projects.common.lists.list.mom.SimpleArgumentList",
                    return_value=[],
                ):
                    with patch(
                        "cs.pcs.projects.common.lists.list.mom.SimpleArgument",
                        return_value={"cdb_object_id": "bar"},
                    ):
                        dataProvider = ListDataProvider()
                        dataProvider.referer = "bar"
                        dataProvider.rolename = "Relship"

                        (
                            objhndl_dict,
                            objids,
                            error,
                            label,
                        ) = dataProvider.getObjectHandlesFromRelship(restkey)
                        self.assertEqual(objhndl_dict, {})
                        self.assertEqual(objids, [])
                        self.assertEqual(error, True)
                        self.assertEqual(label, "")

        classdef.getKeyNames.assert_called_once_with()
        objecthndl.getAccessInfo.assert_called_once_with("foo_user")
        warning.assert_called_once_with(
            "ListDataProvider - getObjectHandlesfromRelship: "
            + "user '%s' has no read access on object of class '%s' with keys '%s' "
            + "or object does not exists.",
            "foo_user",
            "bar",
            ["bar"],
        )

    @patch("cs.pcs.projects.common.lists.list.logging.warning")
    @patch("cs.pcs.projects.common.lists.list.logging.exception")
    @patch("cs.pcs.projects.common.lists.list.auth", persno="foo_user")
    def test_getObjectHandlesFromRelship_no_access_right_returned(
        self, auth, exception, warning
    ):
        classdef = MagicMock(autospec=CDBClassDef)
        classdef.getKeyNames.return_value = ["cdb_project_id"]
        objecthndl = MagicMock(autospec=mom.CDBObjectHandle)
        objecthndl.getAccessInfo.return_value = {}

        restkey = "bar"
        with patch(
            "cs.pcs.projects.common.lists.list.CDBClassDef", return_value=classdef
        ):
            with patch(
                "cs.pcs.projects.common.lists.list.mom.CDBObjectHandle",
                return_value=objecthndl,
            ):
                with patch(
                    "cs.pcs.projects.common.lists.list.mom.SimpleArgumentList",
                    return_value=[],
                ):
                    with patch(
                        "cs.pcs.projects.common.lists.list.mom.SimpleArgument",
                        return_value={"cdb_object_id": "bar"},
                    ):
                        dataProvider = ListDataProvider()
                        dataProvider.referer = "bar"
                        dataProvider.rolename = "Relship"

                        (
                            objhndl_dict,
                            objids,
                            error,
                            label,
                        ) = dataProvider.getObjectHandlesFromRelship(restkey)

                        self.assertEqual(objhndl_dict, {})
                        self.assertEqual(objids, [])
                        self.assertEqual(error, True)
                        self.assertEqual(label, "")

        classdef.getKeyNames.assert_called_once_with()
        objecthndl.getAccessInfo.assert_called_once_with("foo_user")
        exception.assert_called_once_with(
            "ListDataProvider - _check_read_access_on_objhndl: "
            + "failed to check access on object handle"
        )
        warning.assert_called_once_with(
            "ListDataProvider - getObjectHandlesfromRelship: "
            + "user '%s' has no read access on object of class '%s' with keys '%s' "
            + "or object does not exists.",
            "foo_user",
            "bar",
            ["bar"],
        )

    @patch("cs.pcs.projects.common.lists.list.logging.exception")
    @patch("cs.pcs.projects.common.lists.list.auth", persno="foo_user")
    def test_getObjectHandlesFromRelship_no_access_on_rsobjhndl(self, auth, exception):
        classdef = MagicMock(autospec=CDBClassDef)
        classdef.getKeyNames.return_value = ["cdb_project_id"]
        objecthndl = MagicMock(autospec=mom.CDBObjectHandle)
        objecthndl.getAccessInfo.return_value = {"read": (True,)}
        rsobjhndl_1 = MagicMock(autospec=mom.CDBObjectHandle)
        rsobjhndl_1.cdb_object_id = "object_id_1"
        rsobjhndl_1.getAccessInfo.return_value = {"read": (False,)}
        rsobjhndl_2 = MagicMock(autospec=mom.CDBObjectHandle)
        rsobjhndl_2.cdb_object_id = "object_id_2"
        rsobjhndl_2.getAccessInfo.return_value = {"read": (True,)}
        rsdef = MagicMock()
        rsdef.is_valid.return_value = True
        rsdef.get_label.return_value = "Relship Name"
        rsdef.get_identifier.return_value = "foo"
        objecthndl.navigate_Relship.return_value = [rsobjhndl_1, rsobjhndl_2]
        classdef.getRelationshipByRolename.return_value = rsdef
        restkey = "bar"
        with patch(
            "cs.pcs.projects.common.lists.list.CDBClassDef", return_value=classdef
        ):
            with patch(
                "cs.pcs.projects.common.lists.list.mom.CDBObjectHandle",
                return_value=objecthndl,
            ):
                with patch(
                    "cs.pcs.projects.common.lists.list.mom.SimpleArgumentList",
                    return_value=[],
                ):
                    with patch(
                        "cs.pcs.projects.common.lists.list.mom.SimpleArgument",
                        return_value={"cdb_object_id": "bar"},
                    ):
                        dataProvider = ListDataProvider()
                        dataProvider.referer = "bar"
                        dataProvider.rolename = "Relship"

                        (
                            objhndl_dict,
                            objids,
                            error,
                            label,
                        ) = dataProvider.getObjectHandlesFromRelship(restkey)

                        classdef.getKeyNames.assert_called_once_with()
                        classdef.getRelationshipByRolename.assert_called_once_with(
                            dataProvider.rolename
                        )
                        rsdef.is_valid.assert_called_once_with()
                        rsdef.get_identifier.assert_called_once_with()
                        objecthndl.navigate_Relship.assert_called_once_with("foo")
                        objecthndl.getAccessInfo.assert_called_once_with("foo_user")
                        rsobjhndl_1.getAccessInfo.assert_called_once_with("foo_user")
                        rsobjhndl_2.getAccessInfo.assert_called_once_with("foo_user")
                        exception.assert_not_called()
                        self.assertEqual(objhndl_dict, {"object_id_2": rsobjhndl_2})
                        self.assertEqual(objids, ["object_id_2"])
                        self.assertEqual(error, False)
                        self.assertEqual(label, "Relship Name")

    @patch("cs.pcs.projects.common.lists.list.logging.exception")
    @patch("cs.pcs.projects.common.lists.list.auth", persno="foo_user")
    def test_getObjectHandlesFromRelship_invalid(self, auth, exception):
        classdef = MagicMock(autospec=CDBClassDef)
        classdef.getKeyNames.return_value = ["cdb_project_id"]
        objecthndl = MagicMock(autospec=mom.CDBObjectHandle)
        objecthndl.getAccessInfo.return_value = {"read": (True,)}
        rsobjhndl = MagicMock(autospec=mom.CDBObjectHandle)
        rsobjhndl.cdb_object_id = "object_id"
        rsobjhndl.getAccessInfo.return_value = {"read": (True,)}
        rsdef = MagicMock()
        rsdef.is_valid.return_value = False
        classdef.getRelationshipByRolename.return_value = rsdef
        restkey = "bar"
        with patch(
            "cs.pcs.projects.common.lists.list.CDBClassDef", return_value=classdef
        ):
            with patch(
                "cs.pcs.projects.common.lists.list.mom.CDBObjectHandle",
                return_value=objecthndl,
            ):
                with patch(
                    "cs.pcs.projects.common.lists.list.mom.SimpleArgumentList",
                    return_value=[],
                ):
                    with patch(
                        "cs.pcs.projects.common.lists.list.mom.SimpleArgument",
                        return_value={"cdb_object_id": "bar"},
                    ):
                        dataProvider = ListDataProvider()
                        dataProvider.referer = "bar"
                        dataProvider.rolename = "Relship"
                        (
                            objhndl_dict,
                            objids,
                            error,
                            label,
                        ) = dataProvider.getObjectHandlesFromRelship(restkey)
                        classdef.getKeyNames.assert_called_once_with()
                        classdef.getRelationshipByRolename.assert_called_once_with(
                            dataProvider.rolename
                        )
                        rsdef.is_valid.assert_called_once_with()
                        objecthndl.getAccessInfo.assert_called_once_with("foo_user")
                        rsobjhndl.getAccessInfo.assert_not_called()
                        exception.assert_not_called()
                        self.assertEqual(objhndl_dict, {})
                        self.assertEqual(objids, [])
                        self.assertEqual(error, True)
                        self.assertEqual(label, "")


class TestListItemConfig(testcase.RollbackTestCase):
    def test__getAllPrimaryEntries(self):
        # Mock ListItemConfigEntries
        configEntry1 = Mock()
        configEntry1.layout_position = "primaryText"
        configEntry2 = Mock()
        configEntry1.layout_position = "other"
        with patch(
            "cs.pcs.projects.common.lists.list.ListItemConfig.AllListItemConfigEntries",
            new=[configEntry1, configEntry2],
        ):
            listItemConfig = ListItemConfig()
            self.assertEqual(
                [configEntry1, configEntry2], listItemConfig.AllListItemConfigEntries
            )

    def test_isValid(self):
        # Mock ListItemConfigEntries
        configEntry = Mock()
        configEntry.DisplayType.component = "cs-pcs-widgets-TextRenderer"
        with patch(
            "cs.pcs.projects.common.lists.list.ListItemConfig._getAllPrimaryEntries",
            return_value=[configEntry],
        ):
            listItemConfig = ListItemConfig()
            assert listItemConfig.isValid()

    def test_getPrimaryAttribute(self):
        # Mock ListItemConfigEntries
        content = Mock()
        configEntry = Mock()
        configEntry.content = content
        with patch(
            "cs.pcs.projects.common.lists.list.ListItemConfig.isValid",
            return_value=True,
        ):
            with patch(
                "cs.pcs.projects.common.lists.list.ListItemConfig._getAllPrimaryEntries",
                return_value=[configEntry],
            ):
                listItemConfig = ListItemConfig()
                self.assertEqual(content, listItemConfig.getPrimaryAttribute())


class TestListItemConfigEntry(testcase.RollbackTestCase):
    def test_getDisplayTypeProperties(self):
        fqpyname = Mock()
        content = Mock()
        properties = Mock()
        # Mock Display Type and python func
        displayType = Mock()
        displayType.fqpyname = fqpyname
        pythonFunc = Mock()
        pythonFunc.return_value = properties
        with patch(
            "cs.pcs.projects.common.lists.list.getObjectByName", return_value=pythonFunc
        ):
            with patch(
                "cs.pcs.projects.common.lists.list.ListItemConfigEntry.content",
                new=content,
            ):
                with patch(
                    "cs.pcs.projects.common.lists.list.ListItemConfigEntry.DisplayType",
                    new=displayType,
                ):
                    listItemConfigEntry = ListItemConfigEntry()
                    self.assertEqual(
                        properties, listItemConfigEntry.getDisplayTypeProperties()
                    )
                    pythonFunc.assert_called_with(content)

    def test_getDisplayTypeComponent(self):
        component = Mock()
        displayType = Mock()
        displayType.component = component
        with patch(
            "cs.pcs.projects.common.lists.list.ListItemConfigEntry.DisplayType",
            new=displayType,
        ):
            listItemConfigEntry = ListItemConfigEntry()
            self.assertEqual(component, listItemConfigEntry.getDisplayTypeComponent())


if __name__ == "__main__":
    unittest.main()
