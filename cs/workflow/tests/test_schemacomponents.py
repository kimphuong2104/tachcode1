#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import mock, datetime, unittest
from cdb import auth, testcase
from cdb.objects.operations import operation
from cs.workflow import schemacomponents


def setup_module():
    testcase.run_level_setup()


class SchemaComponent(unittest.TestCase):
    @mock.patch.object(schemacomponents.util, "get_label", autospec=True)
    @mock.patch.object(schemacomponents.os, "getenv", autospec=True,
                       return_value="True")
    def test_addActionToProtocol_simple_mode(self, getenv, get_label):
        "logging is skipped in simple mode"
        comp = mock.MagicMock(spec=schemacomponents.SchemaComponent)
        ctx = mock.MagicMock(action="create", error=None)
        self.assertIsNone(
            schemacomponents.SchemaComponent.addActionToProtocol(comp, ctx)
        )
        self.assertEqual(get_label.call_count, 0)
        self.assertEqual(comp.addProtocol.call_count, 0)
        getenv.assert_called_once_with("CS_WORKFLOW_SIMPLE_LOG_MODE", None)

    @mock.patch.object(schemacomponents.util, "get_label", autospec=True)
    @mock.patch.object(schemacomponents.os, "getenv", autospec=True,
                       return_value="")
    def test_addActionToProtocol_ctx_error(self, getenv, get_label):
        "logging is skipped if ctx.error is True"
        comp = mock.MagicMock(spec=schemacomponents.SchemaComponent)
        ctx = mock.MagicMock(action="create", error=True)
        self.assertIsNone(
            schemacomponents.SchemaComponent.addActionToProtocol(comp, ctx)
        )
        self.assertEqual(get_label.call_count, 0)
        self.assertEqual(comp.addProtocol.call_count, 0)
        getenv.assert_called_once_with("CS_WORKFLOW_SIMPLE_LOG_MODE", None)

    @mock.patch.object(schemacomponents.util, "get_label", autospec=True)
    @mock.patch.object(schemacomponents.os, "getenv", autospec=True,
                       return_value="")
    def test_addActionToProtocol_create(self, getenv, get_label):
        "action is logged for create"
        comp = mock.MagicMock(spec=schemacomponents.SchemaComponent)
        ctx = mock.MagicMock(action="create", error=None)
        self.assertIsNone(
            schemacomponents.SchemaComponent.addActionToProtocol(comp, ctx)
        )
        get_label.assert_called_once_with("cdbwf_component_add")
        comp.addProtocol.assert_called_once_with(
            get_label.return_value.format.return_value,
        )
        get_label.return_value.format.assert_called_once_with(
            comp.task_id,
            comp.title,
        )
        getenv.assert_called_once_with("CS_WORKFLOW_SIMPLE_LOG_MODE", None)

    @mock.patch.object(schemacomponents.util, "get_label", autospec=True)
    @mock.patch.object(schemacomponents.os, "getenv", autospec=True,
                       return_value="")
    def test_addActionToProtocol_copy(self, getenv, get_label):
        "action is logged for copy"
        comp = mock.MagicMock(spec=schemacomponents.SchemaComponent)
        ctx = mock.MagicMock(action="copy", error=None)
        self.assertIsNone(
            schemacomponents.SchemaComponent.addActionToProtocol(comp, ctx)
        )
        get_label.assert_called_once_with("cdbwf_component_copy")
        comp.addProtocol.assert_called_once_with(
            get_label.return_value.format.return_value,
        )
        get_label.return_value.format.assert_called_once_with(
            comp.task_id,
            comp.title,
            ctx.cdbtemplate["process_title"],
            ctx.cdbtemplate["cdb_process_id"],
        )
        getenv.assert_called_once_with("CS_WORKFLOW_SIMPLE_LOG_MODE", None)

    @mock.patch.object(schemacomponents.util, "get_label", autospec=True)
    @mock.patch.object(schemacomponents.os, "getenv", autospec=True,
                       return_value="")
    def test_addActionToProtocol_delete(self, getenv, get_label):
        "action is logged for delete"
        comp = mock.MagicMock(spec=schemacomponents.SchemaComponent)
        ctx = mock.MagicMock(action="delete", error=None)
        self.assertIsNone(
            schemacomponents.SchemaComponent.addActionToProtocol(comp, ctx)
        )
        get_label.assert_called_once_with("cdbwf_component_delete")
        comp.addProtocol.assert_called_once_with(
            get_label.return_value.format.return_value,
        )
        get_label.return_value.format.assert_called_once_with(
            comp.task_id,
            comp.title,
        )
        getenv.assert_called_once_with("CS_WORKFLOW_SIMPLE_LOG_MODE", None)

    @mock.patch.object(schemacomponents.util, "get_label", autospec=True)
    @mock.patch.object(schemacomponents.os, "getenv", autospec=True,
                       return_value="")
    def test_addActionToProtocol_modify(self, getenv, get_label):
        "action is logged for modify"
        comp = mock.MagicMock(spec=schemacomponents.SchemaComponent)
        comp.get_modify_Protocol_text.return_value = ["a", "b"]
        ctx = mock.MagicMock(action="modify", error=None)
        self.assertIsNone(
            schemacomponents.SchemaComponent.addActionToProtocol(comp, ctx)
        )
        get_label.assert_called_once_with("cdbwf_component_modify")
        comp.addProtocol.assert_called_once_with(
            get_label.return_value.replace.return_value.format.return_value,
        )
        get_label.return_value.replace.assert_called_once_with("\\n", "\n")
        get_label.return_value.replace.return_value.format.assert_called_once_with(
            comp.task_id,
            comp.title,
            "\n".join(comp.get_modify_Protocol_text.return_value)
        )
        comp.get_modify_Protocol_text.assert_called_once_with(ctx)
        getenv.assert_called_once_with("CS_WORKFLOW_SIMPLE_LOG_MODE", None)

    @mock.patch.object(schemacomponents, "_not_equal", return_value=False)
    def test_get_modify_Protocol_text_values_equal(self, _not_equal):
        "old and new value are equal, so no protocol message"

        mock_ctx = mock.Mock(spec=["ue_args"])
        d = mock.MagicMock()
        args_dict = {"prot_old_foo": "v1"}
        d.get_attribute_names.return_value = args_dict.keys()
        d.__getitem__.side_effect = args_dict.__getitem__
        mock_ctx.ue_args = d

        comp = mock.MagicMock(spec=schemacomponents.SchemaComponent)
        self_dict = {"foo": "v2"}
        comp.__getitem__.side_effect = self_dict.__getitem__

        # no msg is generated
        self.assertListEqual(
            [],
            schemacomponents.SchemaComponent.get_modify_Protocol_text(
                comp, mock_ctx
            )
        )
        _not_equal.assert_called_once_with("v1", "v2")

    @mock.patch.object(schemacomponents, "isinstance", return_value=False)
    @mock.patch.object(schemacomponents, "_not_equal", return_value=True)
    def test_get_modify_Protocol_text_values_not_equal_not_date_format(
        self, _not_equal, isInstance
    ):
        "old and new value are not equal, so a protocol message is returned"
        mock_ctx = mock.Mock(spec=["ue_args"])
        d = mock.MagicMock()
        args_dict = {"prot_old_foo": "v1"}
        d.get_attribute_names.return_value = args_dict.keys()
        d.__getitem__.side_effect = args_dict.__getitem__
        mock_ctx.ue_args = d

        comp = mock.MagicMock(spec=schemacomponents.SchemaComponent)
        self_dict = {"foo": "v2"}
        comp.__getitem__.side_effect = self_dict.__getitem__

        # msg is generated
        self.assertListEqual(
            ["foo: v1 -> v2"],
            schemacomponents.SchemaComponent.get_modify_Protocol_text(
                comp, mock_ctx
            )
        )
        _not_equal.assert_called_once_with("v1", "v2")
        isInstance.assert_called_once_with(
            "v2", (datetime.datetime, datetime.date)
        )

    @mock.patch.object(
        schemacomponents.typeconversion,
        "to_user_repr_date_format",
        side_effect=[
            "value1_end_more_than_ten_characters",
            "value2_end_more_than_ten_characters"]
    )
    @mock.patch.object(schemacomponents, "isinstance", return_value=True)
    @mock.patch.object(schemacomponents, "_not_equal", return_value=True)
    def test_get_modify_Protocol_text_values_not_equal_date_format(
        self, _not_equal, isInstance, to_user_repr_date_format
    ):
        "old and new value are not equal, so a protocol message is returned"

        mock_ctx = mock.Mock(spec=["ue_args"])
        d = mock.MagicMock()
        args_dict = {"prot_old_foo": "v1"}
        d.get_attribute_names.return_value = args_dict.keys()
        d.__getitem__.side_effect = args_dict.__getitem__
        mock_ctx.ue_args = d

        comp = mock.MagicMock(spec=schemacomponents.SchemaComponent)
        self_dict = {"foo": "v2"}
        comp.__getitem__.side_effect = self_dict.__getitem__

        # msg is generated
        self.assertListEqual(
            ["foo: value1_end -> value2_end"],
            schemacomponents.SchemaComponent.get_modify_Protocol_text(
                comp, mock_ctx
            )
        )
        _not_equal.assert_called_once_with("v1", "v2")
        isInstance.assert_called_once_with(
            "v2", (datetime.datetime, datetime.date)
        )
        to_user_repr_date_format.assert_has_calls(
            [
                mock.call("v1"),
                mock.call("v2")
            ]
        )

    def test_AbsolutePath(self):
        from cs.workflow.processes import Process
        loop = mock.MagicMock(
            spec=schemacomponents.SchemaComponent,
            position=0,
            Parent=None,
        )
        workflow = mock.MagicMock(
            spec=Process,
            position=99,
            ParentTask=loop,
        )
        group1 = mock.MagicMock(
            spec=schemacomponents.SchemaComponent,
            position=8.0,
            Parent=workflow,
        )
        group2 = mock.MagicMock(
            spec=schemacomponents.SchemaComponent,
            position=1,
            Parent=group1,
        )
        task = mock.MagicMock(
            spec=schemacomponents.SchemaComponent,
            position=5.0,
            Parent=group2,
        )
        self.assertEqual(
            schemacomponents.SchemaComponent.AbsolutePath(task),
            "-1/8/1/5",
        )

    @mock.patch.object(schemacomponents, "isinstance", return_value=False)
    def test__not_equal_not_equal_new_value_not_date(self, isInstance):
        " returns true, since both values are not equal"
        self.assertTrue(
            schemacomponents._not_equal("v1", "v2")
        )
        isInstance.assert_called_once_with(
            "v2", (datetime.datetime, datetime.date)
        )

    @mock.patch.object(schemacomponents, "isinstance", return_value=False)
    def test__not_equal_equal_new_value_not_date(self, isInstance):
        " returns false, since both values are equal"
        self.assertFalse(
            schemacomponents._not_equal("v1", "v1")
        )
        isInstance.assert_called_once_with(
            "v1", (datetime.datetime, datetime.date)
        )

    @mock.patch.object(
        schemacomponents, "to_legacy_date_format", return_value="v2"
    )
    @mock.patch.object(schemacomponents, "isinstance", return_value=True)
    def test__not_equal_not_equal_new_value_date(
        self, isInstance, to_legacy_date_format
    ):
        " returns true, since both values are not equal"
        self.assertTrue(
            schemacomponents._not_equal("v1", "v2")
        )
        isInstance.assert_called_once_with(
            "v2", (datetime.datetime, datetime.date)
        )
        to_legacy_date_format.assert_called_once_with("v2")

    @mock.patch.object(
        schemacomponents, "to_legacy_date_format", return_value="v1"
    )
    @mock.patch.object(schemacomponents, "isinstance", return_value=True)
    def test__not_equal_equal_new_value_date(
        self, isInstance, to_legacy_date_format
    ):
        " returns false, since both values are equal"
        self.assertFalse(
            schemacomponents._not_equal("v1", "v1")
        )
        isInstance.assert_called_once_with(
            "v1", (datetime.datetime, datetime.date)
        )
        to_legacy_date_format.assert_called_once_with("v1")

    @mock.patch.object(schemacomponents, "isinstance", return_value=True)
    def test__not_equal_no_old_value_given(self, isInstance):
        " returns false, since old value is None"
        self.assertFalse(
            schemacomponents._not_equal(None, "v1")
        )
        isInstance.assert_called_once_with(
            "v1", (datetime.datetime, datetime.date)
        )


class SchemaComponentIntegration(testcase.RollbackTestCase):
    maxDiff = None

    def test_Create(self):
        "Create presets empty extension class"
        new = schemacomponents.SchemaComponent.Create(
            cdb_classname="cdbwf_task_execution",
            cdb_process_id="foo",
            task_id="bar",
        )
        assert set({
            "cdb_classname": "cdbwf_task_execution",
            "cdb_extension_class": "",
            "cdb_process_id": "foo",
            "task_id": "bar",
        }.items()).issubset(set(dict(new).items()))

    def test_CDB_Create(self):
        "CDB_Create presets empty extension class"
        schemacomponents.Process.CreateNoResult(
            cdb_process_id="foo",
            subject_id=auth.persno,
            subject_type="Person",
            is_template="0",
            status=0,
        )

        new = operation(
            "CDB_Create",
            "cdbwf_task_execution",
            cdb_process_id="foo",
        )
        assert set({
            "cdb_classname": "cdbwf_task_execution",
            "cdb_extension_class": "",
            "cdb_process_id": "foo",
        }.items()).issubset(set(dict(new).items()))
