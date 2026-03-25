#!/usr/bin/env python
# coding: utf-8
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
# pylint: disable=W0212

import unittest

import mock
from cdb import sqlapi, testcase, util

from cs.objectdashboard.config import DashboardConfig, DashboardDefaultConfig
from cs.objectdashboard.dashboard_setup import (
    DashboardDefault,
    _copy_objects_referenced_by_dashboard_config,
)
from cs.pcs.projects import Project


@mock.patch("cs.objectdashboard.dashboard_setup.sig")
def test___copy_objects_referenced_by_dashboard_config(signal):
    copied_obj = mock.MagicMock()
    copied_obj.SetText = mock.MagicMock()
    referenced_obj = mock.MagicMock()
    referenced_obj.GetText.return_value = "text_value"
    referenced_obj.GetTextFieldNames.return_value = ["text_name"]
    referenced_obj.Copy.return_value = copied_obj
    referenced_class = mock.MagicMock()
    referenced_class.KeywordQuery.return_value = [referenced_obj]
    signal.emit.return_value = mock.MagicMock(return_value=[referenced_class])

    default_conf = mock.PropertyMock(cdb_object_id="def_id")
    new_conf = mock.PropertyMock(cdb_object_id="new_id")

    _copy_objects_referenced_by_dashboard_config(default_conf, new_conf)

    signal.emit.assert_called_once()
    referenced_class.KeywordQuery.assert_called_with(cdb_config_id="def_id")
    referenced_obj.Copy.assert_called_with(cdb_config_id="new_id")
    copied_obj.SetText.assert_called_with("text_name", "text_value")


class DashboardDefaultTest(testcase.RollbackTestCase):
    def test_references(self):
        config = DashboardDefault.Create(classname="foo")
        entry_a = DashboardDefaultConfig.Create(
            cdb_object_id="A",
            context_object_id=config.cdb_object_id,
        )
        entry_b = DashboardDefaultConfig.Create(
            cdb_object_id="B",
            context_object_id=config.cdb_object_id,
        )
        self.assertEqual(
            set(config.ConfigEntries.cdb_object_id),
            set([entry_a.cdb_object_id, entry_b.cdb_object_id]),
        )

    def test_get_template_classname(self):
        for classname in [None, "", "foo"]:
            config = DashboardDefault(classname=classname)
            self.assertEqual(config.get_template_classname(), config.classname)

    def test_get_empty_context_object_ids_classname_None(self):
        broken_config = DashboardDefault(classname=None)
        with self.assertRaises(util.ErrorMessage):
            broken_config._get_empty_context_object_ids()

    def test_get_empty_context_object_ids_classname_unknown(self):
        broken_config = DashboardDefault(classname="does not exist")
        with self.assertRaises(util.ErrorMessage):
            broken_config._get_empty_context_object_ids()

    def test_get_empty_context_object_ids_project(self):
        table_name = classname = "cdbpcs_project"
        sqlapi.SQLdelete(f"FROM {table_name}")
        config = DashboardDefault(classname=classname)
        has = Project.Create(
            cdb_object_id="has",
            cdb_project_id="has",
            ce_baseline_id="has_bid",
        )
        has_not = Project.Create(
            cdb_object_id="has not",
            cdb_project_id="has not",
            ce_baseline_id="has not bid",
        )
        DashboardConfig.Create(
            cdb_object_id="A",
            context_object_id=has.cdb_object_id,
        )
        self.assertEqual(
            set(config._get_empty_context_object_ids()), set([has_not.cdb_object_id])
        )

    def test_on_cs_objdashboard_apply_default_now_empty(self):
        ctx = mock.MagicMock()  # cdbscript is not speccable
        config = DashboardDefault(classname="foo")
        config.on_cs_objdashboard_apply_default_now(ctx)
        ctx.MessageBox.assert_not_called()

    @mock.patch(
        "cs.objectdashboard.dashboard_setup._copy_objects_referenced_by_dashboard_config"
    )
    @mock.patch.object(DashboardDefaultConfig, "MakeChangeControlAttributes")
    @mock.patch.object(DashboardConfig, "Create")
    def test_on_cs_objdashboard_apply_default_now(self, CreateConfig, MCCA, CopyRef):
        amount = 10
        MCCA.return_value = {"cdb_cpersno": "PERSNO", "foo": "bar"}
        CreateConfig.return_value = "foo"
        ctx = mock.MagicMock()  # cdbscript is not speccable
        config = DashboardDefault(
            cdb_object_id="foo",
            classname="foo",
        )
        entry = DashboardDefaultConfig.Create(context_object_id=config.cdb_object_id)
        config._get_empty_context_object_ids = lambda: list(range(amount))
        config.on_cs_objdashboard_apply_default_now(ctx)
        CreateConfig.assert_has_calls(
            [
                mock.call(
                    cdb_cpersno="PERSNO",
                    cdb_module_id=None,
                    component_name=None,
                    context_object_id=i,
                    settings=None,
                    xpos=None,
                    ypos=None,
                    foo="bar",
                )
                for i in range(amount)
            ],
            any_order=False,
        )
        CopyRef.assert_has_calls(
            [mock.call(entry, "foo") for i in range(amount)], any_order=False
        )

        ctx.MessageBox.assert_called_with(
            "cs_objdashboard_applied_default",
            [amount],
            "applied_defaults",
            ctx.MessageBox.kMsgBoxIconInformation,
        )


