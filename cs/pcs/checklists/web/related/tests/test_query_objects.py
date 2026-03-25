#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import mock
import pytest

from cs.pcs.checklists.web.related import query_objects


@pytest.mark.unit
class QueryObjects(unittest.TestCase):
    def _getMockChecklists(self):
        return ["C1", "C2"]

    @mock.patch.object(query_objects.Checklist, "Query")
    def test_query_checklists_project_id(self, Query):
        self.assertEqual(
            query_objects.query_checklists("1", None, None),
            Query.return_value,
        )
        Query.assert_called_once_with(
            "cdb_project_id = '1'",
            access="read",
            addtl="ORDER BY cdb_cdate",
        )

    @mock.patch.object(query_objects.Checklist, "Query")
    def test_query_checklists_task_id(self, Query):
        self.assertEqual(
            query_objects.query_checklists("2", "some_Task_id", None),
            Query.return_value,
        )
        Query.assert_called_once_with(
            "cdb_project_id = '2' AND task_id = 'some_Task_id'",
            access="read",
            addtl="ORDER BY cdb_cdate",
        )

    @mock.patch.object(query_objects.Checklist, "Query")
    def test_query_checklists_all_fields(self, Query):
        self.assertEqual(
            query_objects.query_checklists("2", "some_Task_id", "some_checklist_id"),
            Query.return_value,
        )
        Query.assert_called_once_with(
            "cdb_project_id = '2' AND task_id = 'some_Task_id' AND checklist_id = 'some_checklist_id'",
            access="read",
            addtl="ORDER BY cdb_cdate",
        )

    @mock.patch.object(query_objects.Checklist, "Query")
    @mock.patch.object(query_objects.sqlapi, "SQLdate_literal")
    def test_query_checklists_timestamp(self, SQLdate_literal, Query):
        self.assertEqual(
            query_objects.query_checklists("2", None, None),
            Query.return_value,
        )
        Query.assert_called_once_with(
            "cdb_project_id = '2'",
            access="read",
            addtl="ORDER BY cdb_cdate",
        )

    @mock.patch.object(query_objects.ChecklistItem, "Query")
    def test_query_items_no_cls(self, Query):
        self.assertEqual(
            query_objects.query_items("1", None),
            [],
        )
        Query.assert_not_called()

    @mock.patch.object(query_objects.ChecklistItem, "Query")
    def test_query_items_no_ts(self, Query):
        self.assertEqual(
            query_objects.query_items("1", self._getMockChecklists()),
            Query.return_value,
        )
        Query.assert_called_once_with(
            "cdb_project_id = '1' AND checklist_id IN (C1, C2)",
            access="read",
            addtl="ORDER BY position",
        )

    @mock.patch.object(query_objects.ChecklistItem, "Query")
    @mock.patch.object(query_objects.sqlapi, "SQLdate_literal")
    def test_query_items(self, SQLdate_literal, Query):
        self.assertEqual(
            query_objects.query_items("1", self._getMockChecklists()),
            Query.return_value,
        )
        Query.assert_called_once_with(
            "cdb_project_id = '1' AND checklist_id IN (C1, C2)",
            access="read",
            addtl="ORDER BY position",
        )

    @mock.patch.object(query_objects.Rule, "Query")
    @mock.patch.object(query_objects.sqlapi, "RecordSet2")
    def test_query_rules_no_cls(self, RecordSet2, Query):
        self.assertEqual(
            query_objects.query_rules("1", None),
            {},
        )
        RecordSet2.assert_not_called()
        Query.assert_not_called()

    @mock.patch.object(query_objects.Rule, "Query")
    @mock.patch.object(query_objects.sqlapi, "RecordSet2")
    def test_query_rules_no_ts(self, RecordSet2, Query):
        mockRelations = [
            {
                "rule_id": "rule1_id",
                "cdb_project_id": "project_id",
                "checklist_id": "C1",
            },
            {
                "rule_id": "rule2_id",
                "cdb_project_id": "project_id",
                "checklist_id": "C2",
            },
        ]
        RecordSet2.return_value = mockRelations

        self.assertEqual(
            query_objects.query_rules("1", self._getMockChecklists()),
            {
                "rules": Query.return_value,
                "refs": {rel["rule_id"]: [rel] for rel in mockRelations},
            },
        )
        RecordSet2.assert_called_once_with(
            "cdbpcs_deliv2rule",
            "cdb_project_id = '1' AND checklist_id IN (C1, C2)",
            addtl="ORDER BY rule_id",
        )
        Query.assert_called_once_with(
            "name IN ('rule1_id', 'rule2_id')",
            access="read",
        )

    @mock.patch.object(query_objects.Rule, "Query")
    @mock.patch.object(query_objects.sqlapi, "RecordSet2")
    @mock.patch.object(query_objects.sqlapi, "SQLdate_literal")
    def test_query_rules(self, SQLdate_literal, RecordSet2, Query):
        mockRelations = [
            {
                "rule_id": "rule1_id",
                "cdb_project_id": "project_id",
                "checklist_id": "C1",
            },
            {
                "rule_id": "rule2_id",
                "cdb_project_id": "project_id",
                "checklist_id": "C2",
            },
        ]
        RecordSet2.return_value = mockRelations

        self.assertEqual(
            query_objects.query_rules("1", self._getMockChecklists()),
            {
                "rules": Query.return_value,
                "refs": {rel["rule_id"]: [rel] for rel in mockRelations},
            },
        )
        RecordSet2.assert_called_once_with(
            "cdbpcs_deliv2rule",
            "cdb_project_id = '1' AND checklist_id IN (C1, C2)",
            addtl="ORDER BY rule_id",
        )
        Query.assert_called_once_with(
            "name IN ('rule1_id', 'rule2_id')",
            access="read",
        )


if __name__ == "__main__":
    unittest.main()
