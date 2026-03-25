#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import unittest

import pytest
from cdb import testcase, util
from cdb.platform.mom import Term
from cs.platform.web.root.main import _get_dummy_request
from mock import MagicMock, call, patch

from cs.pcs.projects import Project
from cs.pcs.timeschedule import TimeScheduleObject
from cs.pcs.timeschedule.web.models import elements_model
from cs.pcs.timeschedule.web.models.data_model import PCS_OID


@pytest.mark.intergation
class ElementsModelIntegration(testcase.RollbackTestCase):
    def test_get_elements_non_readable(self):
        """
        Simulate read access denied on a non-primary time schedule element.
        Time schedules directly attached to an unreadable project will directly 404.
        """
        project_granted = Project.ByKeys("ptest.cust.middle")
        project_denied = Project.ByKeys("ptest.cust.big")
        # setup project_denied to not be readable
        new_term = Term.Create(
            predicate_name="cs.pcs: Projects",
            table_name="cdbpcs_project",
            attribute="cdb_project_id",
            operator="!=",
            expression=project_denied.cdb_project_id,
            data_type="char",
        )
        util.reload_cache(util.kCGAccessSystem, util.kLocalReload)

        try:
            self.assertTrue(
                project_granted.CheckAccess("read"),
                f"{project_granted.cdb_project_id} is not readable",
            )
            self.assertFalse(
                project_denied.CheckAccess("read"),
                f"{project_denied.cdb_project_id} is readable",
            )

            # add unreadable project to time schedule elements
            schedule_uuid = project_granted.TimeSchedules[0].cdb_object_id
            TimeScheduleObject.Create(
                position=99,
                view_oid=schedule_uuid,
                content_oid=project_denied.cdb_object_id,
                cdb_content_classname="cdbpcs_project",
            )

            model = elements_model.ElementsModel(schedule_uuid)
            self.assertEqual(
                {x.cdb_object_id for x in model._get_pinned_oids()},
                {project_granted.cdb_object_id, project_denied.cdb_object_id},
            )
            request = _get_dummy_request()
            self.assertEqual(
                model._get_schedule_elements(request),
                ["http://localhost/api/v1/collection/project/ptest.cust.middle@"],
            )
        finally:
            new_term.Delete()
            util.reload_cache(util.kCGAccessSystem, util.kLocalReload)