class WithDefaultDashboardTest(testcase.RollbackTestCase):
    @mock.patch(
        "cs.objectdashboard.dashboard_setup._copy_objects_referenced_by_dashboard_config"
    )
    @mock.patch.object(DashboardConfig, "KeywordQuery")
    def test_create_default_widgets_template(self, KWQuery, CopyRef):
        templateConfig = mock.MagicMock()
        newConfig = mock.MagicMock()
        templateConfig.Copy = mock.MagicMock(return_value=newConfig)
        KWQuery.return_value = [templateConfig]
        ctx = mock.MagicMock()
        ctx.cdbtemplate = mock.PropertyMock(cdb_object_id="foo")
        project = Project.Create(
            cdb_object_id="bar",
            cdb_project_id="bar",
            ce_baseline_id="",
        )
        project.has_obj_dashboard_config = mock.MagicMock(return_value=True)
        project._get_default_dashboard_widgets = mock.MagicMock()
        project._create_default_widgets(ctx)
        KWQuery.assert_called_with(context_object_id="foo")
        templateConfig.Copy.assert_called_with(context_object_id="bar")
        CopyRef.assert_called_with(templateConfig, newConfig)

    @mock.patch(
        "cs.objectdashboard.dashboard_setup._copy_objects_referenced_by_dashboard_config"
    )
    @mock.patch.object(DashboardConfig, "create_from_description")
    def test_create_default_widgets_no_template(self, create_from_desc, CopyRef):
        project = Project.Create(
            cdb_object_id="foo",
            cdb_project_id="foo",
            ce_baseline_id="",
        )
        project._get_default_dashboard_widgets = mock.MagicMock(return_value="AB")
        default_config = mock.PropertyMock(
            component_name="component_name",
            settings="settings",
            xpos="xpos",
            ypos="ypos",
        )
        new_config = mock.MagicMock()
        create_from_desc.return_value = new_config
        with mock.patch.object(
            DashboardDefault,
            "ByKeys",
            return_value=mock.PropertyMock(ConfigEntries=[default_config]),
        ):
            project._create_default_widgets()
        create_from_desc.assert_called_with(
            {
                "component_name": "component_name",
                "settings": "settings",
                "xpos": "xpos",
                "ypos": "ypos",
            },
            "foo",
        )
        CopyRef.assert_called_with(default_config, new_config)

    def test_has_obj_dashboard_config_False(self):
        project = Project.Create(
            cdb_object_id="foo",
            cdb_project_id="foo",
            ce_baseline_id="",
        )
        DashboardConfig.Create(context_object_id="")
        self.assertEqual(project.has_obj_dashboard_config(None), False)
        self.assertEqual(project.has_obj_dashboard_config(""), False)
        self.assertEqual(project.has_obj_dashboard_config("unknown context"), False)

    def test_has_obj_dashboard_config_True(self):
        project = Project.Create(
            cdb_object_id="foo",
            cdb_project_id="foo",
            ce_baseline_id="",
        )
        DashboardConfig.Create(context_object_id="bar")
        self.assertEqual(project.has_obj_dashboard_config("bar"), True)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
