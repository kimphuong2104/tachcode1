#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import unittest

import mock
import pytest
from cdb import testcase

from cs.pcs.projects.common.webdata.models import subject_thumbnails


@pytest.mark.unit
class Utilities(unittest.TestCase):
    def test_group_by_first_value(self):
        def transform(value):
            return f"### {value[-1]}"

        values = [
            ("A", "3"),
            ("B", "2"),
            ("A", "1"),
        ]
        self.assertEqual(
            subject_thumbnails.group_by_first_value(values, transform),
            {
                "A": ["### 3", "### 1"],
                "B": ["### 2"],
            },
        )

    @mock.patch.object(subject_thumbnails, "values_from_rest_key")
    @mock.patch.object(subject_thumbnails.util, "get_sql_condition")
    @mock.patch.object(subject_thumbnails.sqlapi, "RecordSet2")
    def test_get_rest_objects(
        self, RecordSet2, get_sql_condition, values_from_rest_key
    ):
        self.assertEqual(
            subject_thumbnails.get_rest_objects(
                "table",
                "keynames",
                ["key1", "key2"],
            ),
            RecordSet2.return_value,
        )
        values_from_rest_key.assert_has_calls(
            [
                mock.call("key1"),
                mock.call("key2"),
            ]
        )
        get_sql_condition.assert_called_once_with(
            "table", "keynames", 2 * [values_from_rest_key.return_value]
        )
        RecordSet2.assert_called_once_with(
            "table", get_sql_condition.return_value, access="read"
        )

    def test_get_rest_key(self):
        self.assertEqual(
            subject_thumbnails.get_rest_key(
                "ab",
                {"a": "Ä", "b": "{B}", "c": "C"},
            ),
            "~C3~84@~7BB~7D",
        )

    def test_parse_rest_id(self):
        with self.assertRaises(KeyError):
            subject_thumbnails.parse_rest_id("no slash")

    def test_parse_rest_id(self):
        self.assertEqual(
            subject_thumbnails.parse_rest_id("/foo/bar/baz/bloop"),
            ("baz", "bloop"),
        )

    def test_make_absolute_url(self):
        request = mock.MagicMock(application_url="base")
        self.assertEqual(
            subject_thumbnails.make_absolute_url(request, ("class", "foo")),
            "base/api/v1/collection/class/foo",
        )


@pytest.mark.unit
class BaseRoleModel(unittest.TestCase):
    def test__resolve(self):
        self.assertEqual(
            subject_thumbnails.BaseRoleModel._resolve({"foo": "bar"}, "foo"),
            "bar",
        )

    @testcase.without_error_logging
    def test__resolve_missing_key(self):
        with self.assertRaises(KeyError):
            subject_thumbnails.BaseRoleModel._resolve({}, "foo")

    def test_resolve(self):
        self.assertEqual(
            subject_thumbnails.BaseRoleModel.resolve({"foo": "bar"}, "foo"),
            "bar",
        )

    @testcase.without_error_logging
    def test_resolve_missing_key(self):
        self.assertIsNone(
            subject_thumbnails.BaseRoleModel.resolve({}, "foo"),
        )

    def test_get_icon_and_label(self):
        role = mock.MagicMock()
        self.assertEqual(
            subject_thumbnails.BaseRoleModel.get_icon_and_label(role),
            (
                role.GetObjectIcon.return_value,
                role.GetDescription.return_value,
            ),
        )

    @testcase.without_error_logging
    def test_load_thumbnails(self):
        with self.assertRaises(NotImplementedError):
            subject_thumbnails.BaseRoleModel.load_thumbnails("foo")


@pytest.mark.unit
class PersonModel(unittest.TestCase):
    def test_get_icon_and_label_no_thumbnail(self):
        user = mock.MagicMock()
        user.GetThumbnailFile.return_value = None
        self.assertEqual(
            subject_thumbnails.PersonModel.get_icon_and_label(user),
            (
                None,
                user.GetDescription.return_value,
            ),
        )

    def test_get_icon_and_label(self):
        user = mock.MagicMock()
        user.GetThumbnailFile.return_value = mock.MagicMock(cdb_object_id="foo")
        self.assertEqual(
            subject_thumbnails.PersonModel.get_icon_and_label(user),
            (
                "/api/v1/collection/person/caddok/files/foo",
                user.GetDescription.return_value,
            ),
        )

    @mock.patch.object(subject_thumbnails.PersonModel, "get_icon_and_label")
    @mock.patch.object(
        subject_thumbnails.User,
        "Query",
        return_value=[
            mock.MagicMock(personalnummer="A"),
            mock.MagicMock(personalnummer="B"),
        ],
    )
    def test_load_thumbnails(self, Query, get_icon_and_label):
        self.assertEqual(
            subject_thumbnails.PersonModel.load_thumbnails("foo"),
            {
                "A": get_icon_and_label.return_value,
                "B": get_icon_and_label.return_value,
            },
        )
        Query.assert_called_once_with("personalnummer IN ('f','o','o')", access="read")


