# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from webtest import TestApp as Client

from cs.materials import Material
from cs.materials.tests import MaterialsTestCase
from cs.platform.web.root import Root


class TestDiff(MaterialsTestCase):
    def setUp(self):
        super(TestDiff, self).setUp()
        self.client = Client(Root())

    def test_get_material_curves(self):
        material_id = "T000013"
        url = "/internal/cs_materials_diff/material/{}@".format(material_id)
        res = self.client.get(url).json
        material = res.get("material")
        self.assertIsNotNone(material)
        self.assertEqual(material["short_name"], "T000013")

    def test_get_material_curves_inherited(self):
        material_id = "T000011"
        url = "/internal/cs_materials_diff/material/{}@".format(material_id)
        res = self.client.get(url).json

        material = res.get("material")
        self.assertIsNotNone(material)
        self.assertEqual(material["material_id"], material_id)

        diagrams = res.get("diagrams")
        self.assertIsNotNone(diagrams)
        self.assertTrue("Stress-Strain-Temperature" in diagrams)
        self.assertTrue("Stress-Strain-StrainRate" in diagrams)

        curves = res.get("curves")
        self.assertIsNotNone(curves)
        for _, diagram in diagrams.items():
            self.assertIsNotNone(curves.get(diagram["cdb_object_id"]))

    def test_materials_metadata_diff(self):
        material0 = Material.ByKeys("T000003", "")
        material1 = Material.ByKeys("T000004", "")
        material0_oid = material0.cdb_object_id
        material1_oid = material1.cdb_object_id

        url = "/internal/cs_materials_diff/metadata/{}/{}".format(
            material0_oid, material1_oid
        )
        res = self.client.get(url).json

        left_title = res["left_title"]
        right_title = res["right_title"]
        attribute_diff = res["attribute_diff"]

        self.assertEqual(left_title, material0.GetDescription())
        self.assertEqual(right_title, material1.GetDescription())

        short_name_diff = attribute_diff["short_name"]
        variant_type_name_diff = attribute_diff["mapped_variant_type_name_de"]
        derived_from_diff = attribute_diff["derived_from"]
        application_diff = attribute_diff["application"]

        self.assertTrue(short_name_diff["changed"])
        self.assertTrue(variant_type_name_diff["changed"])
        self.assertTrue(derived_from_diff["changed"])
        self.assertFalse(application_diff["changed"])
