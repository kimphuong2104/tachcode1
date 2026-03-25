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

from cs.pcs.projects.web.rest_app.project_structure import helpers


@pytest.mark.unit
class Utility(unittest.TestCase):
    def test__check(self):
        mock_json = mock.MagicMock(get=mock.MagicMock(return_value="bar"))
        self.assertEqual(helpers._check(mock_json, "foo", str), "bar")

    @mock.patch.object(helpers, "logging")
    def test__check_key_not_given(self, logging):
        with self.assertRaises(helpers.HTTPBadRequest):
            helpers._check({}, "foo", str)

        logging.error.assert_called_once_with("missing value for key: %s", "foo")

    @mock.patch.object(helpers, "logging")
    def test__check_key_not_given_optional(self, logging):
        self.assertIsNone(helpers._check({}, "foo", str, False))
        logging.error.assert_not_called()

    @mock.patch.object(helpers, "logging")
    def test__check_not_of_instance(self, logging):
        with self.assertRaises(helpers.HTTPBadRequest):
            mock_json = mock.MagicMock(get=mock.MagicMock(return_value=1))
            helpers._check(mock_json, "foo", str)

        logging.error.assert_called_once_with("malformed '%s': %s", "foo", 1)

    @mock.patch.object(helpers, "logging")
    def test__check_not_of_instance_optional(self, logging):
        with self.assertRaises(helpers.HTTPBadRequest):
            mock_json = mock.MagicMock(get=mock.MagicMock(return_value=1))
            helpers._check(mock_json, "foo", str, False)

        logging.error.assert_called_once_with("malformed '%s': %s", "foo", 1)

    @mock.patch.object(helpers.logging, "error")
    @mock.patch.object(
        helpers, "_check", side_effect=["foo", "bar", "bam", "boo", "blu"]
    )
    def test_parse_persist_drop_payload_invalid_is_move(self, _check, error):
        with self.assertRaises(helpers.HTTPBadRequest):
            helpers.parse_persist_drop_payload("baz")

        error.assert_called_once_with(
            "dropEffect may only be 'move' or 'copy', is '%s'", "blu"
        )
        _check.assert_has_calls(
            [
                mock.call("baz", "targetId", str),
                mock.call("baz", "parentId", str),
                mock.call("baz", "children", list, False),
                mock.call("baz", "predecessor", str, False),
                mock.call("baz", "dropEffect", str),
            ]
        )

    @mock.patch.object(
        helpers, "_check", side_effect=["foo", "bar", "bam", "boo", "move"]
    )
    def test_parse_persist_drop_payload(self, _check):
        self.assertEqual(
            helpers.parse_persist_drop_payload("baz"),
            ("foo", "bar", "bam", "boo", True),
        )
        _check.assert_has_calls(
            [
                mock.call("baz", "targetId", str),
                mock.call("baz", "parentId", str),
                mock.call("baz", "children", list, False),
                mock.call("baz", "predecessor", str, False),
                mock.call("baz", "dropEffect", str),
            ]
        )


if __name__ == "__main__":
    unittest.main()
