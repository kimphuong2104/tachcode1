# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from cdb import cdbuuid, constants
from cdb.objects.operations import operation
from cs.materials import MaterialStates
from cs.materials.diagram import Diagram
from cs.materials.tests import MaterialsTestCase, test_utils


class TestDiagram(MaterialsTestCase):
    def test_material_relationship(self):
        name = "TestCatalogPropertyValue:test_material_relationship"

        material = test_utils.create_material(name)
        diagram = test_utils.create_diagram(material, name)

        parent_material = diagram.Material
        self.assertEqual(material.cdb_object_id, parent_material.cdb_object_id)

    def test_copy_material(self):
        name = "TestCatalogPropertyValue:test_copy_material"

        material = test_utils.create_material(name)
        test_utils.create_diagram(material, name)
        material_copy = operation(
            constants.kOperationCopy, material, short_name=cdbuuid.create_uuid()
        )
        material_id = material_copy.material_id
        material_index = material_copy.material_index

        diagrams = Diagram.KeywordQuery(
            material_id=material_id, material_index=material_index
        )
        self.assertEqual(1, len(diagrams))

    def test_delete_material(self):
        name = "TestCatalogPropertyValue:test_delete_material"

        material = test_utils.create_material(name)
        material_id = material.material_id
        material_index = material.material_index
        test_utils.create_diagram(material, name)

        operation(constants.kOperationDelete, material)

        diagrams = Diagram.KeywordQuery(
            material_id=material_id, material_index=material_index
        )
        self.assertEqual(0, len(diagrams))

    def test_index_material(self):
        name = "TestCatalogPropertyValue:test_index_material"

        material = test_utils.create_material(name, status=MaterialStates.REVIEW)
        test_utils.create_diagram(material, name)
        material.ChangeState(MaterialStates.RELEASED)

        material_index = operation(
            "csmat_create_index",
            material,
        )
        material_id = material_index.material_id
        material_index = material_index.material_index

        diagrams = Diagram.KeywordQuery(
            material_id=material_id, material_index=material_index
        )
        self.assertEqual(1, len(diagrams))
