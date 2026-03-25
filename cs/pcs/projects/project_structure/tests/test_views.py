#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

__revision__ = "$Id$"


import unittest

import mock
import pytest

from cs.pcs.projects.project_structure import views


@pytest.mark.unit
class View(unittest.TestCase):
    @mock.patch.object(views, "_get_dummy_request")
    def test___init___defaults(self, _get_dummy_request):
        params = {"subprojects": "0"}
        req = mock.Mock()
        req.params = params
        x = mock.MagicMock(spec=views.View)
        self.assertIsNone(views.View.__init__(x, "root", req))
        self.assertEqual(x.root_oid, "root")
        self.assertEqual(x.subprojects, False)
        self.assertEqual(x.request, req)

    def test___init__(self):
        params = {"subprojects": "1"}
        req = mock.Mock()
        req.params = params
        x = mock.MagicMock(spec=views.View)
        self.assertIsNone(views.View.__init__(x, "root", req))
        self.assertEqual(x.root_oid, "root")
        self.assertEqual(x.subprojects, True)
        self.assertEqual(x.request, req)

    def test_resolve(self):
        x = mock.MagicMock(spec=views.View)
        self.assertEqual(
            views.View.resolve(x, 5),
            x.format_response.return_value,
        )
        x.resolve_structure.assert_called_once_with()
        x.get_full_data.assert_called_once_with(5)
        x.format_response.assert_called_once_with()


