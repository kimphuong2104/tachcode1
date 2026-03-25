#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=W0212

import json
import mock
import unittest

import pytest
from cdb import sqlapi, testcase, ue
from cdb.constants import kOperationCopy, kOperationNew
from cdb.objects.operations import operation

from cs.objectdashboard import config
from cs.objectdashboard.config import (
    DashboardConfig,
    DashboardDefaultConfig,
    DefaultKPIsThreshold,
    Widget,
)
from cs.objectdashboard.dashboard_setup import DashboardDefault
from cs.pcs.projects import Project


class DashboardConfigTest(testcase.RollbackTestCase):
    def test_get_config(self):
        for name, xpos, ypos in [
            ("B", 0, 1),
            ("C", 0, 1),
            ("D", 1, 0),
            ("A", 0, 0),
        ]:
            DashboardConfig.Create(
                context_object_id="foo", component_name=name, xpos=xpos, ypos=ypos
            )
        component_name_att = []
        for i in DashboardConfig.get_config("foo"):
            component_name_att.append(i.component_name)
        self.assertEqual(component_name_att, ["A", "B", "C", "D"])

    def test_create_from_description(self):
        """
        Successful creation of a single dashboard config entry
        """
        entry = DashboardConfig.create_from_description(
            {
                "component_name": "NAME",
                "settings": "SETTINGS",
            },
            "foo",
        )
        self.assertEqual(entry.context_object_id, "foo")
        self.assertEqual(entry.component_name, "NAME")
        self.assertEqual(entry.settings, "SETTINGS")

    def test_check_once_only_ok(self):
        Widget.Create(comp_path="foo", once_only=1)
        entry = DashboardConfig(component_name="foo")
        entry._check_once_only(None)

    def test_check_once_only_not_ok(self):
        Widget.Create(comp_path="foo", once_only=1)
        DashboardConfig.Create(
            component_name="foo",
            context_object_id="bar",
        )
        entry = DashboardConfig(
            component_name="foo",
            context_object_id="bar",
        )
        with self.assertRaises(ue.Exception):
            entry._check_once_only(None)


class WidgetTest(testcase.RollbackTestCase):
    def test_ByClassname(self):
        Widget.Create(comp_path="bar")
        self.assertEqual(Widget.ByClassname("foo").comp_path, [])
        sqlapi.Record(
            "cs_objdashboard_widget_appl",
            classname="foo",
            comp_path="bar",
        ).insert()
        self.assertEqual(Widget.ByClassname("foo").comp_path, ["bar"])

    def test_get_libraries(self):
        Widget.Query().Delete()
        self.assertEqual(Widget.get_libraries(), [])
        expected = [
            ("A", "a"),
            ("A", "a"),
            ("B", "b"),
        ]
        for i, vals in enumerate(expected):
            name, version = vals
            Widget.Create(
                comp_path=f"foo-{i}",
                library_name=name,
                library_version=version,
            )
        self.assertEqual(Widget.get_libraries(), expected)


