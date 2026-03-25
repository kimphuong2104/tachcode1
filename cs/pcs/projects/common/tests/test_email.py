#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access,abstract-method

import unittest

import mock
import pytest
from cdb import rte, testcase
from cdb.objects.org import User

from cs.pcs.projects.common import email


@pytest.mark.unit
class Utility(testcase.RollbackTestCase):
    def _create_user(self, persno):
        return User.Create(personalnummer=persno)

    def test_get_email_links_no_params(self):
        self.assertEqual(email.get_email_links(), ([], None))

    def test_get_email_links_param_no_tuple(self):
        with self.assertRaises(TypeError):
            email.get_email_links(42)

    def test_get_email_links_param_no_3_tuple(self):
        with self.assertRaises(ValueError):
            email.get_email_links((1, 2))

    def test_get_email_links_param_1_no_obj(self):
        with self.assertRaises(AttributeError):
            email.get_email_links((1, 2, 3))

    @mock.patch.dict(rte.environ, {"CADDOK_WWWSERVICE_URL": "http://foo"})
    def test_get_email_links(self):
        a = self._create_user("TEST_EMAIL_A")
        b = self._create_user("TEST_EMAIL_B")
        links = email.get_email_links((a, "foo", "bar"), (b, "baz", "boo"))

        self.assertEqual(
            links,
            (
                [
                    (
                        "cdb:///byname/classname/angestellter/bar/interactive?angestellter.personalnummer=TEST_EMAIL_A",  # noqa
                        "foo (Client)",
                    ),
                    (
                        "cdb:///byname/classname/angestellter/boo/interactive?angestellter.personalnummer=TEST_EMAIL_B",  # noqa
                        "baz (Client)",
                    ),
                ],
                [
                    ("http://foo/info/person/TEST_EMAIL_A", "foo (Browser)"),
                    ("http://foo/info/person/TEST_EMAIL_B", "baz (Browser)"),
                ],
            ),
        )

    @mock.patch.object(email.logging, "info")
    @mock.patch.dict(rte.environ, {"CADDOK_WWWSERVICE_URL": "http://www.example.org"})
    def test_get_email_links_no_web_links(self, info):
        a = self._create_user("TEST_EMAIL_A")
        b = self._create_user("TEST_EMAIL_B")
        links = email.get_email_links((a, "foo", "bar"), (b, "baz", "boo"))

        self.assertEqual(
            links,
            (
                [
                    (
                        "cdb:///byname/classname/angestellter/bar/interactive?angestellter.personalnummer=TEST_EMAIL_A",  # noqa
                        "foo (Client)",
                    ),
                    (
                        "cdb:///byname/classname/angestellter/boo/interactive?angestellter.personalnummer=TEST_EMAIL_B",  # noqa
                        "baz (Client)",
                    ),
                ],
                None,
            ),
        )

        info.assert_called_once_with(
            "set the root URL to something else than '%s' "
            "to include web links in issue e-mail notifications",
            "http://www.example.org",
        )


if __name__ == "__main__":
    unittest.main()
