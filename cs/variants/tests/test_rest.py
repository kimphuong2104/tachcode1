# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
import unittest

from cs.variants.rest import is_incomplete


def get_classification_data_with_value(value):
    return {"prop": [{"property_type": "text", "value": value}]}


class TestRest(unittest.TestCase):
    def test_is_incomplete_false_result(self):
        test_classification = get_classification_data_with_value("abc")
        result = is_incomplete(test_classification)

        self.assertFalse(result)

    def test_is_incomplete_true_result(self):
        test_classification = get_classification_data_with_value(None)
        result = is_incomplete(test_classification)

        self.assertTrue(result)

    def test_is_incomplete_compatability_kwarg_false_result(self):
        """
        Test for compatability reasons mainly with cs.designpush (E070936)
        """
        test_classification = get_classification_data_with_value("abc")
        result = is_incomplete(test_classification, ["testing_compatability"])

        self.assertFalse(result)

    def test_is_incomplete_compatability_kwarg_true_result(self):
        """
        Test for compatability reasons mainly with cs.designpush (E070936)
        """
        test_classification = get_classification_data_with_value(None)
        result = is_incomplete(test_classification, ["testing_compatability"])

        self.assertTrue(result)