@pytest.mark.unit
class TreeView(unittest.TestCase):
    def test_view_name(self):
        self.assertEqual(views.TreeView.view_name, "project_structure")

    def test_get_row_and_node(self):
        level = mock.MagicMock()
        self.assertEqual(
            views.TreeView.get_row_and_node(None, level, "/a/b/c", "foo", None),
            (
                None,
                {
                    "id": level.cdb_object_id,
                    "level": level.level,
                    "rest_key": "c",
                    "system:navigation_id": "foo",
                },
            ),
        )

    def test_get_tree_object_no_rest_obj(self):
        self.assertEqual(
            views.TreeView.get_tree_object(None),
            {},
        )

    def test_get_tree_object_no_status(self):
        rest_object = {
            "@id": "ID",
            "system:classname": "Classname",
            "system:navigation_id": "navigation",
            "system:description": "Description",
            "system:icon_link": "Icon",
            "mapped_status_name": "Status Name",
            "foo": "bar",
            "status_code": 0,
            "is_milestone": 0,
            "msp_active": 0,
        }
        expected = {
            "@id": "ID",
            "system:classname": "Classname",
            "system:navigation_id": "navigation",
            "label": "Description",
            "icons": [
                {"url": "Icon"},
                None,
            ],
            "status_code": 0,
        }

        self.assertDictEqual(views.TreeView.get_tree_object(rest_object), expected)

        rest_object["is_milestone"] = 1
        expected["is_milestone"] = 1
        self.assertDictEqual(views.TreeView.get_tree_object(rest_object), expected)

    def test_get_tree_object_no_status_name(self):
        rest_object = {
            "@id": "ID",
            "system:classname": "Classname",
            "system:navigation_id": "navigation",
            "system:description": "Description",
            "system:icon_link": "Icon",
            "status_icon": "Status Icon",
            "foo": "bar",
            "status_code": 0,
            "is_milestone": 1,
            "msp_active": 0,
        }
        self.assertDictEqual(
            views.TreeView.get_tree_object(rest_object),
            {
                "@id": "ID",
                "system:classname": "Classname",
                "system:navigation_id": "navigation",
                "label": "Description",
                "icons": [
                    {"url": "Icon"},
                    "Status Icon",
                ],
                "status_code": 0,
                "is_milestone": 1,
            },
        )

    def test_get_tree_object(self):
        rest_object = {
            "@id": "ID",
            "system:classname": "Classname",
            "system:navigation_id": "navigation",
            "system:description": "Description",
            "system:icon_link": "Icon",
            "status_icon": "Status Icon",
            "mapped_status_name": "Status Name",
            "foo": "bar",
            "status_code": 0,
            "is_milestone": 0,
            "msp_active": 0,
        }
        self.assertDictEqual(
            views.TreeView.get_tree_object(rest_object),
            {
                "@id": "ID",
                "system:classname": "Classname",
                "system:navigation_id": "navigation",
                "label": "Description",
                "icons": [
                    {"url": "Icon"},
                    "Status Icon",
                ],
                "status_code": 0,
            },
        )

    def test_get_adjacency_list_no_nodes(self):
        self.assertEqual(
            views.TreeView.get_adjacency_list(None),
            {},
        )

    def test_get_adjacency_list(self):
        self.assertEqual(
            views.TreeView.get_adjacency_list(
                [
                    {"level": 0, "rest_key": "A"},
                    {"level": 1, "rest_key": "A.1"},
                    {"level": 2, "rest_key": "A.1.1"},
                    {"level": 2, "rest_key": "A.1.2"},
                    {"level": 1, "rest_key": "A.2"},
                    {"level": 2, "rest_key": "A.2.1"},
                    {"level": 0, "rest_key": "B"},
                ]
            ),
            {
                "A": ["A.1", "A.2"],
                "A.1": ["A.1.1", "A.1.2"],
                "A.2": ["A.2.1"],
            },
        )

    @mock.patch.object(
        views.util, "resolve_project_structure", return_value=(1, 2, 3, 4)
    )
    def test_resolve_structure(self, resolve_project_structure):
        x = mock.MagicMock(
            spec=views.TreeView,
            root_oid="foo",
            subprojects="bar",
            request="baz",
        )
        self.assertIsNone(views.TreeView.resolve_structure(x))
        self.assertEqual(x.records, 1)
        self.assertEqual(x.rows, 2)
        self.assertEqual(x.flat_nodes, 3)
        self.assertEqual(x.levels, 4)
        resolve_project_structure.assert_called_once_with(
            x.root_oid,
            x.subprojects,
            x.get_row_and_node,
            x.request,
        )

    @mock.patch.object(views.util, "get_status")
    @mock.patch.object(views.util, "get_object_icon")
    @mock.patch.object(views.util, "get_object_description")
    def test_get_additional_data_task(
        self, get_object_description, get_object_icon, get_status
    ):
        record = mock.MagicMock(
            table_name="cdbpcs_task", is_milestone=1, status_code=0, msp_active=0
        )
        self.assertEqual(
            views.TreeView.get_additional_data(record, "req"),
            {
                "system:description": get_object_description.return_value,
                "system:icon_link": get_object_icon.return_value,
                "status_icon": get_status.return_value,
                "status_code": record.record["status_code"],
                "is_milestone": record.record.get("is_milestone"),
                "msp_active": record.record.get("msp_active"),
            },
        )
        get_object_description.assert_called_once_with(
            "{position} {task_name}", record.record, "position", "task_name"
        )
        get_object_icon.assert_called_once_with(
            "cdbpcs_task_object", record.record, "is_group", "milestone"
        )
        get_status.assert_called_once_with(
            record.record["cdb_objektart"], record.record["status"]
        )

    @mock.patch.object(views.util, "get_status")
    @mock.patch.object(views.util, "get_object_icon")
    @mock.patch.object(views.util, "get_object_description")
    def test_get_additional_data_proj(
        self, get_object_description, get_object_icon, get_status
    ):
        record = mock.MagicMock(
            table_name="cdbpcs_project", is_milestone=0, status_code=0, msp_active=0
        )
        self.assertEqual(
            views.TreeView.get_additional_data(record, "req"),
            {
                "system:description": get_object_description.return_value,
                "system:icon_link": get_object_icon.return_value,
                "status_icon": get_status.return_value,
                "status_code": record.record["status_code"],
                "is_milestone": record.record.get("is_milestone"),
                "msp_active": record.record.get("msp_active"),
            },
        )
        get_object_description.assert_called_once_with(
            "{cdb_project_id} {project_name}",
            record.record,
            "cdb_project_id",
            "project_name",
        )
        get_object_icon.assert_called_once_with(
            "cdbpcs_project_obj", record.record, "parent_project", "template"
        )
        get_status.assert_called_once_with(
            record.record["cdb_objektart"],
            record.record["status"],
        )

    def test__get_first_nodes_return_all_nodes(self):
        """
        If requested amount of nodes is <= 0 or greater than existing nodes
        return all of them
        """
        tview = mock.MagicMock(
            spec=views.TreeView,
            adjacency_list={
                "0": [],
            },
            flat_nodes=[
                {"rest_key": "0", "id": 10},
            ],
        )
        expected_result = (tview.flat_nodes, [])

        result_1 = views.TreeView._get_first_nodes(tview, first=10)
        result_2 = views.TreeView._get_first_nodes(tview, first=0)
        result_3 = views.TreeView._get_first_nodes(tview, first=-10)

        self.assertEqual(result_1, expected_result)
        self.assertEqual(result_2, expected_result)
        self.assertEqual(result_3, expected_result)

    def _traverse_flat_nodes_BFS(self, start_key, max_length, encountered, expected):
        tview = mock.MagicMock(
            spec=views.TreeView,
            adjacency_list={
                "0": ["1", "2", "5"],
                "1": [],
                "2": ["3", "4"],
                "3": [],
                "4": [],
            },
        )

        result = views.TreeView._traverse_flat_nodes_BFS(
            tview, start_key, max_length, encountered
        )

        self.assertEqual(result, expected)

    def test__traverse_flat_nodes_BFS_five_from_root(self):
        """get first 5 nodes with BFS starting from root"""
        self._traverse_flat_nodes_BFS("0", 5, [], ["0", "1", "2", "5", "3"])

    def test__traverse_flat_nodes_BFS_five_from_2(self):
        """get first 5 nodes with BFS starting from 2, which yields only three nodes"""
        self._traverse_flat_nodes_BFS("2", 5, [], ["2", "3", "4"])

    def test__traverse_flat_nodes_BFS_five_from_1(self):
        """get first 5 nodes with BFS starting from 1, which yields only one node"""
        self._traverse_flat_nodes_BFS("1", 5, [], ["1"])

    def test__traverse_flat_nodes_BFS_five_from_root_with_skipping_some(self):
        """get first 5 nodes with BFS starting from root, but skip 2 and 3"""
        self._traverse_flat_nodes_BFS("0", 5, ["2", "3"], ["0", "1", "5", "4"])

    def test__traverse_flat_nodes_BFS_five_from_root_with_skipping_all(self):
        """get first 5 nodes with BFS starting from root, but skip 2 and 3"""
        self._traverse_flat_nodes_BFS("0", 5, ["0", "1", "2", "3", "4", "5"], [])

    def test__traverse_flat_nodes_BFS_empty_query(self):
        """start with empty query, resulting in empty result"""
        self._traverse_flat_nodes_BFS(None, 5, [], [])

    def test__traverse_flat_nodes_BFS_max_length_zero(self):
        """collect up to zero element, resulting in empty result"""
        self._traverse_flat_nodes_BFS("0", 0, [], [])

    def __traverse_flat_nodes(
        self,
        start_index,
        direction,
        max_length,
        selected_rest_key,
        expanded_rest_keys,
        expected,
    ):
        tview = mock.MagicMock(
            spec=views.TreeView,
            flat_nodes=[
                {"rest_key": "0", "id": 10},
                {"rest_key": "1", "id": 11},
                {"rest_key": "2", "id": 12},
                {"rest_key": "3", "id": 13},
                {"rest_key": "4", "id": 14},
            ],
            child_to_parent={"1": "0", "2": "1", "3": "0", "4": "3"},
        )

        result = views.TreeView._traverse_flat_nodes(
            tview,
            start_index,
            direction,
            max_length,
            selected_rest_key,
            expanded_rest_keys,
        )

        self.assertEqual(result, expected)

    def test___traverse_flat_nodes__start_index_negative(self):
        """no keys are gathered if start_index is negative"""
        self.__traverse_flat_nodes(-3, 1, 1, None, [], [])

    def test___traverse_flat_nodes__start_index_outside_flat_nodes(self):
        """no keys are gathered if start_index is greater than flat_nodes size (5)"""
        self.__traverse_flat_nodes(6, 1, 1, None, [], [])

    def test___traverse_flat_nodes__max_length_zero_or_negative(self):
        """no keys are gathered if max_length is zero or negative"""
        # max_length = zero
        self.__traverse_flat_nodes(0, 1, 0, None, [], [])
        # max_length = negative
        self.__traverse_flat_nodes(0, 1, -1, None, [], [])

    def test___traverse_flat_nodes__down_from_selected_1(self):
        """going down from selected key (1) with expanded nodes [0, 1]"""
        self.__traverse_flat_nodes(1, 1, 5, "1", ["0", "1"], ["1", "2", "3"])

    def test___traverse_flat_nodes__down_from_selected_2(self):
        """going down from selected key (1) with expanded nodes [0]"""
        self.__traverse_flat_nodes(1, 1, 5, "1", ["0"], ["1", "3"])

    def test___traverse_flat_nodes__up_from_selected_1(self):
        """going down from selected key (3) with expanded nodes [0, 1]"""
        self.__traverse_flat_nodes(3, -1, 5, "3", ["0", "1"], ["3", "2", "1", "0"])

    def test___traverse_flat_nodes__up_from_selected_2(self):
        """going down from selected key (3) with expanded nodes [0]"""
        self.__traverse_flat_nodes(3, -1, 5, "3", ["0"], ["3", "1", "0"])

    @mock.patch.object(views, "auth", persno="foo_user")
    @mock.patch.object(views.sqlapi, "RecordSet2")
    def test__get_and_parse_snapshot_no_db_record(self, RecordSet2, a_user):
        """
        return default values if no UI-Setting is stored
        """
        tview = mock.MagicMock(
            spec=views.TreeView,
            flat_nodes=[
                {"rest_key": "0", "id": 10},
            ],
        )

        RecordSet2.return_value = []

        result = views.TreeView._get_and_parse_snapshot(tview)

        RecordSet2.assert_called_once_with(
            sql="""SELECT * from csweb_ui_settings
                WHERE persno = 'foo_user'
                AND component = '0-cs-pcs-projects-web-StructureTree'
                AND property = 'snapshot'
            """
        )

        self.assertEqual(result, (None, 0, []))

    @mock.patch.object(views, "auth", persno="foo_user")
    @mock.patch.object(views.sqlapi, "RecordSet2")
    def test__get_and_parse_snapshot_db_record(self, RecordSet2, a_user):
        """
        get selected node's rest_key, index and list of expanded nodes
        """
        tview = mock.MagicMock(
            spec=views.TreeView,
            flat_nodes=[
                {"rest_key": "0", "id": 10},
            ],
        )

        RecordSet2.side_effect = [
            [{"json_value": ""}],  # first db entry is empty
            [  # second db entry has values
                {"text": '{"selectedRestKey": "0",'},
                {"text": '"0": {"expanded": true}}'},
            ],
        ]

        result = views.TreeView._get_and_parse_snapshot(tview)

        RecordSet2.assert_has_calls(
            [
                mock.call(
                    sql="""SELECT * from csweb_ui_settings
                WHERE persno = 'foo_user'
                AND component = '0-cs-pcs-projects-web-StructureTree'
                AND property = 'snapshot'
            """
                ),
                mock.call(
                    sql="""SELECT * from csweb_ui_settings_txt
                WHERE persno = 'foo_user'
                AND component = '0-cs-pcs-projects-web-StructureTree'
                AND property = 'snapshot'
            """
                ),
            ]
        )

        self.assertEqual(result, ("0", 0, ["0"]))

    def test__get_first_nodes_only_BFS(self):
        """
        call BFS if no db table has a readable entry
        """
        tview = mock.MagicMock(
            spec=views.TreeView,
            adjacency_list={"0": ["1"], "1": []},
            flat_nodes=[
                {"rest_key": "0", "id": 10},
                {"rest_key": "1", "id": 11},
            ],
        )

        tview._traverse_flat_nodes_BFS.return_value = ["0"]

        # simulate no DB entry given
        tview._get_and_parse_snapshot.return_value = (None, 0, [])

        views.TreeView._get_first_nodes(tview, first=1)

        tview._get_and_parse_snapshot.assert_called_once()
        tview._traverse_flat_nodes_BFS.assert_called_once_with("0", 1, ["0"])
        # get nodes is only called for BFS result
        tview._get_first_and_remaining_nodes.assert_called_once_with(["0"])

    def test__get_first_nodes_full_traversing(self):
        """
        If a snapshot is present in the DB, traverse flat_nodes down
        from selected node, then up and since top_level_keys is already full,
        do not fill it with BFS.
        """
        tview = mock.MagicMock(
            spec=views.TreeView,
            adjacency_list={"0": ["1", "3"], "1": ["2"]},
            flat_nodes=[
                {"rest_key": "0", "id": 10},
                {"rest_key": "1", "id": 11},
                {"rest_key": "2", "id": 12},
                {"rest_key": "3", "id": 13},
            ],
        )

        tview._traverse_downwards.return_value = ["1", "3"]
        tview._traverse_upwards.return_value = ["0"]

        tview._traverse_flat_nodes_BFS.return_value = ["0"]

        # selected node is "1"
        # expanded node is only root ("0")
        tview._get_and_parse_snapshot.return_value = ("1", 1, ["0"])

        # get four nodes
        # this calls traversing down from selectedNode "1" to node "3"
        # then traversing up from "1" to "0"
        # then _BFS is not called
        # so node 2 is skipped
        # lastly _get_nodes for rest keys is called
        views.TreeView._get_first_nodes(tview, first=3)

        tview._get_and_parse_snapshot.assert_called_once()

        # called traverse up and traverse down
        tview._traverse_downwards.assert_called_once_with(
            1,  # start_index, index of node 1 in flat_nodes
            3,  # max_length, amount of keys to find (3) - amount of found keys (0)
            "1",  # selected rest key
            ["0"],  # expanded rest keys
        )
        tview._traverse_upwards.assert_called_once_with(
            0,  # start_index - 1, index of node 0 in flat_nodes
            1,  # max_length, amount of keys to find (3) - amount of found keys (2)
            "1",  # selected rest key
            ["0"],  # expanded rest keys
        )

        # BFS not called
        tview._traverse_flat_nodes_BFS.assert_not_called()

        # get_nodes_called
        tview._get_first_and_remaining_nodes.assert_called_once_with(["1", "3", "0"])

    def test__reverse_adjacency_list(self):
        tview = mock.MagicMock(
            spec=views.TreeView,
            adjacency_list={"0": ["1", "3"], "1": ["2"], "3": ["4"]},
        )
        views.TreeView._reverse_adjacency_list(tview)
        self.assertDictEqual(
            tview.child_to_parent, {"1": "0", "3": "0", "2": "1", "4": "3"}
        )

    @mock.patch.object(views.TreeView, "get_tree_object")
    @mock.patch.object(views.TreeView, "get_adjacency_list")
    @mock.patch.object(
        views.rest_objects, "rest_objects_by_oid", return_value={"a": "A"}
    )
    def test_get_full_data(
        self, rest_objects_by_oid, get_adjacency_list, get_tree_object
    ):
        x = mock.MagicMock(
            spec=views.TreeView,
            records="foo",
            flat_nodes=[
                {"id": "a", "rest_key": "a@"},
                {"id": "b", "rest_key": "b@"},
                {"id": "c", "rest_key": "c@"},
            ],
            request="baz",
        )
        x._get_first_nodes.return_value = (x.flat_nodes[:2], x.flat_nodes[2:])
        # pylint: disable=protected-access
        self.assertIsNone(views.TreeView.get_full_data(x))
        self.assertEqual(
            x.adjacency_list,
            get_adjacency_list.return_value,
        )
        self.assertEqual(
            x.full_nodes,
            {
                "a@": x.get_tree_object.return_value,
                "b@": x.get_tree_object.return_value,
            },
        )
        get_adjacency_list.assert_called_once_with(x.flat_nodes)
        rest_objects_by_oid.assert_called_once_with(
            x.records,
            x.request,
            x.get_additional_data,
        )
        x._get_first_nodes.assert_called_once_with(None)

    @mock.patch.object(views.TreeView, "get_tree_object")
    @mock.patch.object(
        views.rest_objects,
        "rest_objects_by_restkey",
        return_value={
            "a": "A",
            "b": "B",
        },
    )
    @mock.patch.object(views.util, "resolve_records")
    @mock.patch.object(views.util, "get_table_for_oids")
    def test_get_full_data_of(
        self,
        get_table_for_oids,
        resolve_records,
        rest_objects_by_restkey,
        get_tree_object,
    ):
        self.assertEqual(
            views.TreeView.get_full_data_of("foo", "bar"),
            {
                "a": get_tree_object.return_value,
                "b": get_tree_object.return_value,
            },
        )
        get_table_for_oids.assert_called_once_with("foo")
        resolve_records.assert_called_once_with(get_table_for_oids.return_value)
        rest_objects_by_restkey.assert_called_once_with(
            resolve_records.return_value, "bar", views.TreeView.get_additional_data
        )
        get_tree_object.assert_has_calls(
            [
                mock.call("A"),
                mock.call("B"),
            ]
        )
        self.assertEqual(get_tree_object.call_count, 2)

    def test_format_response(self):
        x = mock.MagicMock(
            spec=views.TreeView,
            full_nodes="foo",
            adjacency_list="bar",
            remaining="baz",
        )
        self.assertEqual(
            views.TreeView.format_response(x),
            {
                "nodes": x.adjacency_list,
                "objects": x.full_nodes,
                "remaining": x.remaining,
            },
        )


