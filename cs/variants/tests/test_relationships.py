# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb.objects import operations
from cdb.objects.operations import form_input
from cs.variants import VariantPart
from cs.variants.tests import common

# noinspection PyProtectedMember
from cs.vp.products import ProductPart


class TestRelationships(common.VariantsNoSubComponentCase):
    def setUp(self):
        super().setUp()

        self.variant = common.generate_variant(
            self.variability_model,
            {
                self.prop1: "VALUE1",
                self.prop2: "VALUE2",
            },
        )

    def test_add_maxbom_to_varmodel_add_relationship_product(self):
        """
        Adding a maxbom to a variabilitymodel should also add the maxbom to
        project <=> part relationship table
        """

        # this should already done by setup
        self.assertEqual(
            len(ProductPart.KeywordQuery(product_object_id=self.product.cdb_object_id)),
            1,
        )

    def test_instantiate_part_adds_part_to_product_relationship(self):
        """
        Instantiate part should also add the new part to project <=> part relationship table
        """
        self.assertEqual(len(self.variant.Instances), 0)

        inst_part = operations.operation(
            "cs_variant_instantiate",
            self.variant,
            form_input(self.variant, max_bom_id=self.maxbom.cdb_object_id),
        )
        self.assertIsNotNone(inst_part)

        self.assertEqual(len(self.variant.Instances), 1)

        x = VariantPart.KeywordQuery(
            variability_model_id=self.variability_model.cdb_object_id,
            variant_id=self.variant.id,
        )

        self.assertEqual(len(x), 1)
