# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access,no-value-for-parameter

__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import unittest

import pytest
from mock import MagicMock, call, patch
from webob.exc import HTTPBadRequest

from cs.pcs.timeschedule.web.models import set_relships_model


def _get_model(model_cls):
    # initialize model without calling __init__
    return model_cls.__new__(model_cls)


@pytest.mark.unit
class SetRelshipsModel(unittest.TestCase):
    def _get_model(self):
        return _get_model(set_relships_model.SetRelshipsModel)

    @patch.object(set_relships_model.logging, "error", autospec=True)
    @patch.object(set_relships_model.UpdateModel, "__init__")
    @patch.object(
        set_relships_model.SetRelshipsModel, "get_object_from_uuid", autospec=True
    )
    def test__init__(self, get_object_from_uuid, UpdateModel__init__, error):
        "initializes correctly"
        model = set_relships_model.SetRelshipsModel(
            "ctx",
            "task",
            "predecessors",
        )
        self.assertEqual(model.task_object_id, "task")
        self.assertEqual(model.relship_name, "predecessors")
        UpdateModel__init__.assert_called_once_with(model, "ctx", True)
        self.assertEqual(model.task, get_object_from_uuid.return_value)
        get_object_from_uuid.assert_called_once_with(model, "task")
        self.assertEqual(error.call_count, 0)

    @patch.object(set_relships_model.logging, "error", autospec=True)
    @patch.object(set_relships_model.UpdateModel, "__init__")
    def test__init__illegal_relship_name(self, UpdateModel__init__, error):
        "fails to initialize"
        with self.assertRaises(HTTPBadRequest):
            set_relships_model.SetRelshipsModel("foo", "bar", "preds")

        error.assert_called_once_with(
            "SetRelshipsModel: unknown relship_name '%s'",
            "preds",
        )

    @patch.object(set_relships_model.TaskRelation, "KeywordQuery")
    def test_get_relships_pred(self, KeywordQuery):
        "returns predecessors"
        model = self._get_model()
        model.relship_name = "predecessors"
        model.task_object_id = "foo"
        self.assertEqual(model.get_relships(), KeywordQuery.return_value)
        KeywordQuery.assert_called_once_with(
            succ_task_oid="foo",
        )

    @patch.object(set_relships_model.TaskRelation, "KeywordQuery")
    def test_get_relships_succ(self, KeywordQuery):
        "returns successors"
        model = self._get_model()
        model.relship_name = "successors"
        model.task_object_id = "foo"
        self.assertEqual(model.get_relships(), KeywordQuery.return_value)
        KeywordQuery.assert_called_once_with(
            pred_task_oid="foo",
        )

    def test_get_relships_illegal_relship_name(self):
        "fails if relship_name is unknown"
        model = self._get_model()
        model.relship_name = "unknown"
        with self.assertRaises(KeyError) as error:
            model.get_relships()

        self.assertEqual(str(error.exception), "'unknown'")

    @staticmethod
    def _get_objects():
        return {
            "pred_task_oid": "foo1",
            "succ_task_oid": "foo2",
            "rel_type": "foo3",
            "minimal_gap": "foo4",
        }

    def test_relationships_identical_true(self):
        a = self._get_objects()
        b = self._get_objects()
        self.assertTrue(
            set_relships_model.SetRelshipsModel.relationships_identical(a, b)
        )

    def test_relationships_identical_false(self):
        a = self._get_objects()
        b = self._get_objects()
        b.update(pred_task_oid="bar")
        self.assertFalse(
            set_relships_model.SetRelshipsModel.relationships_identical(a, b)
        )

        a = self._get_objects()
        b = self._get_objects()
        b.update(succ_task_oid="bar")
        self.assertFalse(
            set_relships_model.SetRelshipsModel.relationships_identical(a, b)
        )

        a = self._get_objects()
        b = self._get_objects()
        b.update(rel_type="bar")
        self.assertTrue(
            set_relships_model.SetRelshipsModel.relationships_identical(a, b)
        )

    def test_relationships_gap_identical_true(self):
        self.assertTrue(
            set_relships_model.SetRelshipsModel.relationships_gap_identical(
                {"minimal_gap": 0, "rel_type": "EA"},
                {"minimal_gap": 0, "rel_type": "EA"},
            )
        )

    def test_relationships_gap_identical_false_1(self):
        self.assertFalse(
            set_relships_model.SetRelshipsModel.relationships_gap_identical(
                {"minimal_gap": 0, "rel_type": "EA"},
                {"minimal_gap": 1, "rel_type": "EA"},
            )
        )

    def test_relationships_gap_identical_false_2(self):
        self.assertFalse(
            set_relships_model.SetRelshipsModel.relationships_gap_identical(
                {"minimal_gap": 0, "rel_type": "EA"},
                {"minimal_gap": 0, "rel_type": "EE"},
            )
        )

    @patch.object(
        set_relships_model.SetRelshipsModel,
        "relationships_identical",
        return_value=True,
    )
    def test_relationship_exists_true(self, relationships_identical):
        result = set_relships_model.SetRelshipsModel.relationship_exists("a", "b")
        self.assertEqual(result, "b")
        relationships_identical.assert_called_once_with("a", "b")

    @patch.object(
        set_relships_model.SetRelshipsModel,
        "relationships_identical",
        return_value=False,
    )
    def test_relationship_exists_false(self, relationships_identical):
        result = set_relships_model.SetRelshipsModel.relationship_exists("a", "b")
        self.assertEqual(result, None)
        relationships_identical.assert_called_once_with("a", "b")

    @patch.object(set_relships_model, "kOperationDelete")
    @patch.object(set_relships_model, "operation", autospec=True)
    @patch.object(
        set_relships_model.SetRelshipsModel, "relationship_exists", return_value=False
    )
    def test_delete_old_relships(
        self, relationship_exists, operation, kOperationDelete
    ):
        "deletes existing relships"
        model = self._get_model()
        model.delete_old_relships(["foo"], ["a", "b"])
        relationship_exists.assert_has_calls(
            [
                call("a", ["foo"]),
                call("b", ["foo"]),
            ]
        )
        operation.assert_has_calls(
            [
                call(kOperationDelete, "a"),
                call(kOperationDelete, "b"),
            ]
        )
        self.assertEqual(operation.call_count, 2)

    @patch.object(set_relships_model.util, "ErrorMessage")
    def test_assert_is_task(self, ErrorMessage):
        "does nothing when called with a task"
        model = self._get_model()
        t = set_relships_model.Task()
        self.assertIsNone(model.assert_is_task(t))
        ErrorMessage.assert_not_called()

    @patch.object(set_relships_model.util, "ErrorMessage")
    def test_assert_is_task_raises(self, ErrorMessage):
        "raises when called with something else than a task"
        model = self._get_model()
        with self.assertRaises(set_relships_model.ElementsError) as error:
            model.assert_is_task("foo")

        self.assertEqual(str(error.exception), f"{ErrorMessage.return_value}")

        ErrorMessage.assert_called_once_with("cdbpcs_taskrel_tasks_only")

    @patch.object(set_relships_model.TaskRelation, "createRelation", return_value="foo")
    def _create_new_relships(self, relship_name, oid_attr, createRelation):
        model = self._get_model()
        model.relship_name = relship_name
        model.task = MagicMock()
        pred = MagicMock()
        model.get_object_from_uuid = pred
        model.assert_is_task = MagicMock()
        with patch.object(model, "task") as task:
            self.assertEqual(
                model.create_new_relships(
                    [
                        {oid_attr: "foo"},
                        {oid_attr: "bar"},
                    ],
                    [],
                ),
                ["foo", "foo"],
            )

        model.get_object_from_uuid.assert_has_calls(
            [
                call("foo"),
                call("bar"),
            ]
        )
        model.assert_is_task.assert_has_calls(
            [
                call(model.get_object_from_uuid.return_value),
                call(model.get_object_from_uuid.return_value),
            ]
        )

        def call_args(oid):
            if relship_name == "predecessors":
                return {
                    oid_attr: oid,
                    "cdb_project_id2": pred.return_value.cdb_project_id,
                    "task_id2": pred.return_value.task_id,
                    "cdb_project_id": task.cdb_project_id,
                    "task_id": task.task_id,
                }
            else:
                return {
                    oid_attr: oid,
                    "cdb_project_id2": task.cdb_project_id,
                    "task_id2": task.task_id,
                    "cdb_project_id": pred.return_value.cdb_project_id,
                    "task_id": pred.return_value.task_id,
                }

        createRelation.assert_has_calls(
            [
                call(**call_args("foo")),
                call(**call_args("bar")),
            ]
        )
        self.assertEqual(model.get_object_from_uuid.call_count, 2)
        self.assertEqual(model.assert_is_task.call_count, 2)
        self.assertEqual(createRelation.call_count, 2)

    def test_create_new_relships_pred(self):
        "creates predecessors"
        self._create_new_relships("predecessors", "pred_task_oid")

    def test_create_new_relships_succ(self):
        "creates successors"
        self._create_new_relships("successors", "succ_task_oid")

    @patch.object(set_relships_model.logging, "error", autospec=True)
    def test_set_relships_invalid_json(self, error):
        "fails if json is invalid"
        model = self._get_model()
        request = MagicMock(json={"foo": "bar"})

        with self.assertRaises(set_relships_model.HTTPBadRequest):
            model.set_relships(request)

        error.assert_called_once_with(
            "set_relships: 'relships' missing in request JSON: %s", request.json
        )

    @patch.object(set_relships_model.SetRelshipsModel, "verify_writable")
    @patch.object(set_relships_model.logging, "exception", autospec=True)
    def test_set_relships_error(self, exception, verify_writable):
        "fails if object is no task"
        model = self._get_model()
        model.task = "task"
        model.assert_is_task = MagicMock(
            side_effect=set_relships_model.ElementsError,
        )
        request = MagicMock()

        with self.assertRaises(set_relships_model.HTTPForbidden):
            model.set_relships(request)

        exception.assert_called_once_with("set_relships failed")
        verify_writable.assert_called_once_with("task", ["predecessors", "successors"])

    @patch.object(
        set_relships_model.SetRelshipsModel, "get_relships", return_value="bass"
    )
    @patch.object(set_relships_model.SetRelshipsModel, "verify_writable")
    @patch.object(set_relships_model.transaction, "Transaction", autospec=True)
    @patch.object(set_relships_model.logging, "error", autospec=True)
    def test_set_relships(self, error, Transaction, verify_writable, get_relships):
        "returns new relships"
        model = self._get_model()
        model.task = "task"
        model.assert_is_task = MagicMock()
        model.delete_old_relships = MagicMock()
        model.create_new_relships = MagicMock()
        model.create_new_relships.return_value = "bar"
        model.get_changed_data = MagicMock()
        request = MagicMock()

        self.assertEqual(
            model.set_relships(request), model.get_changed_data.return_value
        )

        self.assertEqual(error.call_count, 0)
        model.assert_is_task.assert_called_once_with(model.task)
        Transaction.assert_called_once_with()
        model.delete_old_relships.assert_called_once_with("bar", "bass")
        get_relships.assert_called_once_with()
        model.create_new_relships.assert_called_once_with(
            request.json["relships"], "bass"
        )
        model.get_changed_data.assert_called_once_with(request)
        verify_writable.assert_called_once_with("task", ["predecessors", "successors"])


if __name__ == "__main__":
    unittest.main()
