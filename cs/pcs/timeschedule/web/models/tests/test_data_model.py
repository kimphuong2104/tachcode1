#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access,too-many-lines

import unittest

import pytest
from cdb import testcase
from mock import MagicMock, call, patch
from webob.exc import HTTPBadRequest

from cs.pcs.timeschedule import TimeSchedule
from cs.pcs.timeschedule.web import plugins
from cs.pcs.timeschedule.web.models import data_model


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


@pytest.mark.unit
class DataModel(testcase.RollbackTestCase):
    def _get_model(self):
        schedule = TimeSchedule.Create(name="foö", cdb_project_id="bär")
        return data_model.DataModel(schedule.cdb_object_id)

    @patch.object(data_model.ColumnDefinition, "ByGroup")
    @patch.object(data_model.DataModel, "collect_plugins")
    @patch.object(data_model.DataModel, "get_object_from_uuid")
    def test___init__(self, get_object_from_uuid, collect_plugins, ByGroup):
        "model and super class are initialized"
        model = self._get_model()
        # reset calls made by _get_model
        collect_plugins.reset_mock()
        ByGroup.reset_mock()

        model.__init__("foo")  # pylint: disable=unnecessary-dunder-call
        self.assertEqual(model.columns, ByGroup.return_value)
        self.assertEqual(
            model.plugin_signal,
            get_object_from_uuid.return_value.schedule_plugin_signal,
        )
        self.assertEqual(
            model.column_group,
            get_object_from_uuid.return_value.schedule_column_group,
        )
        collect_plugins.assert_called_once_with(model.plugin_signal)
        ByGroup.assert_called_once_with(model.column_group)

    def test_get_row(self):
        "returns row JSON data"
        model = self._get_model()
        self.assertEqual(
            model.get_row(1, "foo", "bar", "pinned_oid", None),
            {
                "id": "foo@pinned_oid",
                "rowNumber": 1,
                "columns": [],
                "restLink": "bar",
            },
        )
        self.assertEqual(
            model.get_row(1, "foo", "bar", "pinned_oid", "parent_oid"),
            {
                "id": "foo@parent_oid@pinned_oid",
                "rowNumber": 1,
                "columns": [],
                "restLink": "bar",
            },
        )

    @patch.object(
        data_model.sqlapi, "SQLdbms", return_value=data_model.sqlapi.DBMS_ORACLE
    )
    def test__get_pinned_oids_oracle(self, SQLdbms):
        model = self._get_model()
        model.context_object_id = "context"

        with patch.object(data_model.sqlapi, "RecordSet2") as RecordSet2:
            content1 = MagicMock(relation="foo", id="bar")
            content2 = MagicMock(relation="foo", id="baz")
            RecordSet2.return_value = [content1, content2]
            self.assertEqual(model._get_pinned_oids(), [("bar", "foo"), ("baz", "foo")])

        RecordSet2.assert_called_once_with(
            sql="""
            SELECT o.id, o.relation
                FROM cdb_object  o
            LEFT OUTER JOIN cdbpcs_ts_content  c
                ON o.id = c.content_oid
            WHERE c.view_oid='context'
            ORDER BY c.position
            """
        )
        SQLdbms.assert_called_once_with()

    @patch.object(
        data_model.sqlapi, "SQLdbms", return_value=data_model.sqlapi.DBMS_MSSQL
    )
    def test__get_pinned_oids_other_dbms(self, SQLdbms):
        model = self._get_model()
        model.context_object_id = "context"

        with patch.object(data_model.sqlapi, "RecordSet2") as RecordSet2:
            content1 = MagicMock(relation="foo", id="bar")
            content2 = MagicMock(relation="foo", id="baz")
            RecordSet2.return_value = [content1, content2]
            self.assertEqual(model._get_pinned_oids(), [("bar", "foo"), ("baz", "foo")])

        RecordSet2.assert_called_once_with(
            sql="""
            SELECT o.id, o.relation
                FROM cdb_object AS o
            LEFT OUTER JOIN cdbpcs_ts_content AS c
                ON o.id = c.content_oid
            WHERE c.view_oid='context'
            ORDER BY c.position
            """
        )
        SQLdbms.assert_called_once_with()

    def test__resolve_structure_pinned_not_iter(self):
        "fails if pinned or any pinned value is not iterable"
        model = self._get_model()
        request = MagicMock()
        with self.assertRaises(TypeError) as error:
            model._resolve_structure(None, request)
        self.assertEqual("'NoneType' object is not iterable", str(error.exception))
        with self.assertRaises(TypeError) as error:
            model._resolve_structure([None], request)
        self.assertEqual("'NoneType' object is not iterable", str(error.exception))

    def test__resolve_structure_pinned_not_iter(self):
        "fails if any pinned value does not contain exactly 2 values"
        model = self._get_model()
        request = MagicMock()
        with self.assertRaises(ValueError) as error:
            model._resolve_structure([(1, 2, 3)], request)
        self.assertEqual("too many values to unpack (expected 2)", str(error.exception))
        with self.assertRaises(ValueError) as error:
            model._resolve_structure([(1,)], request)
        self.assertEqual(
            "not enough values to unpack (expected 2, got 1)", str(error.exception)
        )

    def test__resolve_structure(self):
        "resolves content successfully"
        resolve_foo = MagicMock(return_value=["f", "o", "o"])
        resolve_bar = MagicMock(return_value=["b", "a", "r"])
        request = MagicMock()
        model = self._get_model()
        model.plugins = {
            "foo": MagicMock(ResolveStructure=resolve_foo),
            "bar": MagicMock(ResolveStructure=resolve_bar),
            "unused": MagicMock(),
        }
        with patch.object(data_model.logging, "warning") as warning:
            self.assertEqual(
                model._resolve_structure(
                    [
                        ("1", "foo"),
                        ("2", "bar"),
                        ("3", "baz"),  # no plugin for this one
                    ],
                    request,
                ),
                ["f", "o", "o", "b", "a", "r"],
            )

        resolve_foo.assert_called_once_with("1", request)
        resolve_bar.assert_called_once_with("2", request)
        model.plugins["unused"].ResolvedStructure.assert_not_called()
        warning.assert_called_once_with(
            "no plugin found for relation '%s'",
            "baz",
        )

    @patch.object(data_model, "get_oids_by_relation", return_value=[("cdbpcs_task", 1)])
    def test__get_record_tuples_not_str(self, get_oids_by_relation):
        "fails if first value in resolved_oids is not a str"
        model = self._get_model()
        oids = "oids"
        with self.assertRaises(ValueError) as error:
            model._get_record_tuples(oids)
        self.assertEqual("non-string oid value: '1'", str(error.exception))
        get_oids_by_relation.assert_called_once_with("oids")

    def test_GetQueryStrFromOids_not_str(self):
        "fails if oid value in is not a str"
        oids = 1
        with self.assertRaises(ValueError) as error:
            plugins.TimeSchedulePlugin.GetQueryStrFromOids(oids)
        self.assertEqual("non-string oid value: '1'", str(error.exception))

    @patch.object(
        data_model,
        "get_oids_by_relation",
        return_value=[("cdbpcs_task", ["a", "b"]), ("cdbpcs_project", ["c"])],
    )
    @patch.object(plugins, "get_oid_query_str", autospec=True)
    def test_get_record_tuples(self, get_oid_query_str, get_oids_by_relation):
        resolved_oids = "res_oids"
        model = self._get_model()
        with patch.object(
            data_model.sqlapi, "RecordSet2", return_value=["R1", "R2"]
        ) as RecordSet2:
            self.assertEqual(
                model._get_record_tuples(resolved_oids),
                [
                    ("cdbpcs_task", "R1"),
                    ("cdbpcs_task", "R2"),
                    ("cdbpcs_project", "R1"),
                    ("cdbpcs_project", "R2"),
                ],
            )

        get_oid_query_str.assert_has_calls(
            [
                call(["a", "b"]),
                call(["c"]),
            ]
        )
        RecordSet2.assert_has_calls(
            [
                call("cdbpcs_task", get_oid_query_str.return_value, access="read"),
                call("cdbpcs_project", get_oid_query_str.return_value, access="read"),
            ],
            # iter() calls cannot be asserted
            any_order=True,
        )
        self.assertEqual(RecordSet2.call_count, 2)
        self.assertEqual(get_oid_query_str.call_count, 2)
        get_oids_by_relation.assert_called_once_with("res_oids")

    def test__get_readable(self):
        "returns readable pcs_levels in original order"
        model = self._get_model()
        ordered_oids = [
            data_model.util.PCS_LEVEL("A", "foo", 0),
            data_model.util.PCS_LEVEL("B", "foo", 0),
            data_model.util.PCS_LEVEL("C", "foo", 0),
            data_model.util.PCS_LEVEL("C.1", "foo", 1),
            data_model.util.PCS_LEVEL("D", "bar", 0),
        ]
        readable_oids = ["D", "B", "C.1"]
        self.assertEqual(
            model._get_readable(ordered_oids, readable_oids),
            [
                data_model.util.PCS_LEVEL("B", "foo", 0),
                # C.1's parent is not readable
                data_model.util.PCS_LEVEL("D", "bar", 0),
            ],
        )

    @patch.object(data_model.util, "get_tree_nodes", autospec=True)
    @patch.object(data_model, "get_node", autospec=True)
    @patch.object(data_model, "get_restlinks_in_batch", autospec=True)
    def test__get_data_oids(self, get_restlinks_in_batch, get_node, get_tree_nodes):
        "returns data successfully"
        model = MagicMock(
            spec=data_model.DataModel,
            context_object_id="ctx",
            with_baselines=True,
        )
        model._get_readable.return_value = [
            data_model.util.PCS_LEVEL("oid1", "tbl1", "1"),
            data_model.util.PCS_LEVEL("oid2", "tbl2", 2.1),
            data_model.util.PCS_LEVEL("oid3", "tbl2", 2.1, "bl_oid"),
        ]

        request = MagicMock()

        self.assertEqual(
            data_model.DataModel._get_data(model, "A", "B", request),
            (
                [
                    model.get_row.return_value,
                    model.get_row.return_value,
                    model.get_row.return_value,
                ],
                get_tree_nodes.return_value,
                {"oid3": ("tbl2", "bl_oid")},
            ),
        )
        get_restlinks_in_batch.assert_called_once_with("B", request)
        model._get_readable.assert_called_once_with(
            "A",
            get_restlinks_in_batch.return_value,
        )
        model.get_row.assert_has_calls(
            [
                call(0, "oid1", get_restlinks_in_batch.return_value["oid1"], "", None),
                call().get("id"),
                call(1, "oid2", get_restlinks_in_batch.return_value["oid2"], "", None),
                call().get("id"),
                call(2, "oid3", get_restlinks_in_batch.return_value["oid3"], "", None),
                call().get("id"),
            ]
        )
        self.assertEqual(model.get_row.call_count, 3)
        get_node.assert_has_calls(
            [
                call(0, model._get_is_expanded(), model.get_row().get()),
                call(1, model._get_is_expanded(), model.get_row().get()),
                call(2, model._get_is_expanded(), model.get_row().get()),
            ]
        )
        self.assertEqual(get_node.call_count, 3)
        get_tree_nodes.assert_called_once_with(
            3 * [get_node.return_value],
            [1, 2, 2],
        )

    @patch.object(
        data_model.DataModel,
        "_get_baseline_data",
        autospec=True,
        return_value=("records", "mapping"),
    )
    @patch.object(
        data_model.DataModel,
        "_get_full_data_first_page",
        autospec=True,
        return_value={"full": True},
    )
    @patch.object(
        data_model.DataModel,
        "_get_data",
        autospec=True,
        return_value=("rows", "tree_nodes", "bl"),
    )
    @patch.object(
        data_model.DataModel,
        "_get_record_tuples",
        autospec=True,
        return_value=[("relation", MagicMock())],
    )
    @patch.object(
        data_model.DataModel,
        "_resolve_structure",
        autospec=True,
        return_value=([("ID", "relation")]),
    )
    @patch.object(
        data_model.DataModel, "_get_pinned_oids", autospec=True, return_value=["A", "B"]
    )
    def test_get_data(
        self,
        _get_pinned_oids,
        _resolve_structure,
        _get_record_tuples,
        _get_data,
        _get_full_data_first_page,
        _get_baseline_data,
    ):
        "returs application JSON data"
        request = MagicMock()
        model = self._get_model()
        model.first_page_size = 0
        self.maxDiff = None
        self.assertCountEqual(
            model.get_data(request),
            {
                "error": False,
                "rows": _get_data.return_value[0],
                "treeNodes": _get_data.return_value[1],
                "baselineMapping": _get_baseline_data.return_value[1],
                "full": True,
                "relships": [],
                "plugins": [
                    {
                        "catalog": {
                            "catalogName": "cdbpcs_tasks_uuid",
                            "catalogTableURL": request.link.return_value,
                            "className": "cdbpcs_task",
                            "directCreate": False,
                            "formData": {"cdb_project_id": "bär"},
                            "isMultiSelect": True,
                            "isNewWindowOperation": False,
                            "itemsURL": request.link.return_value,
                            "offerOperations": True,
                            "proposalCatalogURL": request.link.return_value,
                            "proposalLabel": "Zuletzt ausgew\xe4hlt",
                            "queryFormURL": request.link.return_value,
                            "selectURL": request.link.return_value,
                            "tableDefURL": request.link.return_value,
                            "typeAheadURL": request.link.return_value,
                            "userSettings": {
                                "preview": "",
                                "settingKey": "cdbpcs_tasks_uuid",
                            },
                            "valueCheckURL": request.link.return_value,
                        },
                        "classname": "cdbpcs_task",
                        "icon": "cdbpcs_task",
                        "title": "Projektaufgaben",
                    },
                    {
                        "catalog": {
                            "catalogName": "cdbpcs_projects_uuid",
                            "catalogTableURL": request.link.return_value,
                            "className": "cdbpcs_project",
                            "directCreate": False,
                            "formData": {"cdb_project_id": "bär"},
                            "isMultiSelect": True,
                            "isNewWindowOperation": False,
                            "itemsURL": request.link.return_value,
                            "offerOperations": True,
                            "proposalCatalogURL": request.link.return_value,
                            "proposalLabel": "Zuletzt ausgew\xe4hlt",
                            "queryFormURL": request.link.return_value,
                            "selectURL": request.link.return_value,
                            "tableDefURL": request.link.return_value,
                            "typeAheadURL": request.link.return_value,
                            "userSettings": {
                                "preview": "",
                                "settingKey": "cdbpcs_projects_uuid",
                            },
                            "valueCheckURL": request.link.return_value,
                        },
                        "classname": "cdbpcs_project",
                        "icon": "cdbpcs_project",
                        "title": "Projekte",
                    },
                ],
            },
        )
        _get_pinned_oids.assert_called_once_with(model)
        _resolve_structure.assert_called_once_with(
            model,
            _get_pinned_oids.return_value,
            request,
        )
        _get_record_tuples.assert_called_once_with(
            model,
            _resolve_structure.return_value,
        )
        _get_data.assert_called_once_with(
            model,
            _resolve_structure.return_value,
            _get_record_tuples.return_value,
            request,
        )
        _get_full_data_first_page.assert_called_once_with(
            model,
            _get_data.return_value[1],  # tree_nodes
            _get_record_tuples.return_value,
            _get_baseline_data.return_value[0],
            _get_data.return_value[2],
            request,
        )

    @patch.object(data_model.util, "get_tree_nodes", autospec=True)
    @patch.object(data_model, "get_restlinks_in_batch")
    def test__get_data_empty(self, get_restlinks_in_batch, get_tree_nodes):
        request = MagicMock()
        request.path = ""
        model = MagicMock(data_model.DataModel)
        model.context_object_id = "context_object_id"
        model.with_baselines = False
        model._get_readable.return_value = []
        model.get_user_settings.return_value = {"collapsedRows": []}
        get_restlinks_in_batch.return_value = {}
        get_tree_nodes.return_value = None

        data = data_model.DataModel._get_data(model, "resolved", "ts_records", request)
        self.assertEqual(data[0], [])
        self.assertEqual(data[1], None)
        self.assertEqual(data[2], {})

    @patch.object(data_model.util, "get_tree_nodes", autospec=True)
    @patch.object(data_model, "get_restlinks_in_batch")
    def test__get_data_resources(self, get_restlinks_in_batch, get_tree_nodes):
        # Object structure:
        # Pool
        #   Demand
        #   Resource Pool Assignment
        #       Demand
        #       Assignment
        #   Resource Pool Assignment
        # Demand
        # Assingment
        # Resource Pool Assignment
        #   Assingment
        #   Demand

        def get_row_side_effect(a1, oid, a2, a3, a4):
            return {"id": oid}

        request = MagicMock()
        request.path = ""
        get_tree_nodes.return_value = None
        model = MagicMock(data_model.DataModel)
        model.context_object_id = "context_object_id"
        model.with_baselines = False
        model.get_row.side_effect = get_row_side_effect
        model._get_is_expanded.return_value = True
        get_restlinks_in_batch.return_value = {
            "object_id_1": 1,
            "object_id_2": 2,
            "object_id_3": 3,
            "object_id_4": 4,
            "object_id_5": 5,
            "object_id_6": 6,
            "object_id_7": 7,
            "object_id_8": 8,
            "object_id_9": 9,
            "object_id_10": 10,
            "object_id_11": 11,
        }
        model.get_user_settings.return_value = {"collapsedRows": []}
        model._get_readable.return_value = [
            MagicMock(cdb_object_id="object_id_1", level=0, table_name="Pool"),
            MagicMock(
                cdb_object_id="object_id_2", level=1, table_name="cdbpcs_prj_demand"
            ),
            MagicMock(
                cdb_object_id="object_id_3",
                level=1,
                table_name="Resource Pool Assignment",
            ),
            MagicMock(
                cdb_object_id="object_id_4", level=2, table_name="cdbpcs_prj_demand"
            ),
            MagicMock(
                cdb_object_id="object_id_5", level=2, table_name="cdbpcs_prj_alloc"
            ),
            MagicMock(
                cdb_object_id="object_id_6",
                level=1,
                table_name="Resource Pool Assignment",
            ),
            MagicMock(
                cdb_object_id="object_id_7", level=0, table_name="cdbpcs_prj_demand"
            ),
            MagicMock(
                cdb_object_id="object_id_8", level=0, table_name="cdbpcs_prj_alloc"
            ),
            MagicMock(
                cdb_object_id="object_id_9",
                level=0,
                table_name="Resource Pool Assignment",
            ),
            MagicMock(
                cdb_object_id="object_id_10", level=2, table_name="cdbpcs_prj_alloc"
            ),
            MagicMock(
                cdb_object_id="object_id_11", level=2, table_name="cdbpcs_prj_demand"
            ),
        ]

        data_model.DataModel._get_data(model, "resolved", "ts_records", request)
        self.assertEqual(model.get_row.call_count, 11)
        model.get_row.assert_has_calls(
            [
                call(0, "object_id_1", 1, "object_id_1", None),
                call(1, "object_id_2", 2, "object_id_1", "object_id_1"),
                call(2, "object_id_3", 3, "object_id_1", None),
                call(3, "object_id_4", 4, "object_id_1", "object_id_3"),
                call(4, "object_id_5", 5, "object_id_1", "object_id_3"),
                call(5, "object_id_6", 6, "object_id_1", None),
                call(6, "object_id_7", 7, "object_id_7", None),
                call(7, "object_id_8", 8, "object_id_8", None),
                call(8, "object_id_9", 9, "object_id_9", None),
                call(9, "object_id_10", 10, "object_id_9", "object_id_9"),
                call(10, "object_id_11", 11, "object_id_9", "object_id_9"),
            ]
        )

    @patch.object(data_model, "get_restlinks_in_batch")
    @patch.object(data_model.DataModel, "_get_record_tuples", autospec=True)
    def test__get_baseline_data(self, _get_record_tuples, get_restlinks_in_batch):
        _get_record_tuples.return_value = [("t", "r")]
        get_restlinks_in_batch.return_value = {"bl_oid1": "link"}
        relevant_baselines = {"oid1": ("cdbpcs_task", "bl_oid1")}
        request = "request"
        model = self._get_model()
        self.assertEqual(
            model._get_baseline_data(relevant_baselines, request),
            (_get_record_tuples.return_value, {"oid1": "link"}),
        )

        _get_record_tuples.assert_called_once_with(model, [("bl_oid1", "cdbpcs_task")])
        get_restlinks_in_batch.assert_called_once_with(
            _get_record_tuples.return_value, request
        )

    def test__get_full_data_first_page_not_iter(self):
        "fails if record_tuples is not iterable"
        model = self._get_model()
        model.first_page_size = "pagesize"
        with self.assertRaises(TypeError) as error:
            model._get_full_data_first_page(None, None, None, None, None)
        self.assertEqual("'NoneType' object is not iterable", str(error.exception))

    def test__get_full_data_first_page_no_oid(self):
        "fails if any record is not a PCS_RECORD"
        model = self._get_model()
        model.first_page_size = "pagesize"
        with self.assertRaises(AttributeError) as error:
            model._get_full_data_first_page(None, [(1, None)], [], {}, None)
        self.assertEqual(
            "'tuple' object has no attribute 'record'", str(error.exception)
        )

    @patch.object(data_model.DataModel, "get_full_data", autospec=True)
    @patch.object(data_model.util, "get_first_nodes", return_value=["a", "c"])
    def test__get_full_data_first_page(self, get_first_nodes, get_full_data):
        "returns full JSON data of first page"
        records = [
            data_model.util.PCS_RECORD("relation1", MagicMock(cdb_object_id="a")),
            data_model.util.PCS_RECORD("relation2", MagicMock(cdb_object_id="b")),
            data_model.util.PCS_RECORD("relation3", MagicMock(cdb_object_id="c")),
        ]
        bl_records = [
            data_model.util.PCS_RECORD("relation1", MagicMock(cdb_object_id="d"))
        ]
        relevant_baselines = {"a": ("tbl1", "d")}
        model = self._get_model()
        model.first_page_size = "pagesize"
        self.assertEqual(
            model._get_full_data_first_page(
                "nodes", records, bl_records, relevant_baselines, "request"
            ),
            get_full_data.return_value,
        )
        get_first_nodes.assert_called_once_with("nodes", "pagesize")
        get_full_data.assert_called_once_with(
            model,
            get_first_nodes.return_value,
            None,
            [records[0], records[2]],
            [bl_records[0]],
            "request",
        )

    @patch.object(data_model, "get_rest_objects", autospec=True)
    @patch.object(data_model.DataModel, "add_status_info", autospec=True)
    @patch.object(data_model.DataModel, "_get_record_tuples", autospec=True)
    def test__get_rest_objects_no_plugin(
        self, _get_record_tuples, add_status_info, get_rest_objects
    ):
        "fails if plugin is missing"
        model = self._get_model()
        model.plugins = {"foo": "plugin"}
        with self.assertRaises(KeyError) as error:
            model._get_rest_objects(None, [("bar", "record")], None)
        self.assertEqual("'bar'", str(error.exception))
        _get_record_tuples.assert_has_calls([])
        add_status_info.assert_has_calls([])
        get_rest_objects.assert_has_calls([])

    @patch.object(data_model, "get_rest_objects", autospec=True)
    @patch.object(data_model.DataModel, "add_status_info", autospec=True)
    @patch.object(data_model.DataModel, "_get_record_tuples", autospec=True)
    def test__get_rest_objects_not_iter(
        self, _get_record_tuples, add_status_info, get_rest_objects
    ):
        "fails if record_tuples is not None and not iterable"
        model = self._get_model()
        model.plugins = None
        with self.assertRaises(TypeError) as error:
            model._get_rest_objects(None, 1, None)
        self.assertEqual("'int' object is not iterable", str(error.exception))
        _get_record_tuples.assert_has_calls([])
        add_status_info.assert_has_calls([])
        get_rest_objects.assert_has_calls([])

    @patch.object(data_model, "get_rest_objects", autospec=True)
    @patch.object(data_model.DataModel, "add_status_info", autospec=True)
    @patch.object(data_model.DataModel, "_get_record_tuples", autospec=True)
    def test__get_rest_objects_no_unpack(
        self, _get_record_tuples, add_status_info, get_rest_objects
    ):
        "fails if any record tuple does not contain exactly 2 values"
        model = self._get_model()
        model.plugins = None
        with self.assertRaises(ValueError) as error:
            model._get_rest_objects(None, [(1,)], None)
        self.assertEqual(
            "not enough values to unpack (expected 2, got 1)", str(error.exception)
        )
        with self.assertRaises(ValueError) as error:
            model._get_rest_objects(None, [(1, 2, 3)], None)
        self.assertEqual("too many values to unpack (expected 2)", str(error.exception))
        _get_record_tuples.assert_has_calls([])
        add_status_info.assert_has_calls([])
        get_rest_objects.assert_has_calls([])

    @patch.object(data_model, "get_rest_objects", autospec=True)
    def test__get_rest_objects_load_records(self, get_rest_objects):
        "loads records first if not given"
        model = MagicMock(
            spec=data_model.DataModel,
            plugins={"relation": "plugin"},
            column_group="CG",
        )
        self.assertEqual(
            data_model.DataModel._get_rest_objects(
                model,
                "oids",
                None,
                "request",
            ),
            {
                "objects": get_rest_objects.return_value,
                "status": {},
                "projectNames": model._get_project_names.return_value,
            },
        )
        model._get_record_tuples.assert_called_once_with("oids")
        get_rest_objects.assert_called_once_with(
            {"relation": "plugin"},
            "CG",
            model._get_record_tuples.return_value,
            "request",
        )
        model._get_project_names.assert_called_once_with(set())

    @patch.object(data_model, "get_rest_objects", autospec=True)
    def test__get_rest_objects(self, get_rest_objects):
        "uses pre-loaded records"
        model = MagicMock(
            spec=data_model.DataModel,
            plugins={"relation": "plugin"},
            column_group="CG",
        )
        record = MagicMock()
        real_dict = {
            "cdb_project_id": "pid",
            "cdb_object_id": "oid",
            "ce_baseline_id": "",
        }
        record.get.side_effect = real_dict.get
        records = [("relation", record)]
        self.assertEqual(
            data_model.DataModel._get_rest_objects(
                model,
                "oids",
                records,
                "request",
            ),
            {
                "objects": get_rest_objects.return_value,
                "status": {},
                "projectNames": model._get_project_names.return_value,
            },
        )
        model._get_record_tuples.assert_not_called()
        model.add_status_info.assert_called_once_with({}, "plugin", record)
        get_rest_objects.assert_called_once_with(
            model.plugins,
            "CG",
            records,
            "request",
        )
        model._get_project_names.assert_called_once_with(set([("pid", "")]))
        # Note: Mock of record.get has also several calls related to checks and
        # actions of the retrieved values like 'is not null?' or adding to
        # hashable data structures. We skip checking them here and only check
        # directly for what we expect record.get has been called with.
        self.assertListEqual(
            [call("cdb_project_id", None), call("ce_baseline_id", "")],
            record.get.call_args_list,
        )

    @patch.object(data_model, "StatusInfo", autospec=True)
    @testcase.without_error_logging
    def test_add_status_info_plugin_invalid(self, StatusInfo):
        "fails if plugin is invalid"
        model = self._get_model()
        plugin = MagicMock()
        del plugin.GetObjectKind
        # plugin is missing attribute GetObjectKind
        with self.assertRaises(RuntimeError):
            model.add_status_info(None, plugin, "record")
        # plugin.GetObjectKind not callable
        plugin = MagicMock(GetObjectKind="foo")
        with self.assertRaises(RuntimeError):
            model.add_status_info(None, plugin, "record")
        StatusInfo.assert_not_called()

    @patch.object(data_model, "StatusInfo", autospec=True, side_effect=ValueError)
    @patch.object(data_model.logging, "exception", autospec=True)
    def test_add_status_info_kind_none(self, log_exception, StatusInfo):
        "None if plugin cannot determine OLC"
        model = self._get_model()
        plugin = MagicMock(status_attr="status")
        plugin.GetObjectKind.return_value = None
        record = MagicMock(status=10)
        status_info = data_model.StatusInfoDict()
        self.assertIsNone(model.add_status_info(status_info, plugin, record))
        self.assertDictEqual(status_info, {})
        log_exception.assert_called_once_with(f"invalid status: None, {record}")
        plugin.GetObjectKind.assert_called_once_with(record)
        StatusInfo.assert_called_once_with(None, 10)

    @patch.object(data_model, "StatusInfo", autospec=True, return_value=None)
    @patch.object(data_model.logging, "exception", autospec=True)
    def test_add_status_info_no_info(self, log_exception, StatusInfo):
        "None if StatusInfo is None"
        model = self._get_model()
        plugin = MagicMock(status_attr="status")
        plugin.GetObjectKind.return_value = None
        record = MagicMock(status=10)
        status_info = data_model.StatusInfoDict()
        self.assertIsNone(model.add_status_info(status_info, plugin, record))
        self.assertDictEqual(status_info, {})
        self.assertEqual(log_exception.call_count, 0)
        plugin.GetObjectKind.assert_called_once_with(record)
        StatusInfo.assert_called_once_with(None, 10)

    @patch.object(data_model, "StatusInfo", autospec=True, side_effect=TypeError)
    @patch.object(data_model.logging, "exception", autospec=True)
    def test_add_status_info_status_no_int(self, log_exception, StatusInfo):
        "None if status is not an int"
        model = self._get_model()
        plugin = MagicMock(status_attr="status")
        plugin.GetObjectKind.return_value = ""
        record = MagicMock(status="10")
        status_info = data_model.StatusInfoDict()
        self.assertIsNone(model.add_status_info(status_info, plugin, record))
        self.assertDictEqual(status_info, {})
        log_exception.assert_called_once_with(
            f"invalid status: {plugin.GetObjectKind.return_value}, {record}"
        )
        plugin.GetObjectKind.assert_called_once_with(record)
        StatusInfo.assert_called_once_with("", "10")

    @patch.object(data_model, "StatusInfo", autospec=True)
    def test_add_status_info_unknown_status(self, StatusInfo):
        "None if record is missing attribute 'status'"
        model = self._get_model()
        plugin = MagicMock(status_attr="status")
        plugin.GetObjectKind.return_value = None
        status_info = data_model.StatusInfoDict()
        self.assertIsNone(model.add_status_info(status_info, plugin, "record"))
        self.assertDictEqual(status_info, {})
        plugin.GetObjectKind.assert_called_once_with("record")
        StatusInfo.assert_not_called()

    @patch.object(data_model, "StatusInfo", autospec=True)
    @patch.object(data_model.logging, "exception", autospec=True)
    def test_add_status_info(self, log_exception, StatusInfo):
        "returns status info"
        model = self._get_model()
        plugin = MagicMock(status_attr="status")
        plugin.GetObjectKind.return_value = "foo"
        record = MagicMock()
        status_info = data_model.StatusInfoDict()
        self.assertIsNone(model.add_status_info(status_info, plugin, record))
        self.assertDictEqual(
            status_info,
            {
                "foo": {
                    record.status: {
                        "label": StatusInfo.return_value.getLabel.return_value,
                        "color": StatusInfo.return_value.getCSSColor.return_value,
                    },
                },
            },
        )

        log_exception.assert_has_calls([])
        plugin.GetObjectKind.assert_called_once_with(record)
        StatusInfo.assert_called_once_with(
            plugin.GetObjectKind.return_value,
            record.status,
        )

    @patch.object(
        data_model, "get_rest_key", autospec=True, side_effect=["restkey1", "restkey2"]
    )
    @patch.object(data_model, "get_sql_condition", autospec=True)
    @patch.object(
        data_model.sqlapi,
        "RecordSet2",
        autospec=True,
        return_value=[
            MagicMock(cdb_project_id="pid1", ce_baseline_id="bid1", project_name="one"),
            MagicMock(cdb_project_id="pid2", ce_baseline_id="bid2", project_name="two"),
        ],
    )
    def test__get_project_names(self, RecordSet2, get_sql_condition, get_rest_key):
        model = MagicMock(spec=data_model.DataModel)
        self.assertEqual(
            data_model.DataModel._get_project_names(
                model, set([("pid1", "bid1"), ("pid2", "bid2"), None])
            ),
            {"restkey1": "one", "restkey2": "two"},
        )
        RecordSet2.assert_called_once_with(
            "cdbpcs_project",
            get_sql_condition.return_value,
            access="read",
        )
        get_sql_condition.assert_called_once()
        args = get_sql_condition.mock_calls[0][1]
        args[2].sort()
        self.assertEqual(
            args,
            (
                "cdbpcs_project",
                ["cdb_project_id", "ce_baseline_id"],
                [("pid1", "bid1"), ("pid2", "bid2")],
            ),
        )
        get_rest_key.assert_has_calls(
            [
                call(RecordSet2.return_value[0], ["cdb_project_id", "ce_baseline_id"]),
                call(RecordSet2.return_value[1], ["cdb_project_id", "ce_baseline_id"]),
            ]
        )

    def test__get_subjects_objs_no_iter(self):
        "fails if rest_objs is truthy but not iterable"
        model = self._get_model()
        with self.assertRaises(TypeError) as error:
            model._get_subjects(1)
        self.assertEqual("'int' object is not iterable", str(error.exception))

    def test__get_subjects_objs_empty(self):
        "returns empty dict if rest_objs is falsy"
        model = self._get_model()
        self.assertEqual(model._get_subjects(None), {})

    @patch.object(data_model, "SUBJECT_LINK_PATTERNS", {"1": {"link": "L"}})
    @patch.object(data_model, "CADDOK", ISOLANG="XX")
    def test__get_subjects(self, CADDOK):
        "returns subject names"
        objs = [
            {"subject_id": "foo", "subject_type": "1"},
            {"subject_id": "foo", "subject_type": "1"},
            {"subject_id": "bar", "subject_type": "1"},
            {"subject_id": "baz", "subject_type": "2"},
            {},
        ]
        model = self._get_model()
        with patch.object(data_model.sqlapi, "RecordSet2", autospec=True) as RecordSet2:
            RecordSet2.return_value = [
                MagicMock(subject_id="foo", subject_type="1", subject_name="a"),
                MagicMock(subject_id="bar", subject_type="1", subject_name="b"),
                MagicMock(subject_id="baz", subject_type="2", subject_name="c"),
            ]
            self.assertEqual(
                model._get_subjects(objs),
                {
                    "1": {
                        "foo": {"title": "a", "link": "L"},
                        "bar": {"title": "b", "link": "L"},
                    },
                    "2": {
                        "baz": {"title": "c"},
                    },
                },
            )
            RecordSet2.assert_called_once()
            # query condition is built from an unordered set
            args, kwargs = RecordSet2.call_args
            self.assertEqual(args, tuple())
            self.assertEqual(list(kwargs), ["sql"])
            expected = [
                "(subject_id = 'foo' AND subject_type = '1')",
                "(subject_id = 'bar' AND subject_type = '1')",
                "(subject_id = 'baz' AND subject_type = '2')",
                "(subject_id = '' AND subject_type = '')",
            ]
            conditions = [
                condition.strip()
                for condition in kwargs["sql"].split("WHERE ")[-1].split(" OR ")
            ]
            self.assertEqual(len(conditions), len(expected))
            for x in expected:
                self.assertTrue(
                    x in conditions,
                    "missing condition: f'{x}'\nconditions: {conditions}",
                )

    @patch.object(data_model, "get_rest_objects", autospec=True)
    @patch("cs.pcs.timeschedule.web.models.elements_model.ElementsModel")
    @patch.object(data_model.DataModel, "_get_subjects", autospec=True)
    @patch.object(TimeSchedule, "_schedule_resolve_relships", autospec=True)
    @patch.object(data_model.DataModel, "_get_rest_objects", autospec=True)
    @patch.object(data_model, "get_pcs_oids", autospec=True)
    def test_get_full_data_resolve(
        self,
        get_pcs_oids,
        _get_rest_objects,
        resolve_relships,
        _get_subjects,
        mock_EM,
        get_rest_objects,
    ):
        "returns full data after getting table names"
        _get_rest_objects.return_value = {"objects": "O", "status": "S"}
        mock_EM.return_value = MagicMock()
        mock_EM.get_schedule_elements = MagicMock(return_value="foo")
        mock_EM.get_schedule_project_ids = MagicMock(return_value="bar")
        get_rest_objects.return_value = []
        model = self._get_model()
        model.plugins = {}
        model.context_object_id = "context_object_id"
        self.assertDictEqual(
            model.get_full_data(
                "oids",
                [],
                None,
                None,
                "request",
            ),
            {
                "auto_update_time": {
                    0: "Als Prognose übernehmen",
                    1: "Als Soll übernehmen",
                    2: "Nicht übernehmen",
                },
                "relships": resolve_relships.return_value,
                "objects": "O",
                "status": "S",
                "subjects": _get_subjects.return_value,
                "bl_objects": [],
                "elements": "foo",
                "project_ids_by_elements": "bar",
            },
        )
        get_pcs_oids.assert_called_once_with("oids")
        _get_rest_objects.assert_called_once_with(
            model,
            get_pcs_oids.return_value,
            None,
            "request",
        )
        _get_subjects.assert_called_once_with(model, "O")
        get_rest_objects.assert_called_once_with(
            model.plugins, "gantt", None, "request"
        )

    @patch.object(data_model, "get_rest_objects", autospec=True)
    @patch("cs.pcs.timeschedule.web.models.elements_model.ElementsModel")
    @patch.object(data_model.DataModel, "_get_subjects", autospec=True)
    @patch.object(TimeSchedule, "_schedule_resolve_relships", autospec=True)
    @patch.object(data_model.DataModel, "_get_rest_objects", autospec=True)
    @patch.object(data_model, "get_pcs_oids", autospec=True)
    def test_get_full_data(
        self,
        get_pcs_oids,
        _get_rest_objects,
        resolve_relships,
        _get_subjects,
        mock_EM,
        get_rest_objects,
    ):
        "returns full data without getting table names"
        _get_rest_objects.return_value = {"objects": "O", "status": "S"}
        mock_EM.return_value = MagicMock()
        mock_EM.get_schedule_elements = MagicMock(return_value="foo")
        mock_EM.get_schedule_project_ids = MagicMock(return_value="bar")
        get_rest_objects.return_value = []
        model = self._get_model()
        model.plugins = {}
        model.context_object_id = "context_object_id"
        self.assertDictEqual(
            model.get_full_data(
                "oids",
                "resolved_oids",
                None,
                None,
                "request",
            ),
            {
                "objects": "O",
                "status": "S",
                "subjects": _get_subjects.return_value,
                "bl_objects": [],
                "elements": "foo",
                "project_ids_by_elements": "bar",
                "relships": resolve_relships.return_value,
                "auto_update_time": {
                    0: "Als Prognose übernehmen",
                    1: "Als Soll übernehmen",
                    2: "Nicht übernehmen",
                },
            },
        )
        get_pcs_oids.assert_has_calls([])
        _get_rest_objects.assert_called_once_with(
            model,
            "resolved_oids",
            None,
            "request",
        )
        _get_subjects.assert_called_once_with(model, "O")
        get_rest_objects.assert_called_once_with(
            model.plugins, "gantt", None, "request"
        )

    @testcase.without_error_logging
    def test__get_value_from_payload_payload_not_dict(self):
        "raises if payload is not a dict"
        payload = []
        key = ""
        model = self._get_model()
        with self.assertRaises(HTTPBadRequest):
            model._get_value_from_payload(payload, key)

    @testcase.without_error_logging
    def test__get_value_from_payload_key_not_string(self):
        "raises errord if key is not a string"
        payload = {}
        key = 5
        model = self._get_model()
        with self.assertRaises(HTTPBadRequest):
            model._get_value_from_payload(payload, key)

    @testcase.without_error_logging
    def test__get_value_from_payload_key_not_in_payload(self):
        "raises HTTPBadRequest if key not in payload"
        payload = {"bar": "baz"}
        key = "foo"
        model = self._get_model()
        with self.assertRaises(HTTPBadRequest):
            model._get_value_from_payload(payload, key)

    @testcase.without_error_logging
    def test__get_value_from_payload(self):
        "returns value stored under key in payload"
        payload = {"foo": "baz"}
        key = "foo"
        model = self._get_model()
        self.assertEqual(model._get_value_from_payload(payload, key), "baz")


