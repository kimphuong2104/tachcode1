#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access,abstract-method

__revision__ = "$Id$"

import unittest

import mock
import pytest
from cdb import testcase

from cs.pcs.projects.project_structure import util


@pytest.mark.unit
class Utility(unittest.TestCase):
    @mock.patch.object(util, "unquote")
    def test_url_unquote(self, unquote):
        "returns unquoted text"
        self.assertEqual(
            util.url_unquote("foo"),
            unquote.return_value,
        )
        unquote.assert_called_once_with("foo")

    @mock.patch.object(util, "urlencode")
    @mock.patch.object(util, "quote")
    def test__get_icon_url_no_query(self, quote, urlencode):
        self.assertEqual(
            util._get_icon_url("foo", ""),
            f"/resources/icons/byname/{quote.return_value}",
        )
        quote.assert_called_once_with("foo")
        urlencode.assert_not_called()

    @mock.patch.object(util, "urlencode")
    @mock.patch.object(util, "quote")
    def test__get_icon_url(self, quote, urlencode):
        self.assertEqual(
            util._get_icon_url("foo", "bar"),
            f"/resources/icons/byname/{quote.return_value}?{urlencode.return_value}",
        )
        quote.assert_called_once_with("foo")
        urlencode.assert_called_once_with("bar")

    @mock.patch.object(util, "urlencode")
    @mock.patch.object(util, "quote")
    def test_get_object_icon_attrs(self, quote, urlencode):
        "returns object icon with dynamic attrs"
        self.assertEqual(
            util.get_object_icon("icon", {"ä": "Ä", "b": "B"}, "ä", "b"),
            f"/resources/icons/byname/{quote.return_value}?{urlencode.return_value}",
        )
        quote.assert_called_once_with("icon")
        urlencode.assert_called_once_with([("ä", "Ä"), ("b", "B")])

    @mock.patch.object(util, "quote")
    def test_get_object_icon(self, quote):
        "returns simple object icon"
        self.assertEqual(
            util.get_object_icon("icon", "record"),
            f"/resources/icons/byname/{quote.return_value}",
        )
        quote.assert_called_once_with("icon")

    @mock.patch.object(util.logging, "exception")
    @mock.patch.object(util, "StatusInfo", side_effect=ValueError)
    def test__get_status_label_invalid(self, StatusInfo, exception):
        self.assertIsNone(util._get_status_label("foo", "bar"))
        StatusInfo.assert_called_once_with("foo", "bar")
        exception.assert_called_once_with("invalid status: '%s', %s", "foo", "bar")

    @mock.patch.object(util, "StatusInfo")
    def test__get_status_label(self, StatusInfo):
        self.assertEqual(
            util._get_status_label("foo", "bar"),
            StatusInfo.return_value.getLabel.return_value,
        )
        StatusInfo.assert_called_once_with("foo", "bar")
        StatusInfo.return_value.getLabel.assert_called_once_with()

    @mock.patch.object(util, "_get_status_label")
    @mock.patch.object(util, "_get_icon_url")
    def test_get_status(self, _get_icon_url, _get_status_label):
        self.assertEqual(
            util.get_status("foo", "bar"),
            {
                "url": _get_icon_url.return_value,
                "title": _get_status_label.return_value,
            },
        )
        _get_icon_url.assert_called_once_with(
            "State Color/0",
            [
                ("sys::workflow", "foo"),
                ("sys::status", "bar"),
            ],
        )
        _get_status_label.assert_called_once_with("foo", "bar")

    def test_get_object_description_attrs(self):
        "returns object description with dynamic attrs"
        self.assertEqual(
            util.get_object_description(
                "b={b} ä={ä}",
                {"ä": "Ä", "b": "B"},
                "ä",
                "b",
            ),
            "b=B ä=Ä",
        )

    def test_get_object_description(self):
        "returns simple object description"
        self.assertEqual(
            util.get_object_description("desc"),
            "desc",
        )

    @mock.patch.object(util, "get_readable_oids")
    @mock.patch("cs.pcs.projects.common.rest_objects.get_restlinks_in_batch")
    @mock.patch("cs.pcs.projects.common.rest_objects.get_restkeys_in_batch")
    def test_get_flat_structure(
        self, get_restkeys_in_batch, get_restlinks_in_batch, get_readable_oids
    ):
        getter = mock.MagicMock()
        getter.return_value = ("row", "node")
        levels = [
            mock.MagicMock(level="0", cdb_object_id="a"),
            mock.MagicMock(level=1, cdb_object_id="b"),
        ]
        get_restkeys_in_batch.return_value = {"a": "X", "b": "Y"}
        get_restlinks_in_batch.return_value = {"a": "A", "b": "B"}
        get_readable_oids.return_value = levels
        self.assertEqual(
            util.get_flat_structure(
                "levels", "records", getter, "request", {"1": True}
            ),
            (["row", "row"], ["node", "node"], [0, 1]),
        )
        get_restkeys_in_batch.assert_called_once_with("records")
        get_restlinks_in_batch.assert_called_once_with("records", "request")
        get_readable_oids.assert_called_once_with(
            "levels", get_restlinks_in_batch.return_value
        )
        getter.assert_has_calls(
            [
                mock.call(0, levels[0], "A", "X", True),
                mock.call(1, levels[1], "B", "Y", False),
            ]
        )

    @mock.patch.object(util, "get_flat_structure", return_value=(1, 2, 3))
    @mock.patch.object(util, "resolve_records")
    @mock.patch.object(util, "resolve_structure")
    def test_resolve_project_structure(
        self, resolve_structure, resolve_records, get_flat_structure
    ):
        self.assertEqual(
            util.resolve_project_structure("foo", True, "getter", "req"),
            (resolve_records.return_value, 1, 2, 3),
        )
        resolve_structure.assert_called_once_with("foo", "cdbpcs_project", True)
        resolve_records.assert_called_once_with(resolve_structure.return_value)
        get_flat_structure.assert_called_once_with(
            resolve_structure.return_value,
            resolve_records.return_value,
            "getter",
            "req",
        )

    @mock.patch.object(util, "resolve_query")
    @mock.patch.object(util.query_patterns, "get_query_pattern")
    def test_resolve_structure(self, get_query_pattern, resolve_query):
        "resolve structure"
        self.assertEqual(
            util.resolve_structure("root", "table", True),
            resolve_query.return_value,
        )
        get_query_pattern.assert_called_once_with("structure")
        resolve_query.assert_called_once_with(
            get_query_pattern.return_value.format(oid="root"),
        )

    @mock.patch.object(util, "resolve_query")
    @mock.patch.object(util.query_patterns, "get_query_pattern")
    def test_resolve_structure_subprojects(self, get_query_pattern, resolve_query):
        "resolve structure"
        self.assertEqual(
            util.resolve_structure("root", "cdbpcs_project", True),
            resolve_query.return_value,
        )
        get_query_pattern.assert_called_once_with("subprojects")
        resolve_query.assert_called_once_with(
            get_query_pattern.return_value.format(oid="root"),
        )

    @mock.patch.object(util.query_patterns, "get_query_pattern", return_value=None)
    def test_resolve_structure_no_children(self, get_query_pattern):
        "resolve structure without children"
        self.assertEqual(
            util.resolve_structure("A", "table", True),
            [util.PCS_LEVEL("A", "table", 0)],
        )

    @mock.patch.object(
        util.sqlapi,
        "RecordSet2",
        return_value=[
            mock.MagicMock(cdb_object_id="oid1", table_name="tbl1", llevel=0),
            mock.MagicMock(cdb_object_id="oid2", table_name="tbl2", llevel=1.0),
        ],
    )
    def test_resolve_query(self, RecordSet2):
        self.assertEqual(
            util.resolve_query("query"),
            [
                util.PCS_LEVEL("oid1", "tbl1", 0),
                util.PCS_LEVEL("oid2", "tbl2", 1),
            ],
        )
        RecordSet2.assert_called_once_with(sql="query")

    def test_get_tree_nodes_no_flat_nodes(self):
        "handles falsy 'flat_nodes' gracefully"
        self.assertEqual(
            util.get_tree_nodes(None, None),
            [],
        )

    def test_get_tree_nodes_no_children(self):
        "node missing 'children' -> KeyError"
        with self.assertRaises(KeyError):
            util.get_tree_nodes([{"id": "A"}, {"id": "B"}], [0, 1])

    def test_get_tree_nodes_no_dict(self):
        "node is not a dict -> TypeError"
        with self.assertRaises(TypeError):
            util.get_tree_nodes([0, 1], [0, 1])

    def test_get_tree_nodes_levels_no_iter(self):
        "levels not iterable -> TypeError"
        with self.assertRaises(TypeError):
            util.get_tree_nodes([0], None)

    def test_get_tree_nodes_less_levels_than_nodes(self):
        "len(levels) < len(flat_nodes) -> IndexError"
        with self.assertRaises(IndexError):
            util.get_tree_nodes([0], [])

    def test_get_tree_nodes_first_level_not_0(self):
        "levels doesn't start with 0 -> IndexError"
        with self.assertRaises(IndexError):
            util.get_tree_nodes([{"id": "A", "children": []}], [1])

    def test_get_tree_nodes_gap_in_levels(self):
        "levels has a gap -> IndexError"
        with self.assertRaises(IndexError):
            util.get_tree_nodes(
                [{"id": "A", "children": []}, {"id": "B", "children": []}],
                [0, 2],
            )

    def test_get_tree_nodes(self):
        "returns nested nodes"
        _flat_nodes = [
            "A",
            "A.1",
            "B",
            "C",
            "C.1",
            "C.1.1",
            "C.1.2",
            "C.2",
            "D",
            "D.1",
            "D.1.1",
            "E",
        ]
        flat_nodes = [{"id": x, "children": []} for x in _flat_nodes]
        levels = [
            0,
            1,
            0,
            0,
            1,
            2,
            2,
            1,
            0,
            1,
            2,
            0,
        ]
        self.assertEqual(
            util.get_tree_nodes(flat_nodes, levels),
            [
                {
                    "id": "A",
                    "children": [
                        {"id": "A.1", "children": []},
                    ],
                },
                {"id": "B", "children": []},
                {
                    "id": "C",
                    "children": [
                        {
                            "id": "C.1",
                            "children": [
                                {"id": "C.1.1", "children": []},
                                {"id": "C.1.2", "children": []},
                            ],
                        },
                        {"id": "C.2", "children": []},
                    ],
                },
                {
                    "id": "D",
                    "children": [
                        {
                            "id": "D.1",
                            "children": [
                                {"id": "D.1.1", "children": []},
                            ],
                        },
                    ],
                },
                {"id": "E", "children": []},
            ],
        )

    def test_get_first_nodes_missing_id(self):
        "fails if key 'id' is missing in node"
        nodes = [{"children": [9, 8]}]
        with self.assertRaises(KeyError) as error:
            util.get_first_nodes(nodes, 5)
        self.assertEqual("'id'", str(error.exception))

    def test_get_first_nodes_missing_children(self):
        "fails if key 'children' is missing in node"
        nodes = [{"id": "1", "expanded": True}]
        with self.assertRaises(KeyError) as error:
            util.get_first_nodes(nodes, 5)
        self.assertEqual("'children'", str(error.exception))

    def test_get_first_nodes_non_numerical_size(self):
        "fails if max_size is not numerical"
        nodes = [{"id": "1", "expanded": True, "children": []}]
        with self.assertRaises(TypeError) as error:
            util.get_first_nodes(nodes, "foo")
        self.assertEqual(
            "'>=' not supported between instances of 'int' and 'str'",
            str(error.exception),
        )

    def test_get_first_nodes_first(self):
        "always includes the first node in result"
        nodes = [{"id": "1"}]
        self.assertEqual(util.get_first_nodes(nodes, 0), ["1"])
        self.assertEqual(util.get_first_nodes(nodes, -1), ["1"])

    def test_get_first_nodes(self):
        "flattens tree nodes to first n visible node IDs"
        nodes = [
            {"id": "1", "children": [9, 8]},  # expanded defaults to False
            {
                "id": "2",
                "expanded": True,
                "children": [
                    {
                        "id": "3",
                        "expanded": True,
                        "children": [
                            {"id": "4", "expanded": False, "children": [7, 6]},
                        ],
                    },
                ],
            },
            {
                "id": "5",
                "expanded": True,
                "children": [
                    {"id": "6", "expanded": False, "children": []},
                    {"id": "7", "expanded": False, "children": []},
                    {"id": "8", "expanded": False, "children": []},
                ],
            },
            {"id": "9", "expanded": False, "children": []},
        ]
        self.assertEqual(
            util.get_first_nodes(nodes, 7), ["1", "2", "3", "4", "5", "6", "7"]
        )

    @mock.patch.object(util, "_get_oid_query_str", side_effect=TypeError)
    @mock.patch.object(
        util,
        "_get_oids_by_relation",
        return_value=[
            ("r1", "o1"),
            ("r2", "o2"),
        ],
    )
    def test_resolve_records_error(self, _get_oids_by_relation, _get_oid_query_str):
        "fails if query cannot be constructed"
        with self.assertRaises(ValueError) as error:
            util.resolve_records("oids")

        self.assertEqual(
            str(error.exception),
            "non-string oid value: 'o1'",
        )
        _get_oids_by_relation.assert_called_once_with("oids")
        _get_oid_query_str.assert_called_once_with("o1")

    @mock.patch.object(
        util.sqlapi, "RecordSet2", autospec=True, return_value=["rec1", "rec2"]
    )
    @mock.patch.object(util, "_get_oid_query_str")
    @mock.patch.object(
        util,
        "_get_oids_by_relation",
        return_value=[
            ("r1", "o1"),
            ("r2", "o2"),
        ],
    )
    def test_resolve_records(
        self, _get_oids_by_relation, _get_oid_query_str, RecordSet2
    ):
        "resolves records for pcs_oids"
        self.assertEqual(
            util.resolve_records("oids"),
            [
                util.PCS_RECORD("r1", "rec1"),
                util.PCS_RECORD("r1", "rec2"),
                util.PCS_RECORD("r2", "rec1"),
                util.PCS_RECORD("r2", "rec2"),
            ],
        )
        _get_oids_by_relation.assert_called_once_with("oids")
        _get_oid_query_str.assert_has_calls(
            [
                mock.call("o1"),
                mock.call("o2"),
            ]
        )
        self.assertEqual(_get_oid_query_str.call_count, 2)
        RecordSet2.assert_has_calls(
            [
                mock.call("r1", _get_oid_query_str.return_value, access="read"),
                mock.call("r2", _get_oid_query_str.return_value, access="read"),
            ]
        )
        self.assertEqual(RecordSet2.call_count, 2)

    def test_get_readable_oids(self):
        "returns only nodes with readable paths"
        ordered_oids = [
            util.PCS_LEVEL("zero", "foo", 0),
            util.PCS_LEVEL("one", "foo", 0),
            util.PCS_LEVEL("two", "foo", 0),
            util.PCS_LEVEL("three", "foo", 1),
            util.PCS_LEVEL("four", "foo", 0),
        ]
        self.assertEqual(
            util.get_readable_oids(ordered_oids, ["one", "three", "four"]),
            # "three" is theoretically visible, but its parent "two" is not
            [ordered_oids[1], ordered_oids[4]],
        )

    @mock.patch.object(util, "format_in_condition")
    def test__get_oid_query_str_default(self, format_in_condition):
        "returns query for cdb_object_id"
        self.assertEqual(
            util._get_oid_query_str("foo"),
            format_in_condition.return_value,
        )
        format_in_condition.assert_called_once_with("cdb_object_id", "foo")

    @mock.patch.object(util, "format_in_condition")
    def test__get_oid_query_str(self, format_in_condition):
        "returns query for attribute"
        self.assertEqual(
            util._get_oid_query_str("foo", "bar"),
            format_in_condition.return_value,
        )
        format_in_condition.assert_called_once_with("bar", "foo")

    def test__get_oids_by_relation_type(self):
        "fails if value is not iterable"
        pcs_oids = [1]

        with self.assertRaises(ValueError) as error:
            util._get_oids_by_relation(pcs_oids)

        self.assertEqual(
            str(error.exception),
            "value (or one of its values) is not iterable: '[1]'",
        )

    def test__get_oids_by_relation_index(self):
        "fails if value contains less than two values"
        pcs_oids = [[1]]

        with self.assertRaises(ValueError) as error:
            util._get_oids_by_relation(pcs_oids)

        self.assertEqual(
            str(error.exception),
            "each value must contain at least 2 values: '[[1]]'",
        )

    def test__get_oids_by_relation(self):
        "group oids by relation"
        pcs_levels = [
            util.PCS_LEVEL("zero", "bar", 0),
            util.PCS_LEVEL("one", "foo", 0),
            util.PCS_LEVEL("two", "bar", 0),
            util.PCS_LEVEL("three", "bar", 0),
            util.PCS_LEVEL("four", "foo", 0),
        ]
        self.assertEqual(
            util._get_oids_by_relation(pcs_levels),
            [
                ("bar", ["zero", "two", "three"]),
                ("foo", ["one", "four"]),
            ],
        )

    @mock.patch.object(
        util.sqlapi,
        "RecordSet2",
        return_value=[
            mock.MagicMock(id="o1", relation="t1"),
            mock.MagicMock(id="o2", relation="t2"),
        ],
    )
    @mock.patch.object(util, "_get_oid_query_str")
    def test_get_table_for_oids(self, _get_oid_query_str, RecordSet2):
        self.assertEqual(
            util.get_table_for_oids("foo"),
            [
                util.PCS_LEVEL("o1", "t1", 0),
                util.PCS_LEVEL("o2", "t2", 0),
            ],
        )
        _get_oid_query_str.assert_called_once_with("foo", "id")
        RecordSet2.assert_called_once_with(
            sql=f"SELECT * FROM cdb_object WHERE {_get_oid_query_str.return_value}"
        )

    @mock.patch.object(util.ddl, "Table")
    @mock.patch.object(util, "CDBClassDef")
    def test_validate_dtag_raises(self, CDBClassDef, Table):
        Table.return_value.hasColumn.side_effect = [True, True, False]
        classname = "cdbpcs_project"
        label = "{cdb_project_id} {cdb_project_name} {false_attrb}"
        with self.assertRaises(util.util.ErrorMessage):
            util.validate_dtag(classname, label, False)
        CDBClassDef.assert_called_once_with(classname)
        Table.assert_called_once_with(
            CDBClassDef.return_value.getPrimaryTable.return_value
        )

    @mock.patch.object(util.ddl, "Table")
    @mock.patch.object(util, "CDBClassDef")
    def test_validate_dtag(self, CDBClassDef, Table):
        Table.return_value.hasColumn.return_value = True
        classname = "cdbpcs_project"
        label = "{cdb_project_id} {cdb_project_name}"
        util.validate_dtag(classname, label)
        CDBClassDef.assert_called_once_with(classname)
        Table.assert_called_once_with(
            CDBClassDef.return_value.getPrimaryTable.return_value
        )

    def test_rest_id2rest_key_too_few_segments(self):
        with self.assertRaises(IndexError):
            util.rest_id2rest_key("A")

    def test_rest_id2rest_key_no_task(self):
        self.assertEqual(
            util.rest_id2rest_key("A/B/C"),
            ("C", False),
        )

    def test_rest_id2rest_key_task(self):
        self.assertEqual(
            util.rest_id2rest_key("A/project_task/C"),
            ("C", True),
        )

    def test_fit_text_high_max(self):
        self.assertEqual(
            util.fit_text("abcdef", "g", 10),
            "abcdefg",
        )

    def test_fit_text_exact_fit(self):
        self.assertEqual(
            util.fit_text("abcdef", "g", 7),
            "abcdefg",
        )

    def test_fit_text_ellipsis(self):
        self.assertEqual(
            util.fit_text("abcdef", "g", 6),
            "ab...g",
        )

    def test_fit_text_ellipsis_only(self):
        self.assertEqual(
            util.fit_text("abcdef", "g", 4),
            "...g",
        )

    def test_fit_text_too_few_chars(self):
        with self.assertRaises(ValueError) as error:
            util.fit_text("abcdef", "g", 3)

        self.assertEqual(
            str(error.exception),
            "cannot fit text into 3 chars: 'abcdefg'",
        )

    @mock.patch.object(util.util, "get_label", return_value="COPY")
    def test_get_copy_name_first_copy_empty(self, _):
        self.assertEqual(
            util.get_copy_name("X", [], 60),
            "X",
        )

    @mock.patch.object(util.util, "get_label", return_value="COPY")
    def test_get_copy_name_first_copy(self, _):
        self.assertEqual(
            util.get_copy_name("X", ["a"], 60),
            "X",
        )

    @mock.patch.object(util.util, "get_label", return_value="COPY")
    def test_get_copy_name_first_copy_with_postfix_1(self, _):
        self.assertEqual(
            util.get_copy_name("X (COPY)", ["a"], 60),
            "X",
        )

    @mock.patch.object(util.util, "get_label", return_value="COPY")
    def test_get_copy_name_first_copy_with_postfix_n(self, _):
        self.assertEqual(
            util.get_copy_name("X (COPY 4)", ["a"], 60),
            "X",
        )

    @mock.patch.object(util.util, "get_label", return_value="COPY")
    def test_get_copy_name_second_copy(self, _):
        self.assertEqual(
            util.get_copy_name("X", ["X"], 60),
            "X (COPY)",
        )

    @mock.patch.object(util.util, "get_label", return_value="COPY")
    def test_get_copy_name_second_copy_with_postfix(self, _):
        self.assertEqual(
            util.get_copy_name("X (COPY 5)", ["X"], 60),
            "X (COPY)",
        )

    @mock.patch.object(util.util, "get_label", return_value="CP")
    def test_get_copy_name_nth_copy(self, _):
        children = ["X (CP 7)", "X (CP 41)", "X (CP 5)", "a (CP 111)"]
        self.assertEqual(
            util.get_copy_name("X", children, 60),
            "X (CP 42)",
        )

    @mock.patch.object(util.util, "get_label", return_value="CP")
    def test_get_copy_name_nth_copy_has_postfix(self, _):
        children = ["X (CP 7)", "X (CP 41)", "X (CP 5)", "a (CP 111)"]
        self.assertEqual(
            util.get_copy_name("X (CP 9)", children, 60),
            "X (CP 42)",
        )

    @mock.patch.object(util.util, "get_label", return_value="COPY")
    def test_get_copy_name_has_postfix_without_space(self, _):
        self.assertEqual(
            util.get_copy_name("X (COPY5123)", [], 60),
            "X",
        )

    @mock.patch.object(util.util, "get_label", return_value="COPY")
    def test_get_copy_name_has_postfix_with_addtl_space(self, _):
        self.assertEqual(
            util.get_copy_name("X (COPY 5123) ", [], 60),
            "X",
        )

    @mock.patch.object(util.util, "get_label", return_value="COPY")
    def test_get_copy_name_fits_column(self, _):
        self.assertEqual(
            util.get_copy_name("abcdefg", ["abc... (COPY 12345)"], 19),
            "abc... (COPY 12346)",
        )


@pytest.mark.integration
class UtilityIntegration(testcase.RollbackTestCase):
    def test_format_in_condition(self):
        base_condition = condition = "cdb_project_id='Ptest.msp.small'"
        all_tasks = util.sqlapi.RecordSet2("cdbpcs_task", base_condition)
        task_ids = [x.task_id for x in all_tasks]

        condition = (
            f"{base_condition} AND ({util.format_in_condition('task_id', task_ids, 3)})"
        )
        rset = util.sqlapi.RecordSet2("cdbpcs_task", condition)
        self.assertEqual(
            {x.task_id for x in rset},
            set(task_ids),
        )


if __name__ == "__main__":
    unittest.main()
