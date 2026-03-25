#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest
from collections import defaultdict
from datetime import date

import mock
import pytest
from cdb import sqlapi, testcase, util

from cs.pcs.checklists import Checklist, ChecklistItem
from cs.pcs.issues import Issue
from cs.pcs.projects import Project, data_sources, indicators
from cs.pcs.projects.tasks import Task


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


@pytest.mark.unit
class Utility(unittest.TestCase):
    @mock.patch.object(
        data_sources.DataSource, "GetCombinedViewStatement", return_value=""
    )
    def test_generate_cdbpcs_project_indicators_v_fallback(
        self, GetCombinedViewStatement
    ):
        "returns fallback view definition if no indicators exist"
        self.assertEqual(
            indicators.generate_cdbpcs_project_indicators_v(),
            """
            SELECT
                NULL AS data_source,
                0 AS quantity,
                NULL AS cdb_project_id,
                '' AS ce_baseline_id
            FROM cdbpcs_project
            WHERE 1=2
        """,
        )
        GetCombinedViewStatement.assert_called_once_with("project", ["cdb_project_id"])

    @mock.patch.object(
        data_sources.DataSource, "GetCombinedViewStatement", return_value=""
    )
    def test_generate_cdbpcs_task_indicators_v_fallback(self, GetCombinedViewStatement):
        "returns fallback view definition if no indicators exist"
        self.assertEqual(
            indicators.generate_cdbpcs_task_indicators_v(),
            """
            SELECT
                NULL AS data_source,
                0 AS quantity,
                NULL AS cdb_project_id,
                '' AS ce_baseline_id,
                NULL AS task_id
            FROM cdbpcs_task
            WHERE 1=2
        """,
        )
        GetCombinedViewStatement.assert_called_once_with(
            "project_task", ["cdb_project_id", "task_id"]
        )

    @mock.patch.object(data_sources.DataSource, "GetCombinedViewStatement")
    def test_generate_cdbpcs_project_indicators_v(self, GetCombinedViewStatement):
        "returns indicator view definition"
        self.assertEqual(
            indicators.generate_cdbpcs_project_indicators_v(),
            GetCombinedViewStatement.return_value,
        )
        GetCombinedViewStatement.assert_called_once_with("project", ["cdb_project_id"])

    @mock.patch.object(data_sources.DataSource, "GetCombinedViewStatement")
    def test_generate_cdbpcs_task_indicators_v(self, GetCombinedViewStatement):
        "returns indicator view definition"
        self.assertEqual(
            indicators.generate_cdbpcs_task_indicators_v(),
            GetCombinedViewStatement.return_value,
        )
        GetCombinedViewStatement.assert_called_once_with(
            "project_task", ["cdb_project_id", "task_id"]
        )