@pytest.mark.integration
class DataModelIntegration(testcase.RollbackTestCase):
    def test__get_pinned_oids(self):
        from cs.pcs.projects import Project
        from cs.pcs.projects.tasks import Task

        project = Project.Create(cdb_project_id="integrationtest", ce_baseline_id="")
        task = Task.Create(
            cdb_project_id="integrationtest", task_id="foo", ce_baseline_id=""
        )
        schedule = TimeSchedule.Create(name="integration test")
        schedule.insertObjects([task, project])
        model = data_model.DataModel(schedule.cdb_object_id)
        self.assertEqual(
            model._get_pinned_oids(),
            [
                data_model.PCS_OID(task.cdb_object_id, "cdbpcs_task"),
                data_model.PCS_OID(project.cdb_object_id, "cdbpcs_project"),
            ],
        )

    @patch("cs.pcs.timeschedule.web.models.data_model.CDBClassDef")
    def test__get_plugins(self, CDBClassDef):
        model = MagicMock(
            spec=data_model.DataModel,
            context_object="foo",
        )
        a = MagicMock()
        b = MagicMock()
        model.plugins = {"a": a, "b": b}

        self.assertEqual(
            data_model.DataModel._get_plugins(model, "req"),
            [
                {
                    "classname": a.classname,
                    "allow_pinning": a.allow_pinning,
                    "icon": CDBClassDef.return_value.getIconId.return_value,
                    "title": CDBClassDef.return_value.getTitle.return_value,
                    "catalog": a.GetCatalogConfig.return_value,
                },
                {
                    "classname": b.classname,
                    "allow_pinning": b.allow_pinning,
                    "icon": CDBClassDef.return_value.getIconId.return_value,
                    "title": CDBClassDef.return_value.getTitle.return_value,
                    "catalog": b.GetCatalogConfig.return_value,
                },
            ],
        )

        a.GetCatalogConfig.assert_called_once_with("foo", "req")
        b.GetCatalogConfig.assert_called_once_with("foo", "req")

        self.assertEqual(
            CDBClassDef.mock_calls,
            [
                call(a.classname),
                call().getIconId(),
                call().getTitle(),
                call(b.classname),
                call().getIconId(),
                call().getTitle(),
            ],
        )
        self.assertEqual(CDBClassDef.call_count, 2)


if __name__ == "__main__":
    unittest.main()
