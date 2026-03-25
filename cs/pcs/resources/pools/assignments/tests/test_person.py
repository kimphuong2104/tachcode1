#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

# Since also protected method have to be tested ignore warnings for protected access
# pylint: disable=protected-access

import unittest

import mock
import pytest

from cdb import testcase
from cs.pcs.resources.pools.assignments import Resource, person


def setup_module():
    testcase.run_level_setup()


@pytest.mark.unit
class TestPerson(unittest.TestCase):
    @mock.patch.object(Resource, "ByKeys")
    def test__on_modify_resource_post_abort(self, ByKeys):
        mock_ctx = mock.MagicMock()
        mock_person = mock.MagicMock(person.Person)
        mock_ctx.error = True

        person.Person._on_modify_resource_post(mock_person, mock_ctx)
        mock_person.create_resource.assert_not_called()
        mock_person.delete_resource.assert_not_called()
        ByKeys.assert_not_called()

    @mock.patch.object(Resource, "ByKeys")
    def test__on_modify_resource_post_new_resource(self, ByKeys):
        mock_ctx = mock.MagicMock()
        mock_person = mock.MagicMock(person.Person)
        mock_ctx.error = False
        mock_person.is_resource = True
        mock_person.Resource = None

        person.Person._on_modify_resource_post(mock_person, mock_ctx)
        mock_person.create_resource.assert_called_once()
        mock_person.delete_resource.assert_not_called()
        ByKeys.assert_not_called()

    @mock.patch.object(Resource, "ByKeys")
    def test__on_modify_resource_post_delete_resource(self, ByKeys):
        mock_ctx = mock.MagicMock()
        mock_person = mock.MagicMock(person.Person)
        mock_ctx.error = False
        mock_person.is_resource = False
        mock_person.Resource = True

        person.Person._on_modify_resource_post(mock_person, mock_ctx)
        mock_person.create_resource.assert_not_called()
        mock_person.delete_resource.assert_called_once()
        ByKeys.assert_not_called()

    @mock.patch.object(Resource, "ByKeys")
    def test__on_modify_resource_post_modify_resource(self, ByKeys):
        mock_ctx = mock.MagicMock()
        mock_person = mock.MagicMock(person.Person)
        mock_ctx.error = False
        mock_person.is_resource = True
        mock_person.Resource = True
        mock_person.cdb_object_id = "oid"
        mock_resource = mock.MagicMock(Resource)
        ByKeys.return_value = mock_resource

        person.Person._on_modify_resource_post(mock_person, mock_ctx)
        mock_person.create_resource.assert_not_called()
        mock_person.delete_resource.assert_not_called()
        ByKeys.assert_called_once_with(referenced_oid="oid")
        mock_resource.createSchedules.assert_called_once()


@pytest.mark.integration
def test_overlapping_pool_assignment():
    """
    cannot create a pool assignment that overlaps with an existing one

    the error message broke in the past, so make sure the inner exception's
    message is retained
    """
    user = person.Person.ByKeys("Test.Resource.2.2")
    with pytest.raises(
        person.ElementsError,
        match="Die Mitgliedschaft liegt ganz oder teilweise im Zeitraum",
    ):
        person.operations.operation(
            "pcs_resource_assign_to_pool",
            user,
            person.operations.form_input(
                user,
                resource_oid="02ce8502-2a94-11ed-9d7f-207918bb3392",
                pool_oid="78e9e937-247c-11ee-b4e1-047bcbb395e6",
                start_date="16.10.2023",
                end_date="",
            ),
        )