@pytest.mark.unit
class Indicator(unittest.TestCase):
    @mock.patch.object(indicators.util, "get_label")
    def test_to_json_nolabel(self, get_label):
        "serializes list of indicators to JSON (no label)"
        indicator = mock.MagicMock(
            spec=indicators.Indicator,
            label=None,
            data_source_pattern="{foo}",
            list_config_name="configname",
            overlay_component_name="comname",
        )
        indicator.indicator_fqpyname = ""
        raw_data = {"A": {"foo": 4}, "B": {"foo": 2}}
        self.assertEqual(
            indicators.Indicator.to_json(indicator, raw_data),
            {
                "icon": indicator.icon,
                "label": "",
                "list_config_name": "configname",
                "overlay_component_name": "comname",
                "data": {
                    "A": {
                        "value": "4",
                    },
                    "B": {
                        "value": "2",
                    },
                },
            },
        )
        get_label.assert_not_called()

    @mock.patch.object(indicators.util, "get_label")
    def test_to_json(self, get_label):
        "serializes list of indicators to JSON"
        indicator = mock.MagicMock(
            spec=indicators.Indicator,
            data_source_pattern="{foo}",
            list_config_name="configname",
            overlay_component_name="comname",
        )
        indicator.indicator_fqpyname = ""
        raw_data = {"A": {"foo": 4}, "B": {"foo": 2}}
        self.assertEqual(
            indicators.Indicator.to_json(indicator, raw_data),
            {
                "icon": indicator.icon,
                "label": get_label.return_value,
                "list_config_name": "configname",
                "overlay_component_name": "comname",
                "data": {
                    "A": {
                        "value": "4",
                    },
                    "B": {
                        "value": "2",
                    },
                },
            },
        )
        get_label.assert_called_once_with(indicator.label)

    @mock.patch.object(indicators.util, "get_label")
    @mock.patch.object(indicators, "getObjectByName")
    def test_to_json_with_setup(self, getObjectByName, get_label):
        "serializes list of indicators to JSON with at setup method"

        def setup_method(obj, raw_data):
            data_result = defaultdict(lambda: defaultdict(dict))
            for rid, _ in raw_data.items():
                data_result[rid]["value"] = "bar"
            return data_result

        getObjectByName.return_value = setup_method
        indicator = mock.MagicMock(
            spec=indicators.Indicator,
            data_source_pattern="{foo}",
            list_config_name="configname",
            overlay_component_name="comname",
        )
        indicator.indicator_fqpyname = "foo"
        raw_data = {"A": {"foo": 4}, "B": {"foo": 2}}
        self.assertEqual(
            indicators.Indicator.to_json(indicator, raw_data),
            {
                "icon": indicator.icon,
                "label": get_label.return_value,
                "list_config_name": "configname",
                "overlay_component_name": "comname",
                "data": {
                    "A": {
                        "value": "bar",
                    },
                    "B": {
                        "value": "bar",
                    },
                },
            },
        )
        get_label.assert_called_once_with(indicator.label)
        getObjectByName.assert_called_once_with("foo")

    @mock.patch.object(indicators, "getObjectByName")
    def test_validate_fqpyname(self, getObjectByName):
        indicator = mock.MagicMock(spec=indicators.Indicator, indicator_fqpyname="foo")
        mock_ctx = mock.MagicMock()

        indicators.Indicator.validate_fqpyname(indicator, mock_ctx)

        getObjectByName.assert_called_once_with("foo")

    @mock.patch.object(indicators, "getObjectByName", side_effect=KeyError)
    def test_validate_fqpyname_error(self, getObjectByName):
        indicator = mock.MagicMock(spec=indicators.Indicator, indicator_fqpyname="foo")
        mock_ctx = mock.MagicMock()
        with self.assertRaises(util.ErrorMessage):
            indicators.Indicator.validate_fqpyname(indicator, mock_ctx)

        getObjectByName.assert_called_once_with("foo")


