# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
from cdb import constants
from cdb.objects import operations
from cs.classification import catalog
from cs.classification.tests import utils


class PropertyTests(utils.ClassificationTestCase):
    def setUp(self):
        super(PropertyTests, self).setUp()

        self.properties = {
            "external": catalog.Property.ByKeys(code="TEST_PROP_EXTERNAL_TEXT"),
        }

    def test_modify_property_from_external_system(self):
        """It is not possible to modify properties, which have the flag 'external'"""
        prop = self.properties["external"]
        self.assertIsNotNone(prop)

        self.assertFalse(prop.CheckAccess("save"))

        with self.assertRaisesRegex(RuntimeError, "Sie haben keine Berechtigung für die Operation 'Ändern'"):
            operations.operation(constants.kOperationModify, prop, name_de="MODIFIED NAME")
