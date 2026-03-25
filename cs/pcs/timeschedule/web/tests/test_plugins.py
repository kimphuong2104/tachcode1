#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# pylint: disable=protected-access,disallowed-name

import unittest

import pytest
from mock import MagicMock, call, patch

from cs.pcs.timeschedule.web import plugins


@pytest.mark.unit
class TimeSchedulePlugin(unittest.TestCase):
    @patch.object(
        plugins.TimeSchedulePlugin, "__required_strings__", ["foo", "bar", "baz"]
    )
    @patch.object(
        plugins.TimeSchedulePlugin, "__required_string_tuples__", ["boo", "far", "faz"]
    )
    def test_Validate_fail(self):
        "validation fails if attributes are missing or of wrong type"

        class Plugin(plugins.TimeSchedulePlugin):
            foo = None
            # bar does not exist
            baz = "OK"
            boo = (None, None)
            # far does not exist
            faz = ("Okee", "lee", "dokelee")

        self.assertFalse(hasattr(Plugin, "bar"))
        self.assertFalse(hasattr(Plugin, "far"))

        with self.assertRaises(ValueError) as error:
            Plugin.Validate()

        self.assertTrue(
            "missing attributes (or of wrong type):\n\tfoo, bar, boo, far"
            in error.exception.args
        )

    @patch.object(plugins.TimeSchedulePlugin, "__required_strings__", ["foo", "bar"])
    @patch.object(
        plugins.TimeSchedulePlugin, "__required_string_tuples__", ["boo", "far"]
    )
    def test_Validate_ok(self):
        "validation succeeds if attributes are valid"

        class Plugin(plugins.TimeSchedulePlugin):
            foo = "Yes"
            bar = "OK"
            boo = ("Also", "OK")
            far = ("Workin' just fine",)

        self.assertEqual(Plugin.Validate(), None)

    def test_GetRequiredFields_missing_attrs(self):
        "fails if attrs are not iterable"
        with self.assertRaises(TypeError) as error:
            plugins.TimeSchedulePlugin.GetRequiredFields()

        self.assertEqual("'NoneType' object is not iterable", str(error.exception))

    @patch.object(plugins.TimeSchedulePlugin, "olc_attr", "OLC")
    @patch.object(plugins.TimeSchedulePlugin, "status_attr", "status")
    @patch.object(plugins.TimeSchedulePlugin, "icon_attrs", ("i", "i", "I"))
    @patch.object(plugins.TimeSchedulePlugin, "description_attrs", ("d", "D"))
    @patch.object(plugins.TimeSchedulePlugin, "subject_id_attr", "sid")
    @patch.object(plugins.TimeSchedulePlugin, "subject_type_attr", "stype")
    def test_GetRequiredFields(self):
        "returns set of required field names"
        self.assertEqual(
            plugins.TimeSchedulePlugin.GetRequiredFields(),
            set(["OLC", "status", "i", "I", "d", "D", "sid", "stype"]),
        )

    def test_ResolveStructure(self):
        with self.assertRaises(ValueError):
            plugins.TimeSchedulePlugin.ResolveStructure("foo", "request")

    @patch.object(plugins.TimeSchedulePlugin, "olc_attr", "foo")
    def test_GetObjectKind_missing_attr(self):
        "fails if olc_attr is missing"
        with self.assertRaises(KeyError) as error:
            plugins.TimeSchedulePlugin.GetObjectKind({"foo_": "bar"})

        self.assertEqual("'foo'", str(error.exception))

    @patch.object(plugins.TimeSchedulePlugin, "olc_attr", "foo")
    def test_GetObjectKind(self):
        "returns record's value of olc_attr"
        self.assertEqual(
            plugins.TimeSchedulePlugin.GetObjectKind({"foo": "bar", "baz": "boo"}),
            "bar",
        )

    @patch.object(plugins.TimeSchedulePlugin, "classname", "foo")
    @patch.object(plugins, "_LabelValueAccessor")
    @patch.object(plugins, "IconCache")
    @patch.object(plugins, "CDBClassDef")
    def test_GetObjectIcon(self, CDBClassDef, IconCache, _LabelValueAccessor):
        "succeeds if plugin.classname is defined"
        mock_record = MagicMock(get=MagicMock(return_value=None))
        self.assertEqual(
            plugins.TimeSchedulePlugin.GetObjectIcon(mock_record),
            IconCache.getIcon.return_value,
        )
        CDBClassDef.assert_called_once_with("foo")
        CDBClassDef.return_value.getObjectIconId.assert_called_once()
        IconCache.getIcon.assert_called_once_with(
            CDBClassDef.return_value.getObjectIconId.return_value,
            accessor=_LabelValueAccessor.return_value,
        )
        _LabelValueAccessor.assert_called_once_with(mock_record)

    @patch.object(plugins, "_LabelValueAccessor")
    @patch.object(plugins, "IconCache")
    @patch.object(plugins, "CDBClassDef")
    def test_GetObjectIcon_subclass(self, CDBClassDef, IconCache, _LabelValueAccessor):
        "succeeds if icon of subclass is retrieved"
        mock_record = MagicMock(get=MagicMock(return_value="foo"))
        self.assertEqual(
            plugins.TimeSchedulePlugin.GetObjectIcon(mock_record),
            IconCache.getIcon.return_value,
        )
        CDBClassDef.assert_called_once_with("foo")
        CDBClassDef.return_value.getObjectIconId.assert_called_once()
        IconCache.getIcon.assert_called_once_with(
            CDBClassDef.return_value.getObjectIconId.return_value,
            accessor=_LabelValueAccessor.return_value,
        )
        _LabelValueAccessor.assert_called_once_with(mock_record)

    @patch.object(plugins.TimeSchedulePlugin, "description_attrs", [])
    @patch.object(plugins.TimeSchedulePlugin, "description_pattern", "{}")
    def test_GetDescription_missing_arg(self):
        "fails if description_attrs do not satisfy description_pattern"
        with self.assertRaises(IndexError) as error:
            plugins.TimeSchedulePlugin.GetDescription(None)

        self.assertEqual(
            "Replacement index 0 out of range for positional args tuple",
            str(error.exception),
        )

    @patch.object(plugins.TimeSchedulePlugin, "description_attrs", ["b"])
    def test_GetDescription_missing_attr(self):
        "fails if description_attr is missing"
        with self.assertRaises(KeyError) as error:
            plugins.TimeSchedulePlugin.GetDescription({"a": "A"})

        self.assertEqual("'b'", str(error.exception))

    @patch.object(plugins.TimeSchedulePlugin, "description_attrs", ["a", "b"])
    @patch.object(plugins.TimeSchedulePlugin, "description_pattern")
    def test_GetDescription(self, description_pattern):
        "succeeds with correct configuration"
        self.assertEqual(
            plugins.TimeSchedulePlugin.GetDescription({"a": "A", "b": "B", "c": "C"}),
            description_pattern.format.return_value,
        )
        description_pattern.format.assert_called_once_with("A", "B")

    @patch.object(plugins.TimeSchedulePlugin, "subject_id_attr", "sid")
    @patch.object(plugins.TimeSchedulePlugin, "subject_type_attr", "stype")
    def test_GetResponsible_missing_attr(self):
        "returns empty strings if record is missing a subject key"
        self.assertEqual(
            plugins.TimeSchedulePlugin.GetResponsible(
                {
                    "subject_id": "?",
                    "stype": "bar",
                }
            ),
            {
                "subject_id": "",
                "subject_type": "bar",
            },
        )
        self.assertEqual(
            plugins.TimeSchedulePlugin.GetResponsible(
                {
                    "subject_id": "?",
                    "sid": "foo",
                }
            ),
            {
                "subject_id": "foo",
                "subject_type": "",
            },
        )

    @patch.object(plugins.TimeSchedulePlugin, "subject_id_attr", "sid")
    @patch.object(plugins.TimeSchedulePlugin, "subject_type_attr", "stype")
    def test_GetResponsible(self):
        "returns responsible info"
        self.assertEqual(
            plugins.TimeSchedulePlugin.GetResponsible(
                {
                    "subject_id": "?",
                    "sid": "foo",
                    "stype": "bar",
                }
            ),
            {
                "subject_id": "foo",
                "subject_type": "bar",
            },
        )

    def test__GetCatalogQuery_no_pid(self):
        "returns empty dict if schedule is not assigned to a project"
        schedule = MagicMock(cdb_project_id=None)
        self.assertEqual(plugins.TimeSchedulePlugin._GetCatalogQuery(schedule), {})

    def test__GetCatalogQuery(self):
        "returns project's ID if schedule is assigned to one"
        schedule = MagicMock()
        self.assertEqual(
            plugins.TimeSchedulePlugin._GetCatalogQuery(schedule),
            {"cdb_project_id": schedule.cdb_project_id},
        )

    @patch.object(plugins.TimeSchedulePlugin, "_GetCatalogQuery")
    @patch.object(plugins.TimeSchedulePlugin, "catalog_name", "catalog name")
    @patch.object(plugins.FormInfoBase, "get_catalog_config")
    def test_GetCatalogConfig(self, get_catalog_config, _GetCatalogQuery):
        "returns configuration required to render frontend catalog"
        self.assertEqual(
            plugins.TimeSchedulePlugin.GetCatalogConfig("sched", "req"),
            get_catalog_config.return_value,
        )
        get_catalog_config.assert_called_once_with(
            "req",
            "catalog name",
            False,
            True,
        )
        _GetCatalogQuery.assert_called_once_with("sched")
        get_catalog_config.return_value.__setitem__.assert_called_once_with(
            "formData", _GetCatalogQuery.return_value
        )

    def test_GetClassReadOnlyFields(self):
        self.assertEqual(plugins.TimeSchedulePlugin.GetClassReadOnlyFields(), [])

    def test_GetObjectReadOnlyFields(self):
        self.assertEqual(plugins.TimeSchedulePlugin.GetObjectReadOnlyFields("oids"), {})