@pytest.mark.unit
class Resolve(unittest.TestCase):
    def test_ResolveProjectIndicators_wrong_rest_name(self):
        "Returns None if called with wrong rest name"
        self.assertIsNone(indicators.ResolveProjectIndicators("wrong_rest_name", []))

    @mock.patch.object(indicators.Indicator, "KeywordQuery")
    @mock.patch.object(indicators.sqlapi, "RecordSet2")
    def test_ResolveProjectIndicators(self, RecordSet2, KeywordQuery):
        project_ids = [("foo_pid", "foo_bid"), ("bar_pid", "bar_bid")]
        RecordSet2.return_value = [
            mock.MagicMock(cdb_project_id="foo_pid", data_source="A", quantity=1),
            mock.MagicMock(cdb_project_id="bar_pid", data_source="B", quantity=2),
        ]
        mock_indicator = mock.MagicMock(spec=indicators.Indicator)
        KeywordQuery.return_value = [mock_indicator]
        self.assertDictEqual(
            indicators.ResolveProjectIndicators(
                "project", project_ids, indicator_whitelist=["foo_indicator"]
            ),
            {mock_indicator.name: mock_indicator.to_json.return_value},
        )
        RecordSet2.assert_called_once_with(
            "cdbpcs_project_indicators_v", "cdb_project_id IN ('foo_pid', 'bar_pid')"
        )
        KeywordQuery.assert_called_once_with(
            rest_visible_name="project", name=["foo_indicator"]
        )
        mock_indicator.to_json.assert_called_once_with(
            {"foo_pid@": {"A": 1}, "bar_pid@": {"B": 2}}
        )

    def test_ResolveTasksIndicators_wrong_rest_name(self):
        "Returns None if called with wrong rest name"
        self.assertIsNone(indicators.ResolveTasksIndicators("wrong_rest_name", []))

    @mock.patch.object(indicators.Indicator, "KeywordQuery")
    @mock.patch.object(indicators.sqlapi, "RecordSet2")
    @mock.patch.object(indicators, "get_sql_condition")
    def test_ResolveTasksIndicators(self, get_sql_condition, RecordSet2, KeywordQuery):
        task_ids = [
            ("foo_pid", "foo_tid", "foo_bid"),
            ("bar_pid", "bar_tid", "bar_bid"),
        ]
        RecordSet2.return_value = [
            mock.MagicMock(
                cdb_project_id="foo_pid", task_id="foo_tid", data_source="A", quantity=1
            ),
            mock.MagicMock(
                cdb_project_id="bar_pid", task_id="bar_tid", data_source="B", quantity=2
            ),
        ]

        mock_indicator = mock.MagicMock(spec=indicators.Indicator)
        KeywordQuery.return_value = [mock_indicator]
        self.assertDictEqual(
            indicators.ResolveTasksIndicators(
                "project_task", task_ids, indicator_whitelist=["foo_indicator"]
            ),
            {mock_indicator.name: mock_indicator.to_json.return_value},
        )
        get_sql_condition.assert_called_once_with(
            "cdbpcs_task_indicators_v",
            ("cdb_project_id", "task_id"),
            [["foo_pid", "foo_tid"], ["bar_pid", "bar_tid"]],
        )
        RecordSet2.assert_called_once_with(
            "cdbpcs_task_indicators_v", get_sql_condition.return_value
        )
        KeywordQuery.assert_called_once_with(
            rest_visible_name="project_task", name=["foo_indicator"]
        )
        mock_indicator.to_json.assert_called_once_with(
            {"foo_pid@foo_tid@": {"A": 1}, "bar_pid@bar_tid@": {"B": 2}}
        )


