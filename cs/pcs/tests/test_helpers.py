#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import mock
import pytest
from cdb import testcase

from cs.pcs import helpers


@pytest.mark.unit
class HelpersTestCase(testcase.RollbackTestCase):
    @mock.patch.object(helpers.logging, "error")
    @mock.patch.object(
        helpers, "decode_key_component", side_effect=["foo1", "foo2", "foo3"]
    )
    def test_get_and_check_object_no_object(self, decode_key_component, log_error):
        """Logs error if requested object can not be retrieved"""
        mock_object = None
        mock_expected_class = mock.MagicMock()
        mock_expected_class.ByKeys.return_value = mock_object
        self.assertIsNone(
            helpers.get_and_check_object(
                mock_expected_class,
                "foo_access_right",
                foo_key1="foo_key1",
                foo_key2="foo_key2",
                foo_key3="foo_key3",
            )
        )
        log_error.assert_not_called()
        decode_key_component.assert_has_calls(
            [
                mock.call("foo_key1"),
                mock.call("foo_key2"),
                mock.call("foo_key3"),
            ]
        )
        mock_expected_class.ByKeys.assert_called_once_with(
            foo_key1="foo1", foo_key2="foo2", foo_key3="foo3"
        )

    @mock.patch.object(helpers, "auth")
    @mock.patch.object(helpers.logging, "error")
    @mock.patch.object(
        helpers, "decode_key_component", side_effect=["foo1", "foo2", "foo3"]
    )
    def test_get_and_check_object_no_access_granted(
        self, decode_key_component, log_error, mock_auth
    ):
        "Logs error, if access right on requested object is not granted"
        mock_auth.persno = "foo_user"
        mock_object = mock.MagicMock()
        mock_object.CheckAccess.return_value = False
        mock_expected_class = mock.MagicMock()
        mock_expected_class.ByKeys.return_value = mock_object
        self.assertIsNone(
            helpers.get_and_check_object(
                mock_expected_class,
                "foo_access_right",
                foo_key1="foo_key1",
                foo_key2="foo_key2",
                foo_key3="foo_key3",
            )
        )
        log_error.assert_called_once_with(
            "REST-Model - user '%s' has no '%s' access on '%s': '%s'",
            "foo_user",
            "foo_access_right",
            mock_expected_class,
            {"foo_key1": "foo1", "foo_key2": "foo2", "foo_key3": "foo3"},
        )
        decode_key_component.assert_has_calls(
            [
                mock.call("foo_key1"),
                mock.call("foo_key2"),
                mock.call("foo_key3"),
            ]
        )
        mock_expected_class.ByKeys.assert_called_once_with(
            foo_key1="foo1", foo_key2="foo2", foo_key3="foo3"
        )
        mock_object.CheckAccess.assert_called_once_with("foo_access_right")

    @mock.patch.object(helpers.logging, "error")
    @mock.patch.object(helpers, "decode_key_component", side_effect=["foo1", "foo3"])
    def test_get_and_check_object(self, decode_key_component, log_error):
        """Returns requested object, when access right is granted"""
        mock_object = mock.MagicMock()
        mock_object.CheckAccess.return_value = True
        mock_expected_class = mock.MagicMock()
        mock_expected_class.ByKeys.return_value = mock_object
        self.assertEqual(
            helpers.get_and_check_object(
                mock_expected_class,
                "foo_access_right",
                foo_key1="foo_key1",
                foo_key2=2,  # using int, since some classes have non-string primary keys
                foo_key3="foo_key3",
            ),
            mock_object,
        )
        log_error.assert_not_called()
        decode_key_component.assert_has_calls(
            [
                mock.call("foo_key1"),
                mock.call("foo_key3"),
            ]
        )
        mock_expected_class.ByKeys.assert_called_once_with(
            foo_key1="foo1", foo_key2=2, foo_key3="foo3"
        )
        mock_object.CheckAccess.assert_called_once_with("foo_access_right")

    @mock.patch.object(helpers.logging, "warning")
    @mock.patch.object(helpers.fls, "is_available")
    def test_is_feature_licensed_no_feature_given(self, is_avaiable, mock_warning):
        "Returns True, if no feature was requested"
        self.assertTrue(helpers.is_feature_licensed([]))

        mock_warning.assert_not_called()
        is_avaiable.assert_not_called()

    @mock.patch.object(helpers.logging, "warning")
    @mock.patch.object(helpers.fls, "is_available", return_value=True)
    def test_is_feature_licensed(self, is_avaiable, mock_warning):
        "Returns True, if requested feature is licensed."
        self.assertTrue(helpers.is_feature_licensed(["foo", "bar"]))

        mock_warning.assert_not_called()
        is_avaiable.assert_has_calls([mock.call("foo"), mock.call("bar")])

    @mock.patch.object(helpers.logging, "warning")
    @mock.patch.object(helpers.fls, "is_available", side_effect=[True, False])
    def test_is_feature_licensed_unlicensed_feature(self, is_avaiable, mock_warning):
        "Returns False, if at least one requested feature is not licensed"
        self.assertFalse(helpers.is_feature_licensed(["foo", "bar"]))

        mock_warning.assert_called_once_with("Missing license features %s", ["bar"])
        is_avaiable.assert_has_calls([mock.call("foo"), mock.call("bar")])


if __name__ == "__main__":
    unittest.main()
