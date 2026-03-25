# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

import json
import os

from webtest import TestApp as Client

from cdb import ElementsError
from cdb.objects.operations import operation
from cs.classification import api as classification_api
from cs.materials import Material, MaterialStates
from cs.materials.curve import Curve
from cs.materials.diagram import Diagram
from cs.materials.tests import MaterialsTestCase, test_utils, test_utils_context
from cs.platform.web.root import Root


class TestMaterial(MaterialsTestCase):
    def test_recursive_hierarchy_one(self):
        name = "TestMaterial:test_recursive_hierarchy_one"

        # Create a Material record
        material = test_utils.create_material(name)

        # Try to create a hierarchy which recursively assigns the material to itself
        with self.assertRaises(ElementsError):
            test_utils.create_material2material(material, material)

    def test_recursive_hierarchy_two(self):
        name = "TestMaterial:test_recursive_hierarchy_two"

        # Create two Material objects
        material1 = test_utils.create_material(name)
        material2 = test_utils.create_material(name)

        # create a hierarchy material1 => material2
        test_utils.create_material2material(material1, material2)

        # Try to create a hierarchy which would result in a recursion like
        # material1 => material2 => material1 => ...
        with self.assertRaises(ElementsError):
            test_utils.create_material2material(material2, material1)

    def test_recursive_hierarchy_mult(self):
        name = "TestMaterial:test_recursive_hierarchy_mult"

        # Create some Material objects
        material1 = test_utils.create_material(name)
        material2 = test_utils.create_material(name)
        material3 = test_utils.create_material(name)
        material4 = test_utils.create_material(name)

        # create a hierarchy material1 => material2 => material3 => material4
        test_utils.create_material2material(material1, material2)
        test_utils.create_material2material(material2, material3)
        test_utils.create_material2material(material3, material4)

        # Try to create a hierarchy which would result in a recursion
        with self.assertRaises(ElementsError):
            test_utils.create_material2material(material4, material1)

    def test_release_parent_fails(self):
        name = "TestMaterial:test_release_parent_fails"

        # Create some Material objects
        mParent = test_utils.create_material(name)
        mChild1 = test_utils.create_material(name)
        mChild2 = test_utils.create_material(name)

        # create a simple hierarchy:
        # mParent
        #     +--- mChild1
        #     +--- mChild2
        test_utils.create_material2material(mParent, mChild1)
        test_utils.create_material2material(mParent, mChild2)

        # Change parent to "Released" - must fail since the sub materials are not released yet
        mParent.ChangeState(MaterialStates.REVIEW)
        with self.assertRaises(ElementsError):
            mParent.ChangeState(MaterialStates.RELEASED)

    def test_release_parent_success(self):
        name = "TestMaterial:test_release_parent_success"

        # Create some Material objects
        mParent = test_utils.create_material(name)
        mChild1 = test_utils.create_material(name)
        mChild2 = test_utils.create_material(name)

        # create a simple hierarchy:
        # mParent
        #     +--- mChild1
        #     +--- mChild2
        test_utils.create_material2material(mParent, mChild1)
        test_utils.create_material2material(mParent, mChild2)

        # Change child materials to "Released"
        mChild1.ChangeState(MaterialStates.REVIEW)
        mChild1.ChangeState(MaterialStates.RELEASED)
        mChild2.ChangeState(MaterialStates.REVIEW)
        mChild2.ChangeState(MaterialStates.RELEASED)

        # Change parent to "Released" - must succeed since all children are released
        mParent.ChangeState(MaterialStates.REVIEW)
        mParent.ChangeState(MaterialStates.RELEASED)
        self.assertEqual(mParent.status, MaterialStates.RELEASED)

    def test_protection_class(self):
        name = "TestMaterial:test_protection_class"

        # Create a Material object
        material = test_utils.create_material(name)

        # No exception must be thrown - modify right is granted
        operation("CDB_Modify", material, remark="Material remark 1")

        # Change material to "Released"
        material.ChangeState(MaterialStates.REVIEW)
        material.ChangeState(MaterialStates.RELEASED)

        # Exception must be thrown - modify right is not granted
        expectedMsg = str(test_utils.get_error_message("authorization8"))
        expectedMsg = expectedMsg.replace("'%s'", ".*")
        with self.assertRaisesRegexp(ElementsError, expectedMsg):
            operation("CDB_Modify", material, remark="Material remark 2")

    def test_variant_create(self):
        name = "TestMaterial:test_variant_create"

        # Create a Material object
        material = test_utils.create_material(name)

        test_utils.create_material_variant(
            material, name, short_name="VAR1", variant_type="treatment"
        )
        test_utils.create_material_variant(
            material, name, short_name="VAR2", variant_type="supplier"
        )

        # Check relationship and attributes
        mat_variants = material.MaterialVariants.Execute()
        self.assertEqual(len(mat_variants), 2)

        var1 = mat_variants[0]
        self.assertEqual(var1.variant_type, "treatment")

        var2 = mat_variants[1]
        self.assertEqual(var2.variant_type, "supplier")

    def test_variant_create_with_relationships(self):
        name = "TestMaterial:test_variant_create_with_relationships"

        # Get the existing material with all kinds of relationships and ensure that at least one
        # relationship exists
        base_material = Material.ByKeys("T000003", "")
        self.assertGreater(len(base_material.Diagrams), 0)
        childrenCount = len(base_material.MaterialChildrenRel)
        self.assertGreater(childrenCount, 0)
        self.assertGreater(len(base_material.MaterialAlternativeRel), 0)
        self.assertGreater(len(base_material.MaterialVariants), 0)
        self.assertGreater(len(base_material.MaterialDocumentRel), 0)
        self.assertGreater(len(base_material.MaterialSupplierRel), 0)

        material_variant = test_utils.create_material_variant(
            base_material, name, base_material.short_name + " var1"
        )

        # Ensure that only the composition relationships have been copied
        self.assertEqual(0, len(material_variant.Diagrams))
        self.assertEqual(childrenCount, len(material_variant.MaterialChildrenRel))
        self.assertEqual(0, len(material_variant.MaterialAlternativeRel))
        self.assertEqual(0, len(material_variant.MaterialVariants))
        self.assertEqual(0, len(material_variant.MaterialDocumentRel))
        self.assertEqual(0, len(material_variant.MaterialSupplierRel))

    def test_material_copy(self):
        name = "TestMaterial:test_material_copy"

        # Get the existing material with all kinds of relationships
        base_material = Material.ByKeys("T000003", "")
        diagramCount = len(base_material.Diagrams)
        self.assertGreater(diagramCount, 0)
        childrenCount = len(base_material.MaterialChildrenRel)
        self.assertGreater(childrenCount, 0)
        alternativeCount = len(base_material.MaterialAlternativeRel)
        self.assertGreater(alternativeCount, 0)
        variantCount = len(base_material.MaterialVariants)
        self.assertGreater(variantCount, 0)
        documentCount = len(base_material.MaterialDocumentRel)
        self.assertGreater(documentCount, 0)
        supplierCount = len(base_material.MaterialSupplierRel)
        self.assertGreater(supplierCount, 0)

        # Create a copy of the existing material
        material_copy = test_utils.copy_material(
            base_material, name, base_material.short_name + "CP"
        )

        self.assertNotEqual(base_material.material_id, material_copy.material_id)
        self.assertNotEqual(base_material.name, material_copy.name)
        self.assertEqual(material_copy.name, name)

        # Make sure that the number of relationships stays the same for the copy
        self.assertEquals(diagramCount, len(material_copy.Diagrams))
        self.assertEquals(childrenCount, len(material_copy.MaterialChildrenRel))
        self.assertEquals(alternativeCount, len(material_copy.MaterialAlternativeRel))
        self.assertEquals(variantCount, len(material_copy.MaterialVariants))
        self.assertEquals(documentCount, len(material_copy.MaterialDocumentRel))
        self.assertEquals(supplierCount, len(material_copy.MaterialSupplierRel))

    def test_material_create_index(self):
        # Get the existing material with all kinds of relationships
        source_material = Material.ByKeys("T000003", "")
        diagram_count = len(source_material.Diagrams)
        self.assertGreater(diagram_count, 0)
        children_count = len(source_material.MaterialChildrenRel)
        self.assertGreater(children_count, 0)
        alternative_count = len(source_material.MaterialAlternativeRel)
        self.assertGreater(alternative_count, 0)
        variant_count = len(source_material.MaterialVariants)
        self.assertGreater(variant_count, 0)
        document_count = len(source_material.MaterialDocumentRel)
        self.assertGreater(document_count, 0)
        supplier_count = len(source_material.MaterialSupplierRel)
        self.assertGreater(supplier_count, 0)

        # Create a new revision of the existing material
        for sub_material in source_material.MaterialChildren:
            sub_material.ChangeState(MaterialStates.REVIEW)
            sub_material.ChangeState(MaterialStates.RELEASED)
        source_material.ChangeState(MaterialStates.REVIEW)
        source_material.ChangeState(MaterialStates.RELEASED)
        material_revision = operation("csmat_create_index", source_material)

        # Assert that a new index has been created
        self.assertEqual(source_material.material_id, material_revision.material_id)
        self.assertEqual(source_material.name, material_revision.name)
        self.assertEqual(material_revision.material_index, "1")

        # Make sure that the number of relationships stays the same for the copy
        self.assertEqual(diagram_count, len(material_revision.Diagrams))
        self.assertEqual(children_count, len(material_revision.MaterialChildrenRel))
        self.assertEqual(
            alternative_count, len(material_revision.MaterialAlternativeRel)
        )
        self.assertEqual(variant_count, len(material_revision.MaterialVariants))
        self.assertEqual(document_count, len(material_revision.MaterialDocumentRel))
        self.assertEqual(supplier_count, len(material_revision.MaterialSupplierRel))

    def test_material_set_obsolete(self):
        """Checks that the cdb_status_txt field is set to the proper value when a later index is released"""
        name = "TestMaterial:test_material_set_obsolete"

        # Create a Material object and release it
        material = test_utils.create_material(name)
        material.ChangeState(MaterialStates.REVIEW)
        material.ChangeState(MaterialStates.RELEASED)
        self.assertEqual(material.cdb_status_txt, "Released")

        # Create a revision
        material_revision = operation("csmat_create_index", material)
        self.assertEqual(material_revision.cdb_status_txt, "Draft")

        material_revision.ChangeState(MaterialStates.REVIEW)
        material_revision.ChangeState(MaterialStates.RELEASED)

        # Assure that the previous material is properly set to obsolete
        material.Reload()
        self.assertEqual(material.status, MaterialStates.OBSOLETE)
        self.assertEqual(material.cdb_status_txt, "Obsolete")

    def test_material_short_name_unique(self):
        name = "TestMaterial:test_material_short_name_unique"

        # Get an existing material
        existing_material = Material.ByKeys("T000003", "")

        # Make sure that creating a new material with an existing short name raises an error
        expectedMsg = str(
            test_utils.get_error_message("csmat_material_short_name_not_unique")
        )
        expectedMsg = expectedMsg.replace("%s", ".*")
        with self.assertRaisesRegexp(ElementsError, expectedMsg):
            test_utils.create_material(name, existing_material.short_name)

    def test_material_copy_short_name_unique(self):
        name = "TestMaterial:test_material_copy_short_name_unique"

        # Get an existing material
        existing_material = Material.ByKeys("T000003", "")

        # Make sure that copying an existing material and keeping the short name raises an error
        expectedMsg = str(
            test_utils.get_error_message("csmat_material_short_name_not_unique")
        )
        expectedMsg = expectedMsg.replace("%s", ".*")
        with self.assertRaisesRegexp(ElementsError, expectedMsg):
            test_utils.copy_material(
                existing_material, name, existing_material.short_name
            )

    def test_material_modify_short_name_unique(self):
        # Get an existing material
        existing_material = Material.ByKeys("T000003", "")

        # Make sure that modifying the material works when the short_name remains unmodified
        operation("CDB_Modify", existing_material, remark="Material remark 1")

        # Make sure that changing the short_name to an existing value raises an error
        expectedMsg = str(
            test_utils.get_error_message("csmat_material_short_name_not_unique")
        )
        expectedMsg = expectedMsg.replace("%s", ".*")
        with self.assertRaisesRegexp(ElementsError, expectedMsg):
            operation("CDB_Modify", existing_material, short_name="GF")

    def test_material_variant_explosion(self):
        # Get the existing material with a variant structure tree
        source_material = Material.ByKeys("T000003", "")

        # Recursively get all variants of that material
        all_variants = source_material.get_variants_deep()
        self.assertEqual(len(all_variants), 6)

        # Create lookup table for the material id (variant hierarchy test data has an empty index)
        variant_map = {}
        for variant in all_variants:
            variant_map[variant.material_id] = variant

        # check the hierarchy
        t000005 = variant_map["T000005"]
        t000012 = variant_map["T000012"]
        self.assertEqual(t000005.cdb_object_id, t000012.variant_of_oid)
        self.assertEqual(source_material.cdb_object_id, t000005.variant_of_oid)

        t000004 = variant_map["T000004"]
        t000009 = variant_map["T000009"]
        t000010 = variant_map["T000010"]
        t000011 = variant_map["T000011"]
        self.assertEqual(source_material.cdb_object_id, t000004.variant_of_oid)
        self.assertEqual(t000004.cdb_object_id, t000009.variant_of_oid)
        self.assertEqual(t000009.cdb_object_id, t000010.variant_of_oid)
        self.assertEqual(t000009.cdb_object_id, t000011.variant_of_oid)

    def test_material_variant_parents(self):
        # Get the existing material with a variant structure tree
        source_material = Material.ByKeys("T000012", "")

        # Recursively get all parent variants of that material
        all_variants = source_material.get_parent_variants()
        self.assertEqual(len(all_variants), 2)

        # Create lookup table for the material id (variant hierarchy test data has an empty index)
        variant_map = {}
        for variant in all_variants:
            variant_map[variant.material_id] = variant

        # check the hierarchy
        t000003 = variant_map["T000003"]
        t000005 = variant_map["T000005"]
        self.assertEqual(t000005.cdb_object_id, source_material.variant_of_oid)
        self.assertEqual(t000003.cdb_object_id, t000005.variant_of_oid)

    def test_export_material(self):
        name = "TestMaterial:test_export_material"

        client = Client(Root())

        # Create material test data for export
        material = test_utils.create_material(name)
        classification_data = classification_api.get_new_classification(
            ["cs_materials_mild_steel"]
        )
        classification_data["properties"]["cs_materials_metals_cs_materials_density"][
            0
        ]["value"]["float_value"] = 123.456
        classification_api.update_classification(material, classification_data)
        diagram = test_utils.create_diagram(material, "Stress-Strain")
        curves_by_label = {
            "0°C": test_utils.create_curve(
                diagram,
                "0°C",
                curve_data="""
                    {
                        "x": [1, 2, 3, 4, 5, 6, 7, 8],
                        "y": [24.8, 28.9, 31.3, 33.0, 34.9, 35.6, 38.4, 39.2]
                    }
                """,
            ),
            "20°C": test_utils.create_curve(
                diagram,
                "20°C",
                curve_data="""
                    {
                        "x": [1, 2, 3, 4, 5, 6, 7, 8],
                        "y": [19.6, 24.1, 26.7, 28.3, 27.5, 30.5, 32.8, 33.1]
                    }
                """,
            ),
            "Empty": test_utils.create_curve(diagram, "Empty", curve_data=""),
            "Error": test_utils.create_curve(
                diagram,
                "Error",
                curve_data="""
                    {
                        "x": [1, 2,, 3, 4, 5, 6, 7, 8],
                        "y": [19.6, 24.1, 26.7, 28.3, 27.5, 30.5, 32.8, 33.1]
                    }
                """,
            ),
        }

        for uses_webui in [True, False]:
            ctx = test_utils_context.TestImportContext(
                export_file="material_export.json", uses_webui=uses_webui
            )
            material.export(ctx)

            # Read the file contents
            if ctx.uses_webui:
                # Web UI
                result = client.get(ctx.dest_url, status=200)
                export_data = json.loads(result.body)
            else:
                # PC Client
                self.assertTrue(os.path.isfile(ctx.server_file))
                with open(ctx.server_file, encoding="utf-8") as server_file:
                    export_data = json.load(server_file)

            # check attributes
            for attr in Material.EXPORT_ATTRIBUTES:
                self.assertEquals(export_data[attr], material[attr])
            self.assertEquals(export_data["variant_of_id"], None)
            self.assertEquals(export_data["variant_of_index"], None)
            # check material classification
            self.assertEquals(
                export_data["properties"]["cs_materials_metals_cs_materials_density"][
                    0
                ]["value"]["float_value"],
                classification_data["properties"][
                    "cs_materials_metals_cs_materials_density"
                ][0]["value"]["float_value"],
            )
            # check data table attributes
            for attr in Diagram.EXPORT_ATTRIBUTES:
                self.assertEquals(export_data["curve_data"][0][attr], diagram[attr])
            # check curves
            for curve_data in export_data["curve_data"][0]["curves"]:
                curve = curves_by_label[curve_data["label"]]
                self.assertIsNotNone(curve)
                # check curve attributes
                for attr in Curve.EXPORT_ATTRIBUTES:
                    self.assertEquals(curve_data[attr], curve[attr])
                # check curve classification
                self.assertEquals(curve_data["properties"], {})
                # check curve data
                try:
                    json_data = json.loads(curve.GetText("curve_data"))
                except Exception:  # pylint: disable=W0703
                    # curve with json error are exported as empty lists
                    json_data = {"x": [], "y": []}
                self.assertListEqual(curve_data["x"], json_data["x"])
                self.assertListEqual(curve_data["y"], json_data["y"])