# (these are acceptance tests)
class TemplateMechanismTest(testcase.RollbackTestCase):
    def setUp(self):
        super().setUp()
        self.widget_one = {
            "component_name": "dashboard",
            "settings": "{'layout': 'm'}",
        }
        self.widget_two = {
            "component_name": "cs-activitystream-web-ObjectActivitiesBlock",
            "settings": "",
            "xpos": "1",
            "ypos": "1",
        }

        self.widgets = [self.widget_one, self.widget_two]
        # Delete current default configuration to make sure that the templates
        # do not get default config already
        self._delete_current_default_cfg()
        self._setup_templates()
        self._setup_dashboard_config(self.template_with_cfg.cdb_object_id)
        self.assertIsNotNone(
            self.template_without_cfg,
            "Template without dashboard has not been created.",
        )
        self.assertIsNotNone(
            self.template_with_cfg, "Template with dashboard has not been created."
        )
        self._setup_default_dashboard_cfg()
        self.assertIsNotNone(
            self.default_config, "Default config root has not been created."
        )
        self.assertIsNotNone(
            self.default_widget, "Default widget has not been created."
        )

    def _setup_templates(self):
        self.template_without_cfg = operation(
            kOperationNew,
            Project,
            cdb_project_id="#1",
            ce_baseline_id="",
            project_name="Template Without Dashboard Config",
            template=1,
        )

        self.template_with_cfg = operation(
            kOperationNew,
            Project,
            cdb_project_id="#2",
            ce_baseline_id="",
            project_name="Template With Dashboard Config",
            template=1,
        )

    @staticmethod
    def _delete_current_default_cfg():
        current_default = DashboardDefault.ByKeys(classname="cdbpcs_project")
        if current_default:
            current_default.Delete()

    def _setup_default_dashboard_cfg(self):
        default_config_root = operation(
            kOperationNew, DashboardDefault, classname="cdbpcs_project"
        )
        self.default_config = default_config_root
        default_widget = {
            "component_name": "DEFAULT",
            "settings": "",
        }
        self.default_widget = DashboardDefaultConfig.create_from_description(
            default_widget, default_config_root.cdb_object_id
        )

    def _setup_dashboard_config(self, context_object_id):
        for widget in self.widgets:
            DashboardConfig.create_from_description(widget, context_object_id)

    def test_create_project(self):
        """
        Project creation (without project template) with default dashboard
        config present.
        """
        new_project = operation(
            kOperationNew,
            Project,
            cdb_project_id="Test #1",
            ce_baseline_id="",
            project_name="Test Project",
        )
        created_config_entries = DashboardConfig.KeywordQuery(
            context_object_id=new_project.cdb_object_id
        )
        self.assertNotEqual(
            created_config_entries, [], "No config entries created at all."
        )
        self.assertEqual(
            len(created_config_entries),
            1,
            "More then one default config entry got created.",
        )
        self.assertEqual(
            created_config_entries[0].component_name,
            self.default_widget.component_name,
            "Wrong default config entry has been created",
        )

    def test_create_project_from_template_with_cfg(self):
        """
        Project creation from template with template having a dashboard
        configuration (2 entries).
        """
        args = {
            "cdb_project_id": "Test #2",
            "ce_baseline_id": "",
            "project_name": "Test Project #2",
            "template": 0,
        }
        copied_project = operation(kOperationCopy, self.template_with_cfg, **args)
        created_config_entries = DashboardConfig.KeywordQuery(
            context_object_id=copied_project.cdb_object_id
        )
        self.assertNotEqual(
            created_config_entries, [], "No config entries created at all."
        )
        self.assertEqual(
            len(created_config_entries),
            2,
            f"More than 2 config entries created: {len(created_config_entries)}",
        )
        widget_names = [x["component_name"] for x in self.widgets]
        self.assertIn(
            created_config_entries[0].component_name,
            widget_names,
            f"Widget with component_name {created_config_entries[0].component_name}"
            " was not included in test data.",
        )
        self.assertIn(
            created_config_entries[1].component_name,
            widget_names,
            f"Widget with component_name {created_config_entries[1].component_name} "
            "was not included in test data.",
        )

    def test_create_project_from_template_without_cfg(self):
        """
        Project creation from template with template NOT having a dashboard
        configuration but a default configuration is present (1 entry).
        """
        args = {"cdb_project_id": "Test #3", "ce_baseline_id": "", "template": 0}
        copied_project = operation(kOperationCopy, self.template_without_cfg, **args)
        created_config_entries = DashboardConfig.KeywordQuery(
            context_object_id=copied_project.cdb_object_id
        )
        self.assertNotEqual(
            created_config_entries, [], "No config entries created at all."
        )
        self.assertEqual(
            len(created_config_entries),
            1,
            f"More than 1 default config created: {len(created_config_entries)}",
        )
        self.assertEqual(
            created_config_entries[0].component_name,
            self.default_widget.component_name,
            "Wrong default config entry has been created",
        )

    def test_create_project_from_template_without_cfg_without_default(self):
        """
        Project creation from template with template NOT having a dashboard
        configuration and no default configuration is present
        """
        # Prepare data by deleting current default configuration used by other
        # scenarios
        self._delete_current_default_cfg()
        # TODO: test mit template ohne temaplate cfg und ohne globalen default
        args = {"cdb_project_id": "Test #4", "ce_baseline_id": "", "template": 0}
        copied_project = operation(kOperationCopy, self.template_without_cfg, **args)
        created_config_entries = DashboardConfig.KeywordQuery(
            context_object_id=copied_project.cdb_object_id
        )
        self.assertEqual(
            created_config_entries,
            [],
            "Some config entries created. Should have been none",
        )


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()


