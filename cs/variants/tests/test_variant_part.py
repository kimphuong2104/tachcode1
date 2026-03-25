# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import constants, testcase
from cdb.objects import operations
from cs.variants import VariantPart
from cs.variants.tests.common import generate_part


class TestVariantPart(testcase.RollbackTestCase):
    def setUp(self):
        super().setUp()

        self.part_1 = generate_part()
        self.part_2 = generate_part()
        self.part_3 = generate_part()

    @staticmethod
    def create_variant_part(part, variant_id=1, variability_model_id="abc"):
        VariantPart.Create(
            teilenummer=part.teilenummer,
            t_index=part.t_index,
            variant_id=variant_id,
            variability_model_id=variability_model_id,
        )

    def build_data(self, variant_parts_to_generate, variant_parts_to_check):
        for each in variant_parts_to_generate:
            self.create_variant_part(each)

        return VariantPart.get_all_belonging_to_parts(variant_parts_to_check)

    @staticmethod
    def get_ids(data):
        return ["{0}_{1}".format(each.teilenummer, each.t_index) for each in data]

    def test_get_all_belonging_to_parts_1_3(self):
        variant_parts_to_generate = [self.part_1]
        variant_parts_to_check = [self.part_1, self.part_2, self.part_3]

        result = self.build_data(variant_parts_to_generate, variant_parts_to_check)

        self.assertEqual(1, len(result))
        self.assertListEqual(
            self.get_ids(variant_parts_to_generate), self.get_ids(result)
        )

    def test_get_all_belonging_to_parts_2_3(self):
        variant_parts_to_generate = [self.part_1, self.part_2]
        variant_parts_to_check = [self.part_1, self.part_2, self.part_3]

        result = self.build_data(variant_parts_to_generate, variant_parts_to_check)

        self.assertEqual(2, len(result))
        self.assertListEqual(
            self.get_ids(variant_parts_to_generate), self.get_ids(result)
        )

    def test_get_all_belonging_to_parts_3_3(self):
        variant_parts_to_generate = [self.part_1, self.part_2, self.part_3]
        variant_parts_to_check = [self.part_1, self.part_2, self.part_3]

        result = self.build_data(variant_parts_to_generate, variant_parts_to_check)

        self.assertEqual(3, len(result))
        self.assertListEqual(
            self.get_ids(variant_parts_to_generate), self.get_ids(result)
        )

    def test_get_all_belonging_to_parts_3_1(self):
        variant_parts_to_generate = [self.part_1, self.part_2, self.part_3]
        variant_parts_to_check = [self.part_1]

        result = self.build_data(variant_parts_to_generate, variant_parts_to_check)

        self.assertEqual(1, len(result))
        self.assertListEqual(self.get_ids(variant_parts_to_check), self.get_ids(result))

    def test_get_all_belonging_to_parts_3_2(self):
        variant_parts_to_generate = [self.part_1, self.part_2, self.part_3]
        variant_parts_to_check = [self.part_1, self.part_2]

        result = self.build_data(variant_parts_to_generate, variant_parts_to_check)

        self.assertEqual(2, len(result))
        self.assertListEqual(self.get_ids(variant_parts_to_check), self.get_ids(result))

    def test_get_all_belonging_to_parts_1_with_index_1(self):
        part_1_indexed = operations.operation(constants.kOperationIndex, self.part_1)

        variant_parts_to_generate = [self.part_1, part_1_indexed]
        variant_parts_to_check = [self.part_1]

        result = self.build_data(variant_parts_to_generate, variant_parts_to_check)

        self.assertEqual(1, len(result))
        self.assertListEqual(self.get_ids(variant_parts_to_check), self.get_ids(result))

    def test_get_all_belonging_to_parts_1_with_index_1_with_index(self):
        part_1_indexed = operations.operation(constants.kOperationIndex, self.part_1)

        variant_parts_to_generate = [self.part_1, part_1_indexed]
        variant_parts_to_check = [self.part_1, part_1_indexed]

        result = self.build_data(variant_parts_to_generate, variant_parts_to_check)

        self.assertEqual(2, len(result))
        self.assertListEqual(self.get_ids(variant_parts_to_check), self.get_ids(result))

    def test_get_all_belonging_to_parts_2_with_index_1(self):
        part_1_indexed = operations.operation(constants.kOperationIndex, self.part_1)

        variant_parts_to_generate = [self.part_1, part_1_indexed, self.part_2]
        variant_parts_to_check = [self.part_1]

        result = self.build_data(variant_parts_to_generate, variant_parts_to_check)

        self.assertEqual(1, len(result))
        self.assertListEqual(self.get_ids(variant_parts_to_check), self.get_ids(result))

    def test_get_all_belonging_to_parts_2_with_index_2(self):
        part_1_indexed = operations.operation(constants.kOperationIndex, self.part_1)

        variant_parts_to_generate = [self.part_1, part_1_indexed, self.part_2]
        variant_parts_to_check = [part_1_indexed, self.part_2]

        result = self.build_data(variant_parts_to_generate, variant_parts_to_check)

        self.assertEqual(2, len(result))
        self.assertListEqual(self.get_ids(variant_parts_to_check), self.get_ids(result))

    def test_get_all_belonging_to_parts_3_with_index_2(self):
        part_1_indexed = operations.operation(constants.kOperationIndex, self.part_1)
        part_2_indexed = operations.operation(constants.kOperationIndex, self.part_2)
        part_3_indexed = operations.operation(constants.kOperationIndex, self.part_3)

        variant_parts_to_generate = [
            self.part_1,
            part_1_indexed,
            self.part_2,
            part_2_indexed,
            self.part_3,
            part_3_indexed,
        ]
        variant_parts_to_check = [part_2_indexed, self.part_3]

        result = self.build_data(variant_parts_to_generate, variant_parts_to_check)

        self.assertEqual(2, len(result))
        self.assertListEqual(self.get_ids(variant_parts_to_check), self.get_ids(result))