@pytest.mark.unit
class TreeTableView(unittest.TestCase):
    def test_view_name(self):
        self.assertEqual(views.TreeTableView.view_name, "tree_table")

    def test_get_row_and_node(self):
        self.assertEqual(
            views.TreeTableView.get_row_and_node(
                12, mock.MagicMock(cdb_object_id="oid"), "rest_link", "foo", True
            ),
            (
                {
                    "id": "oid",
                    "rowNumber": 12,
                    "columns": [],
                    "restLink": "rest_link",
                },
                {
                    "id": "oid",
                    "rowNumber": 12,
                    "expanded": True,
                    "children": [],
                    "system:navigation_id": "foo",
                },
            ),
        )

    @mock.patch.object(
        views.util, "resolve_project_structure", return_value=(1, 2, 3, 4)
    )
    def test_resolve_structure(self, resolve_project_structure):
        x = mock.MagicMock(
            spec=views.TreeTableView,
            root_oid="foo",
            subprojects="bar",
            request="baz",
        )
        self.assertIsNone(views.TreeTableView.resolve_structure(x))
        self.assertEqual(x.records, 1)
        self.assertEqual(x.rows, 2)
        self.assertEqual(x.flat_nodes, 3)
        self.assertEqual(x.levels, 4)
        resolve_project_structure.assert_called_once_with(
            x.root_oid,
            x.subprojects,
            x.get_row_and_node,
            x.request,
        )

    def _get_full_data(self, first, visible_nodes):
        nodes = [
            {
                "id": "a",
                "expanded": False,
                "children": [
                    {"id": "b", "expanded": True, "children": []},
                ],
            },
            {
                "id": "c",
                "expanded": True,
                "children": [
                    {"id": "d", "children": []},
                ],
            },
        ]

        with mock.patch.object(
            views.util, "get_tree_nodes", return_value=nodes
        ) as get_tree_nodes:
            x = mock.MagicMock(
                spec=views.TreeTableView,
                flat_nodes="foo",
                levels="bar",
            )
            self.assertIsNone(views.TreeTableView.get_full_data(x, first))
            self.assertEqual(x.full_nodes, get_tree_nodes.return_value)
            self.assertEqual(x.visible_nodes, visible_nodes)
            get_tree_nodes.assert_called_once_with(x.flat_nodes, x.levels)

    def test_get_full_data_first_None(self):
        self._get_full_data(None, None)

    def test_get_full_data_first_always(self):
        self._get_full_data(0, ["a"])

    def test_get_full_data_first_only(self):
        self._get_full_data(2, ["a", "c"])

    def test_get_full_data(self):
        self._get_full_data(5, ["a", "c", "d"])

    def test_format_response(self):
        x = mock.MagicMock(
            spec=views.TreeTableView,
            rows="foo",
            full_nodes="bar",
        )
        self.assertEqual(
            views.TreeTableView.format_response(x),
            {
                "rows": x.rows,
                "nodes": x.full_nodes,
            },
        )


@pytest.mark.integration
class Utility(unittest.TestCase):
    def get_task_structure(self):
        task_uuid = "d4b2d7cc-94ed-11e9-833d-d0577b2793bc"  # Module 3
        self.assertEqual(
            views.get_task_structure(task_uuid, "").task_name,
            [
                str("Stakeholder Discussions 3"),
                str("Technical Requirements"),
                str("1"),
                str("2"),
                str("Technical requirements documented"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
