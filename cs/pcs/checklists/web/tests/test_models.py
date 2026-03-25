#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=protected-access

import unittest

import mock
import pytest
from cdb import testcase
from webob.exc import HTTPBadRequest

from cs.pcs.checklists.web import models


@pytest.mark.unit
class HelperMethodsTest(testcase.RollbackTestCase):
    def test__is_evaluated_rating(self):
        self.assertTrue(models._is_evaluated_rating("red"))
        self.assertFalse(models._is_evaluated_rating(""))
        self.assertFalse(models._is_evaluated_rating(None))
        self.assertFalse(models._is_evaluated_rating("clear"))


@pytest.mark.unit
class RatingsModelTest(testcase.RollbackTestCase):
    @mock.patch.object(models, "_LabelValueAccessor")
    @mock.patch.object(models.IconCache, "getIcon")
    def test__get_rating_val_icon(self, getIcon, _LabelValueAccessor):
        _LabelValueAccessor.return_value = "accessor"
        rating_model = models.RatingsModel()
        rating_model._get_rating_val_icon("iconid", "rating")
        getIcon.assert_called_once_with("iconid", accessor="accessor")

    @mock.patch.object(models.util, "get_classinfo")
    @mock.patch.object(models.i18n, "default")
    @mock.patch.object(models.RatingsModel, "_get_rating_val_icon")
    @mock.patch.object(models.util, "get_grouped_data")
    @mock.patch.object(models.util, "get_sql_condition")
    def test_get_rating_values(
        self,
        get_sql_condition,
        get_grouped_data,
        _get_rating_val_icon,
        default,
        get_classinfo,
    ):

        rating_model = models.RatingsModel()
        _get_rating_val_icon.side_effect = lambda id_, rv: id_
        get_sql_condition.return_value = "condition"

        default.return_value = "en"
        getObjectIconId = mock.MagicMock(return_value="iconid")
        get_classinfo.return_value = (
            mock.MagicMock(getObjectIconId=getObjectIconId),
            None,
        )

        rating_model.get_rating_values()

        get_sql_condition.assert_called_once_with(
            models.RATING_VALUE_TABLE_NAME,
            ["obsolete"],
            [[0]],
        )

        get_grouped_data.assert_called_once()


class ModelWithChecklistModel(testcase.RollbackTestCase):
    @mock.patch.object(models.Checklist, "ByKeys")
    def test___init__(self, ByKeys):
        model = mock.MagicMock(spec=models.ModelWithChecklist)
        self.assertIsNone(models.ModelWithChecklist.__init__(model, "foo", "bar"))
        ByKeys.assert_called_once_with(cdb_project_id="foo", checklist_id="bar")
        ByKeys.return_value.CheckAccess.assert_called_once_with("read")

    @mock.patch.object(models.Checklist, "ByKeys", return_value=None)
    def test___init___no_checklist(self, ByKeys):
        model = mock.MagicMock(spec=models.ModelWithChecklist)

        with self.assertRaises(models.HTTPNotFound):
            self.assertIsNone(models.ModelWithChecklist.__init__(model, "foo", "bar"))

        ByKeys.assert_called_once_with(cdb_project_id="foo", checklist_id="bar")

    @mock.patch.object(models.Checklist, "ByKeys")
    def test___init___access_denied(self, ByKeys):
        ByKeys.return_value.CheckAccess.return_value = None
        model = mock.MagicMock(spec=models.ModelWithChecklist)

        with self.assertRaises(models.HTTPNotFound):
            self.assertIsNone(models.ModelWithChecklist.__init__(model, "foo", "bar"))

        ByKeys.assert_called_once_with(cdb_project_id="foo", checklist_id="bar")
        ByKeys.return_value.CheckAccess.assert_called_once_with("read")