def setUpModule():
    "ensure DB connection is available"
    testcase.run_level_setup()


@pytest.mark.unit
class TestProject(unittest.TestCase):
    @pytest.mark.unit
    def test_threshold_success_and_danger_not_equal(self):
        """Testing that success and danger threshold are not equal"""
        dashboard_kpi = mock.MagicMock(spec=DefaultKPIsThreshold)
        dashboard_kpi.success_threshold = 0.5
        dashboard_kpi.danger_threshold = 0.5

        with self.assertRaises(ue.Exception) as error:
            DefaultKPIsThreshold._check_thresholds(dashboard_kpi, None)

        self.assertEqual(
            str(error.exception), str(ue.Exception("kpi_threshold_error2"))
        )

    @pytest.mark.unit
    def test_success_bigger_than_danger_threshold(self):
        """Testing that success threshold is bigger than danger threshold"""
        dashboard_kpi = mock.MagicMock(spec=DefaultKPIsThreshold)
        dashboard_kpi.success_threshold = 0.1
        dashboard_kpi.danger_threshold = 0.9

        with self.assertRaises(ue.Exception) as error:
            DefaultKPIsThreshold._check_thresholds(dashboard_kpi, None)

        self.assertEqual(
            str(error.exception), str(ue.Exception("kpi_threshold_error1"))
        )

    @pytest.mark.unit
    def test_danger_threshold_not_negative(self):
        """Testing that danger threshold is not negative"""
        dashboard_kpi = mock.MagicMock(spec=DefaultKPIsThreshold)
        dashboard_kpi.success_threshold = 0.4
        dashboard_kpi.danger_threshold = -0.4

        with self.assertRaises(ue.Exception) as error:
            DefaultKPIsThreshold._check_thresholds(dashboard_kpi, None)

        self.assertEqual(
            str(error.exception), str(ue.Exception("kpi_threshold_error4"))
        )

    @pytest.mark.unit
    def test_success_threshold_not_greater_than_one(self):
        """Testing that success threshold are greater than one"""
        dashboard_kpi = mock.MagicMock(spec=DefaultKPIsThreshold)
        dashboard_kpi.success_threshold = 1.4
        dashboard_kpi.danger_threshold = 0.4

        with self.assertRaises(ue.Exception) as error:
            DefaultKPIsThreshold._check_thresholds(dashboard_kpi, None)

        self.assertEqual(
            str(error.exception), str(ue.Exception("kpi_threshold_error3"))
        )


