# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module block properties tests

"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import constants
from cdb.objects import operations

from cs.classification import catalog

from cs.classification.tests import utils


class BlockPropertyTests(utils.ClassificationTestCase):

    def setUp(self):
        super(BlockPropertyTests, self).setUp()

        self.properties = {
            "root": catalog.Property.ByKeys(code="TEST_PROP_BLOCK_HIERARCHIE"),
            "level 1": catalog.Property.ByKeys(code="TEST_PROP_BLOCK_LEVEL_1"),
            "level 2": catalog.Property.ByKeys(code="TEST_PROP_BLOCK_LEVEL_2"),
            "level 3": catalog.Property.ByKeys(code="TEST_PROP_BLOCK_LEVEL_3"),
            "level 4": catalog.Property.ByKeys(code="TEST_PROP_BLOCK_LEVEL_4"),
            "int": catalog.Property.ByKeys(code="TEST_PROP_INT"),
            "text": catalog.Property.ByKeys(code="TEST_PROP_TEXT"),
        }

    def _assign_property(self, block_prop, assigned_prop):
        operations.operation(
            constants.kOperationNew,  # @UndefinedVariable
            catalog.BlockPropertyAssignment,
            block_property_code=block_prop.code,
            assigned_property_code=assigned_prop.code,
            assigned_property_object_id=assigned_prop.cdb_object_id
        )

    def test_assigning_block_property_to_itsself(self):
        """Block property cannot be added as assigned property to itsself."""

        block_prop = self.properties["root"]
        assigned_prop = self.properties["root"]

        with self.assertRaisesRegex(RuntimeError, "Rekursive Blockmerkmale werden nicht unterstützt."):
            self._assign_property(block_prop, assigned_prop)

    def test_assigning_block_property_recursive(self):
        """Block property cannot be added as assigned property if this leads to a recursion    ."""

        block_prop = self.properties["level 4"]
        assigned_prop = self.properties["root"]

        with self.assertRaisesRegex(RuntimeError, "Rekursive Blockmerkmale werden nicht unterstützt."):
            self._assign_property(block_prop, assigned_prop)

    def test_create_and_delete_catalog_block_prop_assignments(self):
        """Test creating and deleting block property assignments for catalog properties."""

        block_prop = self.properties["level 4"]
        assigned_prop = self.properties["int"]
        self._assign_property(block_prop, assigned_prop)

        block_prop_assignment = catalog.BlockPropertyAssignment.ByKeys(
            block_property_code=block_prop.code, assigned_property_code=assigned_prop.code
        )
        assert block_prop_assignment
        operations.operation(
            constants.kOperationDelete,  # @UndefinedVariable
            block_prop_assignment
        )

    def test_prevent_delete_of_catalog_block_assignment_that_is_used_in_class(self):
        """Test that catalog block property assignment cannot be deleted if block property is used in a class."""

        block_prop = self.properties["root"]
        assigned_prop = self.properties["level 1"]

        propagated_assignment = catalog.BlockPropertyAssignment.ByKeys(
            block_property_code=block_prop.code, assigned_property_code=assigned_prop.code
        )
        assert propagated_assignment

        with self.assertRaisesRegex(RuntimeError, "Fehler beim Löschen von TEST_PROP_BLOCK_LEVEL_1:\nDas Merkmal wird in Klassen verwendet und kann daher nicht angepasst werden."):
            operations.operation(
                constants.kOperationDelete,  # @UndefinedVariable
                propagated_assignment
            )