@pytest.mark.unit
class ChecklistItemsModel(testcase.RollbackTestCase):
    @mock.patch.object(models.rest, "get_collection_app")
    @mock.patch.object(models.ChecklistItem, "Query")
    def test_get_checklist_items(self, Query, get_collection_app):
        Query.return_value = ["cl1", "cl2"]
        get_collection_app.return_value = "app"

        view = mock.MagicMock(side_effect=lambda x, app: f"{x}-view")
        request = mock.MagicMock(view=view)

        items_model = mock.MagicMock(
            spec=models.ChecklistItemsModel,
        )
        items_model.checklist = mock.MagicMock(
            cdb_project_id="foo",
            checklist_id="bar",
        )

        cl_items = models.ChecklistItemsModel.get_checklist_items(items_model, request)

        Query.assert_called_once_with(
            "cdb_project_id='foo' AND checklist_id='bar'",
            access="read",
            addtl="ORDER BY position",
        )
        get_collection_app.assert_called_once_with(request)
        view.assert_has_calls(
            [mock.call("cl1", app="app"), mock.call("cl2", app="app")]
        )

        self.assertEqual(cl_items, ["cl1-view", "cl2-view"])

    @mock.patch.object(models, "open", create=True)
    @mock.patch.object(models.os.path, "join", side_effect=lambda a, b: b)
    @mock.patch.object(models.sqlapi, "SQLdbms", return_value="?")
    @mock.patch.object(models.sqlapi, "DBMS_ORACLE", "ORA")
    def test__get_sql_patterns(self, SQLdbms, join, open_):
        model = mock.MagicMock(spec=models.ChecklistItemsModel)
        self.assertEqual(
            models.ChecklistItemsModel._get_sql_patterns(model),
            (
                "SELECT {}, {}",
                open_.return_value.__enter__.return_value.read.return_value,
            ),
        )
        open_.assert_called_once_with("change_cli_position.sql", "r", encoding="utf8")

    @mock.patch.object(models, "open", create=True)
    @mock.patch.object(models.os.path, "join", side_effect=lambda a, b: b)
    @mock.patch.object(models.sqlapi, "SQLdbms", return_value="ORA")
    @mock.patch.object(models.sqlapi, "DBMS_ORACLE", "ORA")
    def test__get_sql_patterns_oracle(self, SQLdbms, join, open_):
        model = mock.MagicMock(spec=models.ChecklistItemsModel)
        self.assertEqual(
            models.ChecklistItemsModel._get_sql_patterns(model),
            (
                "SELECT {}, {} FROM dual",
                open_.return_value.__enter__.return_value.read.return_value,
            ),
        )
        open_.assert_called_once_with(
            "change_cli_position_oracle.sql", "r", encoding="utf8"
        )

    @mock.patch.object(models.sqlapi, "SQL")
    def test__update_positions(self, SQL):
        model = mock.MagicMock(
            spec=models.ChecklistItemsModel,
            checklist=mock.MagicMock,
        )
        stmt_pattern = mock.MagicMock()
        model._get_sql_patterns.return_value = (
            "SELECT {}, {}",
            stmt_pattern,
        )
        self.assertIsNone(
            models.ChecklistItemsModel._update_positions(model, [3, 2]),
        )
        stmt_pattern.format.assert_called_once_with(
            offset=20,
            cl=model.checklist,
            changed_ids="3, 2",
            changemap=("SELECT 10, 3\n" "    UNION ALL SELECT 20, 2"),
        )
        SQL.assert_called_once_with(
            stmt_pattern.format.return_value,
        )

    @mock.patch.object(models.logging, "error")
    def test_set_checklist_item_positions_no_int(self, error):
        model = mock.MagicMock(
            spec=models.ChecklistItemsModel,
            checklist=mock.MagicMock(),
        )
        request = mock.MagicMock(json=[5, "2"])
        with self.assertRaises(models.HTTPBadRequest):
            models.ChecklistItemsModel.set_checklist_item_positions(model, request)

        model.checklist.CheckAccess.assert_not_called()
        error.assert_called_once_with(
            "non-integer checklist item ID: %s",
            [5, "2"],
        )

    def test_set_checklist_item_positions_no_access(self):
        model = mock.MagicMock(
            spec=models.ChecklistItemsModel,
            checklist=mock.MagicMock(),
        )
        model.checklist.CheckAccess.return_value = False
        request = mock.MagicMock(json=[5, 2])
        with self.assertRaises(models.HTTPForbidden):
            models.ChecklistItemsModel.set_checklist_item_positions(model, request)

        model.checklist.CheckAccess.assert_called_once_with("save")

    def test_set_checklist_item_positions(self):
        model = mock.MagicMock(
            spec=models.ChecklistItemsModel,
            checklist=mock.MagicMock(),
        )
        request = mock.MagicMock(json=[5, 2])
        self.assertIsNone(
            models.ChecklistItemsModel.set_checklist_item_positions(model, request),
        )
        model.checklist.CheckAccess.assert_called_once_with("save")
        model._update_positions.assert_called_once_with(request.json)