@pytest.mark.unit
class WithTimeSchedulePlugin(unittest.TestCase):
    @patch.object(plugins.logging, "error", autospec=True)
    def test__register_invalid(self, error):
        "logs error if plugin is invalid"
        plugin = MagicMock()
        plugin.Validate.side_effect = ValueError("foo")
        with_plugin = plugins.WithTimeSchedulePlugin()
        with_plugin._register_plugin(plugin)
        plugin.Validate.assert_called_once_with()
        error.assert_has_calls(
            [
                call(
                    "ignoring broken timeschedule plugin: %s (%s)",
                    plugin.Validate.side_effect,
                    plugin,
                )
            ]
        )

    @patch.object(plugins.logging, "error", autospec=True)
    def test__register_not_initialized(self, error):
        "logs error if plugin dict has not been initialized"
        plugin = MagicMock()
        with_plugin = plugins.WithTimeSchedulePlugin()
        with_plugin._register_plugin(plugin)
        plugin.Validate.assert_called_once_with()
        self.assertEqual(error.call_count, 1)
        args, _ = error.call_args
        args = (args[0], str(args[1]), args[2])

        self.assertEqual(
            args,
            (
                "ignoring broken timeschedule plugin: %s (%s)",
                "'WithTimeSchedulePlugin' object has no attribute 'plugins'",
                plugin,
            ),
        )

    @patch.object(plugins.logging, "error", autospec=True)
    def test__register(self, error):
        "registers valid plugin"
        plugin = MagicMock(table_name="foo")
        with_plugin = plugins.WithTimeSchedulePlugin()
        with_plugin.plugins = {}
        with_plugin._register_plugin(plugin)
        plugin.Validate.assert_called_once_with()
        self.assertEqual(error.call_count, 0)
        self.assertEqual(with_plugin.plugins, {"foo": plugin})

    @patch.object(plugins.sig, "emit", autospec=True)
    def test_collect_plugins(self, emit):
        "emits register callback for plugin"
        with_plugin = plugins.WithTimeSchedulePlugin()
        with_plugin.collect_plugins("foo")
        self.assertEqual(with_plugin.plugins, {})
        emit.assert_called_once_with("foo")
        emit.return_value.assert_called_once_with(with_plugin._register_plugin)


if __name__ == "__main__":
    unittest.main()