@pytest.mark.unit
class CommonRoleModel(unittest.TestCase):
    @mock.patch.object(subject_thumbnails.CommonRoleModel, "get_icon_and_label")
    @mock.patch.object(
        subject_thumbnails.CommonRole,
        "Query",
        return_value=[mock.MagicMock(role_id="A"), mock.MagicMock(role_id="B")],
    )
    def test_load_thumbnails(self, Query, get_icon_and_label):
        self.assertEqual(
            subject_thumbnails.CommonRoleModel.load_thumbnails("foo"),
            {
                "A": get_icon_and_label.return_value,
                "B": get_icon_and_label.return_value,
            },
        )
        Query.assert_called_once_with("role_id IN ('f','o','o')", access="read")


@pytest.mark.unit
class PCSRoleModel(unittest.TestCase):
    def test__get_id(self):
        self.assertEqual(
            subject_thumbnails.PCSRoleModel._get_id(
                {
                    "subject_id": "Member",
                    "cdb_project_id": "P00",
                },
                "subject_id",
            ),
            ("P00", "Member"),
        )

    def test__resolve(self):
        self.assertEqual(
            subject_thumbnails.PCSRoleModel._resolve(
                {
                    "subject_id": "Member",
                    "cdb_project_id": "P00",
                },
                "subject_id",
            ),
            ("P00", "Member"),
        )

    @mock.patch.object(subject_thumbnails.PCSRoleModel, "get_icon_and_label")
    @mock.patch.object(
        subject_thumbnails.Role,
        "Query",
        return_value=[
            {"role_id": "A", "cdb_project_id": "Pa"},
            {"role_id": "B", "cdb_project_id": "Pb"},
        ],
    )
    def test_load_thumbnails(self, Query, get_icon_and_label):
        self.assertEqual(
            subject_thumbnails.PCSRoleModel.load_thumbnails(
                [
                    ["P00", "Manager"],
                    ["P01", "Assistant"],
                ]
            ),
            {
                ("Pa", "A"): get_icon_and_label.return_value,
                ("Pb", "B"): get_icon_and_label.return_value,
            },
        )
        Query.assert_called_once_with(
            "(cdb_project_id = 'P00' AND role_id IN ('Manager')) OR "
            "(cdb_project_id = 'P01' AND role_id IN ('Assistant'))",
            access="read",
        )