@pytest.mark.integration
class ChecklistItemsModelIntegration(testcase.RollbackTestCase):
    def test__update_positions(self):
        pid = "cli_pos_integr_test"
        cid = 7
        models.Checklist.Create(cdb_project_id=pid, checklist_id=cid)
        for cli_id, pos in (
            (30, 0),  # pos 0, not updated -> shares pos with last changed one
            (0, 1),
            (1, 20),
            (2, 33),
            (3, 34),
            (4, 99),
        ):
            models.ChecklistItem.Create(
                cdb_project_id=pid,
                checklist_id=cid,
                cl_item_id=cli_id,
                position=pos,
            )

        model = models.ChecklistItemsModel(pid, cid)
        model._update_positions([3, 4, 1])
        model.checklist.Reload()

        ids = model.checklist.ChecklistItems.cl_item_id
        self.assertEqual(len(ids), 6)
        self.assertEqual(ids[:2], [3, 4])
        self.assertEqual(set(ids[2:4]), set([1, 30]))
        self.assertEqual(ids[4:], [0, 2])

        self.assertEqual(
            model.checklist.ChecklistItems.position,
            [10, 20, 30, 30, 31, 63],
        )


class WorkObjectsModel(testcase.RollbackTestCase):
    @mock.patch.object(models.Checklist, "KeywordQuery")
    def test_check_work_objects(self, KeywordQuery):
        r1 = mock.MagicMock()
        r2 = mock.MagicMock()
        r2.Rule.match.return_value = 0
        mock_checklist = mock.MagicMock(
            RuleReferences=[r1, r2],
            cdb_project_id="foo_pid",
            checklist_id="cid",
        )
        mock_checklist.CheckAccess.return_value = True
        KeywordQuery.return_value = [mock_checklist]
        model = mock.MagicMock(
            spec=models.WorkObjectsModel,
        )
        request = mock.MagicMock(
            json={
                "checklist_keys": [{"cdb_project_id": "foo_pid", "checklist_id": "cid"}]
            }
        )
        self.assertEqual(
            models.WorkObjectsModel.check_work_objects(model, request),
            {"foo_pid": {"cid": {r1.Rule.name: True, r2.Rule.name: False}}},
        )
        r1.Rule.match.assert_called_once_with(
            mock_checklist.Collection,
        )
        r2.Rule.match.assert_called_once_with(
            mock_checklist.Collection,
        )

    @mock.patch.object(models.Checklist, "KeywordQuery")
    @mock.patch.object(models.logging, "error")
    def test_check_work_objects_missing_ref(self, error, KeywordQuery):
        mock_checklist = mock.MagicMock(
            RuleReferences=[mock.MagicMock(Rule=None)],
            cdb_project_id="foo_pid",
            checklist_id="cid",
        )
        mock_checklist.CheckAccess.return_value = True
        KeywordQuery.return_value = [mock_checklist]
        model = mock.MagicMock(
            spec=models.WorkObjectsModel,
        )
        request = mock.MagicMock(
            json={
                "checklist_keys": [{"cdb_project_id": "foo_pid", "checklist_id": "cid"}]
            }
        )
        self.assertEqual(models.WorkObjectsModel.check_work_objects(model, request), {})
        error.assert_called_once_with(
            "WorkObjectsModel: invalid rule reference: '%s'",
            {},
        )

    def test_get_work_objects_documents_missing_keys(self):
        """
        HTTPBadRequest is raised if request.json is missing keys.
        """
        model = mock.MagicMock(
            spec=models.WorkObjectsModel,
            checklist=mock.MagicMock(),
        )
        request = mock.MagicMock(json={})
        with self.assertRaises(HTTPBadRequest):
            models.WorkObjectsModel.get_work_objects_documents(model, request)

    def test_get_work_objects_documents_rule_not_matching(self):
        """
        HTTPBadRequest is raised if no work object matches the rule_name.
        """
        ruleRefs = [mock.MagicMock(Rule=mock.MagicMock(name="foo"))]
        model = mock.MagicMock(
            spec=models.WorkObjectsModel,
            checklist=mock.MagicMock(
                RuleReferences=ruleRefs,
                cdb_project_id="foo_pid",
                checklist_id="foo_clid",
            ),
        )
        request = mock.MagicMock(json={"rule_name": "bar", "configName": "baz"})
        with self.assertRaises(HTTPBadRequest):
            models.WorkObjectsModel.get_work_objects_documents(model, request)

    @mock.patch.object(models.Checklist, "ByKeys")
    @mock.patch.object(models.mom, "getObjectHandlesFromObjectIDs", return_value=[])
    def test_get_work_objects_documents_no_documents_matching(
        self, getObjHandles, ByKeys
    ):
        """
        No items are returned if no document match the given rule.
        """
        rule = mock.MagicMock(
            match=mock.MagicMock(return_value=[mock.MagicMock(cdb_object_id="foo")])
        )
        rule.configure_mock(name="foo_rule_name")  # mocking name attribute is special
        ruleRefs = [
            mock.MagicMock(Rule=rule),
            mock.MagicMock(Rule=None),  # handles missing rule gracefully
        ]

        mock_checklist = mock.MagicMock(
            RuleReferences=ruleRefs,
            Collection=mock.MagicMock(),
            cdb_project_id="foo_pid",
            checklist_id="foo_clid",
        )
        mock_checklist.CheckAccess.return_value = True
        ByKeys.return_value = mock_checklist

        model = mock.MagicMock(
            spec=models.WorkObjectsModel,
        )
        request = mock.MagicMock(
            json={
                "rule_name": "foo_rule_name",
                "configName": "baz",
                "cdb_project_id": "foo_pid",
                "checklist_id": "foo_clid",
            }
        )

        result = models.WorkObjectsModel.get_work_objects_documents(model, request)
        self.assertDictEqual(
            result,
            {"restKey": "foo_pid@foo_clid", "ruleName": "foo_rule_name", "data": {}},
        )
        mock_checklist.CheckAccess.assert_called_once_with("read")
        rule.match.assert_called_once_with(mock_checklist.Collection)
        getObjHandles.assert_called_once_with(["foo"], False, True)

    @mock.patch.object(models.Checklist, "ByKeys")
    @mock.patch.object(models.mom, "getObjectHandlesFromObjectIDs", return_value="bar")
    @mock.patch.object(models.ListItemConfig, "KeywordQuery", return_value=[])
    def test_get_work_objects_documents_config_not_found(
        self, configQuery, getObjHandles, ByKeys
    ):
        """
        HTTPBadRequest is raised if item config of given name is not found
        in the database
        """
        rule = mock.MagicMock(
            match=mock.MagicMock(return_value=[mock.MagicMock(cdb_object_id="foo")])
        )
        rule.configure_mock(name="foo_rule_name")  # mocking name attribute is special
        ruleRefs = [mock.MagicMock(Rule=rule)]
        mock_checklist = mock.MagicMock(
            RuleReferences=ruleRefs,
            Collection=mock.MagicMock(),
            cdb_project_id="foo_pid",
            checklist_id="foo_clid",
        )
        mock_checklist.CheckAccess.return_value = True
        ByKeys.return_value = mock_checklist
        model = mock.MagicMock(
            spec=models.WorkObjectsModel,
        )
        request = mock.MagicMock(
            json={
                "rule_name": "foo_rule_name",
                "configName": "baz",
                "cdb_project_id": "foo_pid",
                "checklist_id": "foo_clid",
            }
        )
        with self.assertRaises(HTTPBadRequest):
            models.WorkObjectsModel.get_work_objects_documents(model, request)

        rule.match.assert_called_once_with(mock_checklist.Collection)
        configQuery.assert_called_once_with(name="baz")
        getObjHandles.assert_called_once_with(["foo"], False, True)

    @mock.patch.object(models.Checklist, "ByKeys")
    @mock.patch.object(models.cdb_util, "get_label", return_value="foo_{}")
    @mock.patch.object(
        models.mom, "getObjectHandlesFromObjectIDs", return_value="foo_objHandles"
    )
    @mock.patch.object(
        models.ListItemConfig, "KeywordQuery", return_value=["foo_config"]
    )
    def test_get_work_objects_documents_configError(
        self, configQuery, getObjHandles, getLabel, ByKeys
    ):
        """
        ConfigError is returned if given configuration is faulty
        """
        rule = mock.MagicMock(
            match=mock.MagicMock(return_value=[mock.MagicMock(cdb_object_id="foo")])
        )
        rule.configure_mock(name="foo_rule_name")  # mocking name attribute is special
        ruleRefs = [mock.MagicMock(Rule=rule)]
        mock_checklist = mock.MagicMock(
            RuleReferences=ruleRefs,
            Collection=mock.MagicMock(),
            cdb_project_id="foo_pid",
            checklist_id="foo_clid",
        )
        mock_checklist.CheckAccess.return_value = True
        ByKeys.return_value = mock_checklist
        model = mock.MagicMock(
            spec=models.WorkObjectsModel,
        )
        request = mock.MagicMock(
            json={
                "rule_name": "foo_rule_name",
                "configName": "foo_config_name",
                "cdb_project_id": "foo_pid",
                "checklist_id": "foo_clid",
            }
        )
        model._get_list_items_and_config_entries.return_value = (
            "empty_dict",
            "empty_list",
            True,
        )
        result = models.WorkObjectsModel.get_work_objects_documents(model, request)

        self.assertDictEqual(
            result,
            {
                "restKey": "foo_pid@foo_clid",
                "ruleName": "foo_rule_name",
                "data": {
                    "title": "",
                    "items": "empty_list",
                    "displayConfigs": {"foo_config_name": "empty_dict"},
                    "configError": "foo_foo_config_name",
                },
            },
        )
        rule.match.assert_called_once_with(mock_checklist.Collection)
        configQuery.assert_called_once_with(name="foo_config_name")
        getObjHandles.assert_called_once_with(["foo"], False, True)
        getLabel.assert_called_once_with(
            "cs.pcs.projects.common.lists.list.config_error_list_item_config"
        )
        model._get_list_items_and_config_entries.assert_called_once_with(
            "foo_config", "foo_objHandles", "documents", "foo_config_name", request
        )

    @mock.patch.object(models.Checklist, "ByKeys")
    @mock.patch.object(
        models.mom, "getObjectHandlesFromObjectIDs", return_value="foo_objHandles"
    )
    @mock.patch.object(
        models.ListItemConfig, "KeywordQuery", return_value=["foo_config"]
    )
    def test_get_work_objects_documents(self, configQuery, getObjHandles, ByKeys):
        """
        Resolved list item configuration is returned.
        """
        rule = mock.MagicMock(
            match=mock.MagicMock(return_value=[mock.MagicMock(cdb_object_id="foo")])
        )
        rule.configure_mock(name="foo_rule_name")  # mocking name attribute is special
        ruleRefs = [mock.MagicMock(Rule=rule)]
        mock_checklist = mock.MagicMock(
            RuleReferences=ruleRefs,
            Collection=mock.MagicMock(),
            cdb_project_id="foo_pid",
            checklist_id="foo_clid",
        )
        mock_checklist.CheckAccess.return_value = True
        ByKeys.return_value = mock_checklist
        model = mock.MagicMock(
            spec=models.WorkObjectsModel,
        )
        request = mock.MagicMock(
            json={
                "rule_name": "foo_rule_name",
                "configName": "foo_config_name",
                "cdb_project_id": "foo_pid",
                "checklist_id": "foo_clid",
            }
        )
        model._get_list_items_and_config_entries.return_value = (
            "result_dict",
            "result_list",
            False,
        )
        result = models.WorkObjectsModel.get_work_objects_documents(model, request)
        self.assertDictEqual(
            result,
            {
                "restKey": "foo_pid@foo_clid",
                "ruleName": "foo_rule_name",
                "data": {
                    "title": "",
                    "items": "result_list",
                    "displayConfigs": {"foo_config_name": "result_dict"},
                    "configError": "",
                },
            },
        )
        rule.match.assert_called_once_with(mock_checklist.Collection)
        configQuery.assert_called_once_with(name="foo_config_name")
        getObjHandles.assert_called_once_with(["foo"], False, True)
        model._get_list_items_and_config_entries.assert_called_once_with(
            "foo_config", "foo_objHandles", "documents", "foo_config_name", request
        )

    @mock.patch.object(models.logging, "exception")
    @mock.patch.object(models.gui.Message, "GetMessage", return_value="foo_msg")
    def test__get_list_items_and_config_entries_config_not_valid(self, getMsg, log_ex):
        model = mock.MagicMock(spec=models.WorkObjectsModel)
        list_item_config = mock.MagicMock(
            spec=models.ListItemConfig, isValid=mock.MagicMock(return_value=False)
        )
        obj_handles_dict = mock.MagicMock()
        request = mock.MagicMock()

        result = models.WorkObjectsModel._get_list_items_and_config_entries(
            model,
            list_item_config,
            obj_handles_dict,
            "foo_class_name",
            "foo_config_name",
            request,
        )

        self.assertEqual(result, ({}, [], True))
        getMsg.assert_called_once_with(
            "cdbpcs_list_list_item_config_invalid", "foo_config_name"
        )
        log_ex.assert_called_once_with(getMsg.return_value)

    @mock.patch.object(models, "_generateDisplayConfig", return_value=())
    def test__get_list_items_and_config_entries_display_config_error(
        self, _generateDisplayConfig
    ):
        model = mock.MagicMock(spec=models.WorkObjectsModel)
        list_item_config = mock.MagicMock(
            spec=models.ListItemConfig,
            isValid=mock.MagicMock(return_value=True),
            AllListItemConfigEntries=mock.MagicMock(),
        )
        obj_handles_dict = mock.MagicMock()
        request = mock.MagicMock()
        _generateDisplayConfig.return_value = "foo", "bar", True
        result = models.WorkObjectsModel._get_list_items_and_config_entries(
            model,
            list_item_config,
            obj_handles_dict,
            "foo_class_name",
            "foo_config_name",
            request,
        )

        self.assertEqual(result, ({}, [], True))

        _generateDisplayConfig.assert_called_once_with(
            list_item_config.AllListItemConfigEntries, "foo_class_name"
        )

    @mock.patch.object(models, "_generateListItems", return_value=())
    @mock.patch.object(models, "_generateDisplayConfig", return_value=())
    def test__get_list_items_and_config_entries_list_error(
        self, _generateDisplayConfig, _generateListItems
    ):
        model = mock.MagicMock(spec=models.WorkObjectsModel)
        list_item_config = mock.MagicMock(
            spec=models.ListItemConfig,
            isValid=mock.MagicMock(return_value=True),
            AllListItemConfigEntries=mock.MagicMock(),
        )
        obj_handles_dict = mock.MagicMock(keys=mock.MagicMock())
        request = mock.MagicMock()
        _generateDisplayConfig.return_value = "foo", "bar", False
        _generateListItems.return_value = "bam", True
        result = models.WorkObjectsModel._get_list_items_and_config_entries(
            model,
            list_item_config,
            obj_handles_dict,
            "foo_class_name",
            "foo_config_name",
            request,
        )

        self.assertEqual(result, ({}, [], True))

        _generateDisplayConfig.assert_called_once_with(
            list_item_config.AllListItemConfigEntries, "foo_class_name"
        )
        _generateListItems.assert_called_once_with(
            "foo_config_name",
            "bar",
            obj_handles_dict,
            obj_handles_dict.keys.return_value,
            request,
        )

    @mock.patch.object(models, "_generateListItems", return_value=())
    @mock.patch.object(models, "_generateDisplayConfig", return_value=())
    def test__get_list_items_and_config_entries(
        self, _generateDisplayConfig, _generateListItems
    ):
        model = mock.MagicMock(spec=models.WorkObjectsModel)
        list_item_config = mock.MagicMock(
            spec=models.ListItemConfig,
            isValid=mock.MagicMock(return_value=True),
            AllListItemConfigEntries=mock.MagicMock(),
        )
        obj_handles_dict = mock.MagicMock(keys=mock.MagicMock())
        request = mock.MagicMock()
        _generateDisplayConfig.return_value = "foo", "bar", False
        _generateListItems.return_value = "bam", False
        result = models.WorkObjectsModel._get_list_items_and_config_entries(
            model,
            list_item_config,
            obj_handles_dict,
            "foo_class_name",
            "foo_config_name",
            request,
        )

        self.assertEqual(result, ("foo", "bam", False))

        _generateDisplayConfig.assert_called_once_with(
            list_item_config.AllListItemConfigEntries, "foo_class_name"
        )
        _generateListItems.assert_called_once_with(
            "foo_config_name",
            "bar",
            obj_handles_dict,
            obj_handles_dict.keys.return_value,
            request,
        )