@pytest.mark.unit
class FilterFunctions(unittest.TestCase):
    @mock.patch.object(indicators, "DefaultToZeroFormatter")
    def Test_tasks_issues_overdue(self, DefaultToZeroFormatter):
        """Sums overdue tasks and issues."""
        mock_obj = mock.MagicMock()
        raw_data = {
            "foo": {"tasks_overdue": 1, "issues_overdue": 2, "other_key": 1},
            "bar": {"tasks_overdue": 1, "issues_overdue": 2, "other_key": "A"},
            "baz": {"tasks_overdue": 1, "issues_overdue": "A"},
            "bam": {"tasks_overdue": "A", "issues_overdue": 2},
            "bum": {"tasks_overdue": "A", "issues_overdue": "B"},
        }
        self.assertDictEqual(
            indicators.tasks_issues_overdue(mock_obj, raw_data),
            {
                "foo": {
                    "value": 3,
                    "indicator_style": "danger",
                    "additional_icon": "cdbpcs_overdue_fixed",
                },
                "bar": {
                    "value": 3,
                    "indicator_style": "danger",
                    "additional_icon": "cdbpcs_overdue_fixed",
                },
                "baz": {
                    "value": 1,
                    "indicator_style": "danger",
                    "additional_icon": "cdbpcs_overdue_fixed",
                },
                "bam": {
                    "value": 2,
                    "indicator_style": "danger",
                    "additional_icon": "cdbpcs_overdue_fixed",
                },
                "bum": {
                    "value": DefaultToZeroFormatter.return_value.format.return_value,
                    "indicator_style": "danger",
                    "additional_icon": "cdbpcs_overdue_fixed",
                },
            },
        )
        DefaultToZeroFormatter.return_value.format.assert_called_once_with(
            mock_obj.data_source_pattern, tasks_overdue="A", issues_overdue="B"
        )

    @mock.patch.object(indicators, "DefaultToZeroFormatter")
    def Test_set_indicator_style_info(self, DefaultToZeroFormatter):
        """Sets indicator styling to info and hands data through untouched."""
        mock_raw_data = {
            "foo": {"value": 1},
            "bar": {"wrong_key": 1},
            "baz": {"value": "not a number"},
        }
        mock_obj = mock.MagicMock()
        self.assertDictEqual(
            indicators.set_indicator_style_info(mock_obj, mock_raw_data),
            {
                "foo": {
                    "value": DefaultToZeroFormatter.return_value.format.return_value,
                    "indicator_style": "info",
                },
                "bar": {
                    "value": DefaultToZeroFormatter.return_value.format.return_value,
                    "indicator_style": "info",
                },
                "baz": {
                    "value": DefaultToZeroFormatter.return_value.format.return_value,
                    "indicator_style": "info",
                },
            },
        )

    @mock.patch.object(indicators, "DefaultToZeroFormatter")
    def Test_set_indicator_style_error(self, DefaultToZeroFormatter):
        """Sets indicator styling to danger and hands data through untouched."""
        mock_raw_data = {
            "foo": {"value": 1},
            "bar": {"wrong_key": 1},
            "baz": {"value": "not a number"},
        }
        mock_obj = mock.MagicMock()
        self.assertDictEqual(
            indicators.set_indicator_style_error(mock_obj, mock_raw_data),
            {
                "foo": {
                    "value": DefaultToZeroFormatter.return_value.format.return_value,
                    "indicator_style": "danger",
                },
                "bar": {
                    "value": DefaultToZeroFormatter.return_value.format.return_value,
                    "indicator_style": "danger",
                },
                "baz": {
                    "value": DefaultToZeroFormatter.return_value.format.return_value,
                    "indicator_style": "danger",
                },
            },
        )

    @mock.patch.object(indicators, "DefaultToZeroFormatter")
    def Test_set_indicator_style_project_cl_ko(self, DefaultToZeroFormatter):
        """Sets indicator styling to danger if data entry has indicator name
        and hands data through untouched."""
        # Note: 'name' cannot be set as value on a mock (protected), so no danger styling
        mock_obj = mock.MagicMock()
        mock_raw_data = {
            "foo": {"value": 1},
            "bar": {"wrong_key": 1},
            "baz": {"value": "not a number"},
        }
        self.assertDictEqual(
            indicators.set_indicator_style_project_cl_ko(mock_obj, mock_raw_data),
            {
                "foo": {
                    "value": DefaultToZeroFormatter.return_value.format.return_value,
                },
                "bar": {
                    "value": DefaultToZeroFormatter.return_value.format.return_value,
                },
                "baz": {
                    "value": DefaultToZeroFormatter.return_value.format.return_value,
                },
            },
        )