@pytest.mark.unit
class ElementsModel(unittest.TestCase):
    @patch.object(
        elements_model,
        "get_restlinks_in_batch",
        autospec=True,
        return_value={"b": "b_link", "a": "a_link"},
    )
    def test__get_schedule_elements(self, get_restlinks_in_batch):
        model = MagicMock(spec=elements_model.ElementsModel)
        model._get_pinned_oids.return_value = [
            ("a", "foo"),
            ("b", "bar"),
        ]
        model._get_readable.return_value = [
            PCS_OID("a", "foo"),
            PCS_OID("b", "bar"),
        ]
        self.assertEqual(
            elements_model.ElementsModel._get_schedule_elements(model, "req"),
            ["a_link", "b_link"],
        )
        model._get_pinned_oids.assert_called_once_with()
        model._get_record_tuples.assert_called_once_with(
            model._get_pinned_oids.return_value,
        )
        model._get_readable.assert_called_once_with(
            model._get_pinned_oids.return_value,
            get_restlinks_in_batch.return_value,
        )
        get_restlinks_in_batch.assert_called_once_with(
            model._get_record_tuples.return_value,
            "req",
        )

    @patch.object(
        elements_model,
        "operation",
        autospec=True,
        side_effect=elements_model.ElementsError("?"),
    )
    @testcase.without_error_logging
    def test__run_op_fail(self, operation):
        "raises if operation fails"
        model = MagicMock(spec=elements_model.ElementsModel)
        with self.assertRaises(elements_model.HTTPForbidden) as error:
            elements_model.ElementsModel._run_op(model, "OP", "EL", a="b")

        self.assertEqual(error.exception.detail, "?")
        operation.assert_called_once_with("OP", "EL", a="b")

    @patch.object(elements_model, "operation", autospec=True)
    def test__run_op(self, operation):
        "runs an operation, returns nothing"
        model = MagicMock(spec=elements_model.ElementsModel)
        self.assertIsNone(
            elements_model.ElementsModel._run_op(model, "OP", "EL", a="b")
        )
        operation.assert_called_once_with("OP", "EL", a="b")

    @patch.object(
        elements_model.sqlapi,
        "RecordSet2",
        autospec=True,
        return_value=[
            MagicMock(id="a", relation="A"),
            MagicMock(id="b", relation="B"),
        ],
    )
    def test__get_tables_by_oid(self, RecordSet2):
        "indexes tables by oid"
        model = MagicMock(spec=elements_model.ElementsModel)
        self.assertEqual(
            elements_model.ElementsModel._get_tables_by_oid(
                model,
                ["oid1", "oid2"],
            ),
            {
                "a": "A",
                "b": "B",
            },
        )
        RecordSet2.assert_called_once_with(
            "cdb_object",
            "id IN ('oid1', 'oid2')",
        )

    @patch.object(elements_model, "kOperationDelete")
    def test__clear_elements(self, kOperationDelete):
        model = MagicMock(
            spec=elements_model.ElementsModel,
            context_object_id="CTX",
            content_cls=MagicMock(),
        )
        self.assertIsNone(elements_model.ElementsModel._clear_elements(model))
        model._run_op.assert_has_calls(
            [
                call(kOperationDelete, model.content_cls.KeywordQuery.return_value),
            ]
        )
        self.assertEqual(model._run_op.call_count, 1)

    @patch.object(elements_model.logging, "error", autospec=True)
    def test_persist_elements_missing(self, error):
        "fails if request is missing key 'elementOIDs'"
        model = MagicMock(spec=elements_model.ElementsModel)
        request = MagicMock(json={})

        with self.assertRaises(elements_model.HTTPBadRequest):
            elements_model.ElementsModel.persist_elements(model, request)

        error.assert_called_once_with("request is missing 'elementOIDs'")
        model._clear_elements.assert_not_called()

    @patch.object(elements_model.logging, "exception", autospec=True)
    def test_persist_elements_no_table(self, exception):
        "fails if table cannot be found for oid"
        model = MagicMock(spec=elements_model.ElementsModel)
        model.context_object_id = "bar"
        model._get_tables_by_oid.return_value = {}
        request = MagicMock(json={"elementOIDs": ["a", "b"]})

        with self.assertRaises(elements_model.HTTPNotFound):
            elements_model.ElementsModel.persist_elements(model, request)

        exception.assert_called_once_with(
            "adding time schedule element failed",
        )
        model._get_tables_by_oid.assert_called_once_with(["a", "b"])
        model._clear_elements.assert_called_once_with()

    @patch.object(elements_model.logging, "exception", autospec=True)
    def test_persist_elements_no_plugin(self, exception):
        "fails if plugin cannot be found for oid"
        model = MagicMock(spec=elements_model.ElementsModel)
        model.plugins = {}
        model.context_object_id = "bar"
        request = MagicMock(json={"elementOIDs": ["a", "b"]})

        with self.assertRaises(elements_model.HTTPNotFound):
            elements_model.ElementsModel.persist_elements(model, request)

        exception.assert_called_once_with(
            "adding time schedule element failed",
        )
        model._get_tables_by_oid.assert_called_once_with(["a", "b"])
        model._clear_elements.assert_called_once_with()

    @patch.object(elements_model, "kOperationNew", "NEW")
    def test_persist_elements(self):
        "runs operations and returns data"
        model = MagicMock(
            spec=elements_model.ElementsModel,
            context_object_id="CTX",
            content_cls=MagicMock(),
        )
        model._get_tables_by_oid.return_value = {
            "a": "table_a",
            "b": "table_b",
        }
        plugin_a = MagicMock(classname="foo")
        plugin_b = MagicMock(classname="bar")
        model.plugins = {
            "table_a": plugin_a,
            "table_b": plugin_b,
        }
        request = MagicMock(json={"elementOIDs": ["a", "b"]})

        self.assertIsNone(elements_model.ElementsModel.persist_elements(model, request))

        model._get_tables_by_oid.assert_called_once_with(["a", "b"])
        model._run_op.assert_has_calls(
            [
                call(
                    "NEW",
                    model.content_cls,
                    view_oid="CTX",
                    content_oid="a",
                    cdb_content_classname=plugin_a.classname,
                    unremovable=0,
                ),
                call(
                    "NEW",
                    model.content_cls,
                    view_oid="CTX",
                    content_oid="b",
                    cdb_content_classname=plugin_b.classname,
                    unremovable=0,
                ),
            ]
        )
        self.assertEqual(model._run_op.call_count, 2)
        model._clear_elements.assert_called_once_with()

    def test_get_manage_elements_data(self):
        "returns manage elements"
        model = MagicMock(spec=elements_model.ElementsModel)
        model._get_rest_objects.return_value = {
            "objects": "O",
            "status": "S",
            "projectNames": "PN",
            "plugins": "?",
        }
        self.assertEqual(
            elements_model.ElementsModel.get_manage_elements_data(model, "request"),
            {
                "objects": "O",
                "status": "S",
                "projectNames": "PN",
                "plugins": model._get_plugins.return_value,
                "elements": model.get_schedule_elements.return_value,
                "project_ids_by_elements": model.get_schedule_project_ids.return_value,
            },
        )