@pytest.mark.unit
class ChecklistsProgressModel(testcase.RollbackTestCase):
    @mock.patch.object(models.logging, "error")
    def test_get_checklists_progress_missing_attribute_in_payload(self, log_err):
        request = mock.MagicMock()
        model = mock.MagicMock(spec=models.ChecklistsProgressModel)
        with self.assertRaises(HTTPBadRequest):
            models.ChecklistsProgressModel.get_checklists_progress(model, request)

        log_err.assert_called_once_with("No Keys for Checklists")

    @mock.patch.object(models.logging, "error")
    def test_get_checklists_progress_keys_not_a_list(self, log_err):
        request = mock.MagicMock()
        request.json = {"checklist_keys": "Not a list"}
        model = mock.MagicMock(spec=models.ChecklistsProgressModel)
        with self.assertRaises(HTTPBadRequest):
            models.ChecklistsProgressModel.get_checklists_progress(model, request)

        log_err.assert_called_once_with("Keys for Checklist not a list")

    def test_get_checklists_progress_no_keys(self):
        request = mock.MagicMock()
        request.json = {"checklist_keys": []}
        model = mock.MagicMock(spec=models.ChecklistsProgressModel)
        self.assertDictEqual(
            models.ChecklistsProgressModel.get_checklists_progress(model, request), {}
        )

    @mock.patch.object(models, "auth", persno="foo_user")
    @mock.patch.object(models, "logging")
    @mock.patch.object(models.Checklist, "Query", return_value=None)
    def test_get_checklists_progress_no_access(self, Query, logging, auth):
        request = mock.MagicMock()
        request.json = {
            "checklist_keys": [{"cdb_project_id": "foo", "checklist_id": "bar1"}]
        }
        model = mock.MagicMock(spec=models.ChecklistsProgressModel)
        self.assertDictEqual(
            models.ChecklistsProgressModel.get_checklists_progress(model, request), {}
        )
        logging.exception.assert_called_once_with(
            "ChecklistProgressModel - '%s' has no read access on checklists: '%s'",
            "foo_user",
            [{"cdb_project_id": "foo", "checklist_id": "bar1"}],
        )
        Query.assert_called_once_with(
            "(cdb_project_id='foo' AND checklist_id='bar1')", access="read"
        )

    @mock.patch.object(models, "RatingsModel")
    @mock.patch.object(models.util, "get_grouped_data")
    @mock.patch.object(models.Checklist, "Query")
    def test_get_checklists_progress(self, cl_query, get_grouped_data, ratings_model):

        condition = (
            "(cdb_project_id='foo' AND checklist_id='bar1') OR "
            "(cdb_project_id='foo' AND checklist_id='bar2') OR "
            "(cdb_project_id='foo' AND checklist_id='bar3')"
        )

        mock_cl_1 = mock.MagicMock(cdb_project_id="foo", checklist_id="bar1")
        mock_cl_2 = mock.MagicMock(cdb_project_id="foo", checklist_id="bar2")
        cl_query.return_value = [mock_cl_1, mock_cl_2]

        get_grouped_data.return_value = {"foo": {"bar1": ["baz1"], "bar2": ["baz2"]}}
        request = mock.MagicMock()
        request.json = {
            "checklist_keys": [
                {"cdb_project_id": "foo", "checklist_id": "bar1"},
                {"cdb_project_id": "foo", "checklist_id": "bar2"},
                {"cdb_project_id": "foo", "checklist_id": "bar3"},
            ]
        }
        model = mock.MagicMock(spec=models.ChecklistsProgressModel)
        model.get_checklist_progress = mock.MagicMock(return_value="bam")

        self.assertDictEqual(
            models.ChecklistsProgressModel.get_checklists_progress(model, request),
            {"foo": {"bar1": "bam", "bar2": "bam"}},
        )
        cl_query.assert_called_once_with(condition, access="read")
        model.get_checklist_progress.assert_has_calls(
            [
                mock.call(
                    request,
                    mock_cl_1,
                    ratings_model.return_value.get_rating_values.return_value,
                    ["baz1"],
                ),
                mock.call(
                    request,
                    mock_cl_2,
                    ratings_model.return_value.get_rating_values.return_value,
                    ["baz2"],
                ),
            ]
        )
        get_grouped_data.assert_called_once_with(
            "cdbpcs_cl_item", condition, "cdb_project_id", "checklist_id"
        )
        ratings_model.assert_called_once()
        ratings_model.return_value.get_rating_values.assert_called_once()

    @mock.patch.object(models, "RuleReferenceModel")
    @mock.patch.object(models.olc.StateDefinition, "ByKeys")
    def test_get_checklist_progress(
        self,
        state_byKeys,
        rule_ref_model,
    ):
        request = mock.MagicMock()
        model = mock.MagicMock(spec=models.ChecklistsProgressModel)
        cl = mock.MagicMock(
            cdb_objektart="foo_objektart",
            cdb_project_id="foo_project_id",
            checklist_id="foo_checklist_id",
            status="foo_status",
            rating_scheme="foo_rating_scheme",
            rating_id="foo_rating_id",
            type="Deliverable",
            Collection=["foo_work_object_1", "foo_work_object_2"],
        )
        state_byKeys.return_value = mock.MagicMock(StateText={"": "bar_status"})
        rating_values = {
            "foo_rating_scheme": {
                "foo_rating_id": [
                    {
                        "icon": "bar_icon",  # not used since Deliverable
                        "label": "bar_label",
                        "color": "bar_color",  # not used since Deliverable
                    }
                ]
            }
        }
        cl_items = [
            {"rating_id": "foo_cl_item_1"},
            {"rating_id": "foo_cl_item_2"},
            {"rating_id": "clear"},  # this cl item will count as not evaluated
        ]
        rule_ref_model.return_value = mock.MagicMock()
        mock_rule = mock.MagicMock(
            Rule=mock.MagicMock(match=mock.MagicMock(return_value=["foo_matching_obj"]))
        )
        rule_ref_model.return_value.get_rule_references = mock.MagicMock(
            return_value=[mock_rule]
        )

        self.assertDictEqual(
            models.ChecklistsProgressModel.get_checklist_progress(
                model, request, cl, rating_values, cl_items
            ),
            {
                "status": "bar_status",
                "rating": "bar_label",
                "icon": "",
                "color": "",
                "max_items": 3,
                "evaluated_items": 2,
                "max_objects": 1,
                "evaluated_objects": 1,
                "isDeliverable": True,
            },
        )
        state_byKeys.assert_called_once_with(
            statusnummer="foo_status", objektart="foo_objektart"
        )

        rule_ref_model.assert_called_once_with("foo_project_id", "foo_checklist_id")
        rule_ref_model.return_value.get_rule_references.assert_called_once_with(request)


if __name__ == "__main__":
    unittest.main()