@pytest.mark.integration
class IndicatorIntegration(testcase.RollbackTestCase):
    def _create_project(self, pid, bid):
        return Project.Create(cdb_project_id=pid, ce_baseline_id=bid)

    def _create_task(self, pid, bid, tid, **kwargs):
        return Task.Create(
            cdb_project_id=pid, ce_baseline_id=bid, task_id=tid, **kwargs
        )

    def _create_issue(self, pid, iid, **kwargs):
        return Issue.Create(cdb_project_id=pid, issue_id=iid, **kwargs)

    def _create_checklist(self, pid, cid, **kwargs):
        return Checklist.Create(cdb_project_id=pid, checklist_id=cid, **kwargs)

    def _create_checklist_item(self, pid, cid, cliid, **kwargs):
        return ChecklistItem.Create(
            cdb_project_id=pid, checklist_id=cid, cl_item_id=cliid, **kwargs
        )

    def tearDown(self):
        super().tearDown()
        sqlapi.SQLdelete("FROM cdbpcs_indicator WHERE name = 'Empty'")
        sqlapi.SQLdelete("FROM cdbpcs_data_source WHERE data_source_id = 'Empty'")
        data_sources.DataSource.CompileToView("project")
        data_sources.DataSource.CompileToView("project_task")

    def _ResolveObjects(self, rest_name, ids, indicator_names, expected):
        # fill caches before measuring SQL statements
        for x in indicators.Indicator.Query(
            "label > '' and rest_visible_name='project_task'"
        ):
            indicators.util.get_label(x.label)

        if rest_name == "project":
            resolve_func = indicators.ResolveProjectIndicators
        else:
            resolve_func = indicators.ResolveTasksIndicators
        with testcase.max_sql(2):
            # 1st select to get indicator entries,
            # 2nd select to get indicator values
            result = resolve_func(
                rest_name,
                ids,
                indicator_names,
            )

        self.maxDiff = None
        self.assertDictEqual(result, expected)

    def test_ResolveObjects_project(self):
        # create an empty indicator
        empty = data_sources.DataSource.Create(data_source_id="Empty")
        empty.SetText(
            f"cdbpcs_indicator_ds_table_{sqlapi.SQLdbms()}",
            "cdbpcs_project",
        )
        empty.SetText(
            f"cdbpcs_indicator_ds_where_{sqlapi.SQLdbms()}",
            "1=2",
        )
        indicators.Indicator.Create(
            name="Empty", rest_visible_name="project", data_source_pattern="{Empty}"
        )
        data_sources.DataSource.CompileToView("project")
        self._create_project("A", "")
        self._create_checklist("A", "1", rating_id="rot")
        self._create_checklist_item("A", "1", "1", ko_criterion="1")
        self._create_issue("A", "1")
        self._create_task("A", "", "1")
        past_date = date(2020, 3, 13)
        self._create_task("A", "", "2", status=200, end_time_fcast=past_date)
        self._create_task("A", "", "3", status=0, end_time_fcast=past_date)
        self._create_task("A", "", "4", status=0, end_time_fcast=date(2500, 1, 1))

        self._create_project("B", "")
        self._create_issue("B", "1")
        self._create_issue("B", "2", status=200, priority="kritisch")
        self._create_issue("B", "3", status=0, priority="kritisch")

        self._create_project("C", "")

        project_ids = ["A", "B", "C"]
        expected = {
            "Empty": {
                "data": {
                    "A@": {"value": "0"},
                    "B@": {"value": "0"},
                    "C@": {"value": "0"},
                },
                "list_config_name": None,
                "overlay_component_name": None,
                "icon": None,
                "label": "",
            },
            "checklistitem_red_ko": {
                "data": {
                    "A@": {"value": "0"},
                    "B@": {"value": "0"},
                    "C@": {"value": "0"},
                },
                "icon": "cdbpcs_cl_item_rat_exclamation",
                "label": "Rote K.O. Kriterien",
                "list_config_name": "ChecklistItemKO",
                "overlay_component_name": "",
            },
            "issues_open": {
                "data": {
                    "A@": {"value": "0"},
                    "B@": {"value": "1"},
                    "C@": {"value": "0"},
                },
                "icon": "cdbpcs_issue",
                "label": "Offene Punkte",
                "list_config_name": "OpenIssues",
                "overlay_component_name": "",
            },
            "issues_open_critical": {
                "data": {
                    "A@": {"indicator_style": "danger", "value": "0"},
                    "B@": {"indicator_style": "danger", "value": "1"},
                    "C@": {"indicator_style": "danger", "value": "0"},
                },
                "icon": "cdbpcs_issue",
                "label": "kritische offene Punkte",
                "list_config_name": "CriticalIssues",
                "overlay_component_name": "",
            },
            "tasks_issues_overdue": {
                "data": {
                    "A@": {
                        "additional_icon": "cdbpcs_overdue_fixed",
                        "indicator_style": "danger",
                        "value": 1,
                    },
                    "B@": {
                        "additional_icon": "cdbpcs_overdue_fixed",
                        "indicator_style": "danger",
                        "value": "0",
                    },
                    "C@": {
                        "additional_icon": "cdbpcs_overdue_fixed",
                        "indicator_style": "danger",
                        "value": "0",
                    },
                },
                "list_config_name": "OverdueTasks",
                "overlay_component_name": "",
                "icon": "",
                "label": "Überfällige Aufgaben",
            },
        }
        self._ResolveObjects(
            "project",
            project_ids,
            [
                "Empty",
                "checklistitem_red_ko",
                "issues_open",
                "issues_open_critical",
                "tasks_issues_overdue",
            ],
            expected,
        )

    @pytest.mark.dependency(depends=["cs.activitystream", "cs.documents"])
    def test_ResolveObjects_project_task(self):
        from cs.activitystream.objects import Comment, SystemPosting, UserPosting
        from cs.documents import Document

        from cs.pcs.projects_documents import TaskDocumentReference

        def _post(cls, oid, **kwargs):
            if cls == Comment:
                kwargs["posting_id"] = oid
            else:
                kwargs["context_object_id"] = oid
            return cls.Create(**kwargs)

        def _create_doc(pid, tid, z_nummer, z_index):
            d = Document(z_nummer=z_nummer, z_index=z_index)
            TaskDocumentReference.Create(
                z_nummer=z_nummer,
                z_index=z_index,
                task_id=tid,
                cdb_project_id=pid,
                rel_type="doc2task",
            )
            return d

        # create empty indicator
        empty = data_sources.DataSource.Create(data_source_id="Empty")
        empty.SetText(
            f"cdbpcs_indicator_ds_table_{sqlapi.SQLdbms()}",
            "cdbpcs_task",
        )
        empty.SetText(
            f"cdbpcs_indicator_ds_where_{sqlapi.SQLdbms()}",
            "1=2",
        )
        indicators.Indicator.Create(
            name="Empty",
            rest_visible_name="project_task",
            data_source_pattern="{Empty}",
        )
        data_sources.DataSource.CompileToView("project_task")

        # create Project
        self._create_project("C", "")
        # create Task with User Post and comment
        task_c1 = self._create_task("C", "", "1")
        post_c1 = _post(UserPosting, task_c1.cdb_object_id)
        _post(Comment, post_c1.cdb_object_id)
        # create Task with System Post and comment
        task_c2 = self._create_task("C", "", "2")
        post_c2 = _post(SystemPosting, task_c2.cdb_object_id)
        _post(Comment, post_c2.cdb_object_id)
        # create task without AS threads but with checklist
        self._create_task("C", "", "3")
        self._create_checklist("C", "1", task_id="3")
        # create Task with issues (two not open, one open)
        self._create_task("C", "", "4")
        self._create_issue("C", "1", status="200", task_id="4")
        self._create_issue("C", "2", status="180", task_id="4")
        self._create_issue("C", "3", status="0", task_id="4")
        # create a Task with a document
        self._create_task("C", "", "5")
        _create_doc("C", "5", "doc", "d1")

        task_ids = [("C", "1"), ("C", "2"), ("C", "3"), ("C", "4"), ("C", "5")]
        expected = {
            "Empty": {
                "data": {
                    "C@1@": {"value": "0"},
                    "C@3@": {"value": "0"},
                    "C@4@": {"value": "0"},
                },
                "list_config_name": None,
                "overlay_component_name": None,
                "icon": None,
                "label": "",
            },
            "activities_threads": {
                "data": {
                    "C@1@": {"value": "1"},
                    "C@3@": {"value": "0"},
                    "C@4@": {"value": "0"},
                },
                "list_config_name": "Postings",
                "overlay_component_name": None,
                "icon": "cdbblog_comment",
                "label": "Aktivitäten",
            },
            "issues_open": {
                "data": {
                    "C@1@": {"value": "0"},
                    "C@3@": {"value": "0"},
                    "C@4@": {"value": "1"},
                },
                "list_config_name": "OpenIssues4Tasks",
                "overlay_component_name": None,
                "icon": "cdbpcs_issue",
                "label": "Offene Punkte",
            },
            "documents": {
                "data": {
                    "C@1@": {"value": "0"},
                    "C@3@": {"value": "0"},
                    "C@4@": {"value": "0"},
                },
                "list_config_name": "Documents",
                "overlay_component_name": "",
                "icon": "cdb_document",
                "label": "Dokumente",
            },
            "checklists": {
                "data": {
                    "C@1@": {"value": "0"},
                    "C@3@": {"value": "1"},
                    "C@4@": {"value": "0"},
                },
                "icon": "cdbpcs_checkl",
                "label": "Checklisten",
                "list_config_name": "Checklists",
                "overlay_component_name": "",
            },
        }

        self._ResolveObjects(
            "project_task",
            task_ids,
            [
                "activities_threads",
                "checklists",
                "documents",
                "issues_open",
                "Empty",
            ],
            expected,
        )


if __name__ == "__main__":
    unittest.main()