@pytest.mark.unit
class SubjectThumbnailModel(unittest.TestCase):
    @testcase.without_error_logging
    @mock.patch.object(subject_thumbnails.logging, "error")
    def test_bad_request(self, error):
        model = subject_thumbnails.SubjectThumbnailModel()
        with self.assertRaises(subject_thumbnails.HTTPBadRequest):
            model.bad_request("foo", "bar", "baz")

        error.assert_called_once_with("%s foo", "SubjectThumbnailModel", "bar", "baz")

    @testcase.without_error_logging
    def test_read_payload_no_dict(self):
        model = subject_thumbnails.SubjectThumbnailModel()
        request = mock.MagicMock()
        with self.assertRaises(subject_thumbnails.HTTPBadRequest):
            model.read_payload(request)

    @testcase.without_error_logging
    def test_read_payload_invalid_url(self):
        model = subject_thumbnails.SubjectThumbnailModel()
        request = mock.MagicMock(json={"foo": "bar"})
        with self.assertRaises(subject_thumbnails.HTTPBadRequest):
            model.read_payload(request)

    def test_read_payload(self):
        model = subject_thumbnails.SubjectThumbnailModel()
        request = mock.MagicMock(
            json={
                "/fluff/class/foo": "bar",
            }
        )
        self.assertEqual(
            model.read_payload(request),
            {("class", "foo"): "bar"},
        )

    @testcase.without_error_logging
    def test__get_model_unknown(self):
        model = subject_thumbnails.SubjectThumbnailModel()
        self.assertIsNone(model._get_model("foo"))

    def test__get_model_person(self):
        model = subject_thumbnails.SubjectThumbnailModel()
        self.assertEqual(
            model._get_model("Person"),
            subject_thumbnails.PersonModel,
        )

    def test__get_model_common_role(self):
        model = subject_thumbnails.SubjectThumbnailModel()
        self.assertEqual(
            model._get_model("Common Role"),
            subject_thumbnails.CommonRoleModel,
        )

    def test__get_model_pcs_role(self):
        model = subject_thumbnails.SubjectThumbnailModel()
        self.assertEqual(
            model._get_model("PCS Role"),
            subject_thumbnails.PCSRoleModel,
        )

    @mock.patch.object(
        subject_thumbnails,
        "get_rest_objects",
        side_effect=lambda _, keynames, keys: [dict(zip(keynames, keys[0].split("@")))],
    )
    def test__get_objects(self, get_rest_objects):
        model = subject_thumbnails.SubjectThumbnailModel()
        self.maxDiff = None
        self.assertDictEqual(
            model._get_objects(
                {
                    ("person", "foo"): None,
                    ("global_role", "bar"): None,
                    ("cdbpcs_prj_role", "baz@P00"): None,
                }
            ),
            {
                ("person", "foo"): {"personalnummer": "foo"},
                ("global_role", "bar"): {"role_id": "bar"},
                ("cdbpcs_prj_role", "baz@P00"): {
                    "cdb_project_id": "P00",
                    "role_id": "baz",
                },
            },
        )
        get_rest_objects.assert_has_calls(
            [
                mock.call(
                    "cdbpcs_prj_role", ("role_id", "cdb_project_id"), ["baz@P00"]
                ),
                mock.call("cdb_global_role", ("role_id",), ["bar"]),
                mock.call("angestellter", ("personalnummer",), ["foo"]),
            ]
        )

    def test__collect_subjects(self):
        model = subject_thumbnails.SubjectThumbnailModel()
        self.assertEqual(
            model._collect_subjects(
                {
                    "a": ["1", "2"],
                    "b": ["subject_id"],
                    "c@C": ["subject_id"],
                    "missing": ["foo"],
                },
                {
                    "a": {"1": "one", "2": "two"},
                    "b": {
                        "subject_id": "three",
                        "subject_type": "Common Role",
                    },
                    "c@C": {
                        "subject_id": "four",
                        "subject_type": "PCS Role",
                        "cdb_project_id": "C",
                    },
                },
            ),
            (
                {
                    "Person": ["one", "two"],
                    "Common Role": ["three"],
                    "PCS Role": [("C", "four")],
                },
                {
                    "a": {
                        "1": ("one", "Person"),
                        "2": ("two", "Person"),
                    },
                    "b": {"subject_id": ("three", "Common Role")},
                    "c@C": {"subject_id": (("C", "four"), "PCS Role")},
                },
            ),
        )

    @testcase.without_error_logging
    @mock.patch.object(subject_thumbnails.PCSRoleModel, "load_thumbnails")
    @mock.patch.object(subject_thumbnails.CommonRoleModel, "load_thumbnails")
    @mock.patch.object(subject_thumbnails.PersonModel, "load_thumbnails")
    def test__load_thumbnails(self, load_person, load_crole, load_prole):
        model = subject_thumbnails.SubjectThumbnailModel()
        self.assertEqual(
            model._load_thumbnails(
                {
                    "Person": ["a", "b"],
                    "Common Role": ["c"],
                    "PCS Role": [("D", "d")],
                    "foo": ["bar"],
                }
            ),
            {
                "Person": load_person.return_value,
                "Common Role": load_crole.return_value,
                "PCS Role": load_prole.return_value,
            },
        )
        load_person.assert_called_once_with(["a", "b"])
        load_crole.assert_called_once_with(["c"])
        load_prole.assert_called_once_with([("D", "d")])

    def test__prepare_response(self):
        model = subject_thumbnails.SubjectThumbnailModel()
        self.assertEqual(
            model._prepare_response(
                mock.MagicMock(application_url="foo"),
                {
                    ("A", "a"): {
                        "A1": (1, 2),
                        "A2": (3, 4),
                    },
                    ("B", "b"): {
                        "B1": (5, 6),
                        "B2": (7, 8),
                    },
                    ("C", "c"): {"C1": (9, 0)},
                },
                {
                    2: {1: "a.A1"},
                    4: {3: "a.A2"},
                    8: {7: "b.B2"},
                    0: {11: "foo"},
                },
            ),
            {
                "foo/api/v1/collection/A/a": {
                    "A1": "a.A1",
                    "A2": "a.A2",
                },
                "foo/api/v1/collection/B/b": {
                    "B1": None,
                    "B2": "b.B2",
                },
                "foo/api/v1/collection/C/c": {"C1": None},
            },
        )

    def test_get_data(self):
        model = mock.MagicMock(spec=subject_thumbnails.SubjectThumbnailModel)
        model._collect_subjects.return_value = ("foo", "bar")
        self.assertEqual(
            subject_thumbnails.SubjectThumbnailModel.get_data(model, "R"),
            model._prepare_response.return_value,
        )
        model.read_payload.assert_called_once_with("R")
        model._get_objects.assert_called_once_with(model.read_payload.return_value)
        model._collect_subjects.assert_called_once_with(
            model.read_payload.return_value,
            model._get_objects.return_value,
        )
        model._load_thumbnails.assert_called_once_with("foo")
        model._prepare_response.assert_called_once_with(
            "R", "bar", model._load_thumbnails.return_value
        )


if __name__ == "__main__":
    unittest.main()
