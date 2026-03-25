# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tests material assignment to parts
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import cdbuuid, constants, i18n, ElementsError
from cdb.objects.operations import operation
from cdb.testcase import RollbackTestCase
from cs.materials import Material, MaterialStates

from cs.vp.items.tests.test_items import generateItem
from cs.vp.tests import test_utils


def generateMaterial(name, short_name="", status=MaterialStates.DRAFT):

    # Create Material in status DRAFT
    create_args = {
        "name_" + i18n.default(): name,
        "short_name": short_name if short_name else cdbuuid.create_uuid(),
    }
    material = operation(constants.kOperationNew, Material, **create_args)

    # if requested, change the material to the desired status
    if status == MaterialStates.REVIEW:
        material.ChangeState(MaterialStates.REVIEW)
    elif status == MaterialStates.RELEASED:
        material.ChangeState(MaterialStates.REVIEW)
        material.ChangeState(MaterialStates.RELEASED)
    elif status == MaterialStates.OBSOLETE:
        material.ChangeState(MaterialStates.REVIEW)
        material.ChangeState(MaterialStates.RELEASED)
        material.ChangeState(MaterialStates.OBSOLETE)

    return material


class TestMaterials(RollbackTestCase):
    def setUp(self):
        super(TestMaterials, self).setUp()

    def test_release_part_reject(self):
        """
        Asserts that a part which has a material assigned can not be released if the material is not released
        """

        material_name = "TestMaterials:test_release_part_reject"

        material = generateMaterial(material_name)

        item = generateItem()
        item.material_object_id = material.cdb_object_id
        item.ChangeState(100)

        expectedMsg = str(test_utils.get_error_message("csvp_material_not_released"))
        expectedMsg = expectedMsg.replace("'%s'", ".*")
        with self.assertRaisesRegex(ElementsError, expectedMsg):
            item.ChangeState(200)

    def test_release_part_succeed(self):
        """
        Asserts that a part which has a material assigned can be released if the material is also released
        """

        material_name = "TestMaterials:test_release_part_reject"

        material = generateMaterial(material_name, status=MaterialStates.RELEASED)

        item = generateItem()
        item.material_object_id = material.cdb_object_id
        item.ChangeState(100)

        item.ChangeState(200)
        self.assertEqual(item.status, 200)