@pytest.mark.unit
class TestDefaultKPI(unittest.TestCase):
    @pytest.mark.unit
    @mock.patch.object(DashboardConfig, "Query")
    @mock.patch.object(DefaultKPIsThreshold, "ByKeys")
    def test_SPI_are_called(self, ByKeys, Query):
        """Testing that SPI default values are called for InTime tiles"""
        SPI_threshold = mock.MagicMock(
            spec=DefaultKPIsThreshold,
            kpi_name="SPI",
            success_threshold=0.91,
            danger_threshold=0.12,
        )

        config_settings = '{"configuration": [{"tile": "cs-pcs-widgets-InTime"}]}'
        real_dict = {
            "context_object_id": "foo",
            "component_name": "cs-pcs-widgets-ProjectRadar",
            "settings": config_settings,
        }

        def getitem(name):
            return real_dict[name]

        # mock dict with get item method
        configuration_test = mock.MagicMock()
        configuration_test.__getitem__.side_effect = getitem
        configuration_test = [configuration_test]

        Query.return_value = configuration_test
        ByKeys.side_effect = [SPI_threshold, SPI_threshold]

        config_return = DashboardConfig.get_config(None)

        self.assertEqual(
            json.loads(config_return[0].settings)["configuration"][0]["args"],
            [0.91, 0.12],
        )

    @mock.patch.object(DashboardConfig, "Query")
    @mock.patch.object(DefaultKPIsThreshold, "ByKeys")
    def test_CPI_are_called(self, ByKeys, Query):
        """Testing that CPI default values are called for InBudget tiles"""
        CPI_threshold = mock.MagicMock(
            spec=DefaultKPIsThreshold,
            kpi_name="CPI",
            success_threshold=0.81,
            danger_threshold=0.22,
        )

        config_settings = '{"configuration": [{"tile": "cs-pcs-widgets-InBudget"}]}'
        real_dict = {
            "context_object_id": "foo",
            "component_name": "cs-pcs-widgets-ProjectRadar",
            "settings": config_settings,
        }

        def getitem(name):
            return real_dict[name]

        # mock dict with get item method
        configuration_test = mock.MagicMock()
        configuration_test.__getitem__.side_effect = getitem
        configuration_test = [configuration_test]

        Query.return_value = configuration_test
        ByKeys.side_effect = [CPI_threshold, CPI_threshold]

        config_return = DashboardConfig.get_config(None)

        self.assertEqual(
            json.loads(config_return[0].settings)["configuration"][0]["args"],
            [0.81, 0.22],
        )

    @mock.patch.object(DashboardConfig, "Query")
    @mock.patch.object(DefaultKPIsThreshold, "ByKeys")
    def test_CPI_SPI_are_called(self, ByKeys, Query):
        """Testing that CPI default values are called for InBudget tiles
        and SPI default values are called for InTime tiles"""
        CPI_threshold = mock.MagicMock(
            spec=DefaultKPIsThreshold,
            kpi_name="CPI",
            success_threshold=0.81,
            danger_threshold=0.22,
        )

        SPI_threshold = mock.MagicMock(
            spec=DefaultKPIsThreshold,
            kpi_name="SPI",
            success_threshold=0.91,
            danger_threshold=0.12,
        )

        config_settings = (
            '{"configuration": [{"tile": "cs-pcs-widgets-InTime", "args": [0.6, 0.4]}, '
            '{"tile": "cs-pcs-widgets-InBudget"}]}'
        )
        real_dict = {
            "context_object_id": "foo",
            "component_name": "cs-pcs-widgets-ProjectRadar",
            "settings": config_settings,
        }

        def getitem(name):
            return real_dict[name]

        # mock dict with get item method
        configuration_test = mock.MagicMock()
        configuration_test.__getitem__.side_effect = getitem
        configuration_test = [configuration_test]

        Query.return_value = configuration_test
        ByKeys.side_effect = [
            SPI_threshold,
            SPI_threshold,
            CPI_threshold,
            CPI_threshold,
        ]

        config_return = DashboardConfig.get_config(None)

        self.assertEqual(
            json.loads(config_return[0].settings)["configuration"][0]["args"],
            [0.91, 0.12],
        )
        self.assertEqual(
            json.loads(config_return[0].settings)["configuration"][1]["args"],
            [0.81, 0.22],
        )

    @mock.patch.object(DashboardConfig, "Query")
    def test_if_no_intile_inbudget_tile(self, Query):
        """Testing The configuration is valid if no intile and inbudget tiles"""

        config_settings = (
            '{"configuration": [{"tile": "cs-pcs-widgets-RemainingTime"}, '
            '{"tile": "cs-pcs-widgets-Rating"},'
            '{"tile": "cs-pcs-widgets-UnassignedRoles"}]}'
        )
        real_dict = {
            "context_object_id": "foo",
            "component_name": "cs-pcs-widgets-ProjectRadar",
            "settings": config_settings,
        }

        def getitem(name):
            return real_dict[name]

        # mock dict with get item method
        configuration_test = mock.MagicMock()
        configuration_test.__getitem__.side_effect = getitem
        configuration_test = [configuration_test]

        Query.return_value = configuration_test

        config_return = DashboardConfig.get_config(None)

        self.assertEqual(
            json.loads(config_return[0].settings), json.loads(config_settings)
        )

    @mock.patch.object(config, "auth", persno="foo")
    @mock.patch.object(config, "logging")
    @mock.patch.object(DashboardConfig, "Query", return_value=[])
    def test_get_config_no_access(self, Query, logging, persno):
        """Testing No config is returned if read access not granted"""

        config_return = DashboardConfig.get_config(None)
        self.assertEqual([], config_return)

        logging.exception.assert_called_once_with(
            "'%s' has no read access on Global KPIS thresholds", "foo"
        )


if __name__ == "__main__":
    unittest.main()
