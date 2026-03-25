#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import unittest

import mock
import pytest

from cs.pcs.resources import org_extensions


@pytest.mark.unit
class Person(unittest.TestCase):
    @mock.patch.object(
        org_extensions.Person,
        "ByKeys",
        return_value=mock.Mock(Resource=None, is_resource=1),
    )
    def test__sync_pers_no_resource(self, ByKeys):
        ByKeys.return_value.getPersistentObject.return_value.Resource = None
        self.assertIsNone(org_extensions.Person._sync_pers("foo", False))

    @mock.patch.object(
        org_extensions.Person, "ByKeys", return_value=mock.Mock(is_resource="")
    )
    def test__sync_pers_empty_string(self, _):
        self.assertIsNone(org_extensions.Person._sync_pers("foo", False))

    @mock.patch.object(
        org_extensions.Person, "ByKeys", return_value=mock.Mock(is_resource=None)
    )
    def test__sync_pers_none(self, _):
        self.assertIsNone(org_extensions.Person._sync_pers("foo", False))

    @mock.patch.object(
        org_extensions.Person, "ByKeys", return_value=mock.Mock(is_resource=0)
    )
    def test__sync_pers_0(self, _):
        self.assertIsNone(org_extensions.Person._sync_pers("foo", False))

    @mock.patch.object(
        org_extensions.Person, "ByKeys", return_value=mock.Mock(is_resource=1)
    )
    def test__sync_pers_1(self, _):
        with self.assertRaises(org_extensions.ue.Exception) as error:
            org_extensions.Person._sync_pers("foo", False)

        self.assertEqual(
            str(error.exception),
            "Die Ressourcenmarkierung kann nicht entfernt werden, da "
            "die Person als Ressource einem Ressourcenpool zugeordnet ist.",
        )

    @mock.patch.object(
        org_extensions.Person, "ByKeys", return_value=mock.Mock(is_resource="1")
    )
    def test__sync_pers_1_no_change(self, _):
        self.assertIsNone(org_extensions.Person._sync_pers("foo", True))


if __name__ == "__main__":
    unittest.main()
