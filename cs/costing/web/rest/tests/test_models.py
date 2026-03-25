# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest
from mock import MagicMock
from cs.costing.web.rest import CloneAttributes
from cs.costing.calculations import Calculation


class TestCloneAttributes(unittest.TestCase):

    def test___init__(self):
        """Skipped, since it only fetches Calculation based on given id."""
        pass
    
    def test_get_clone_attributes_for_sqlite(self):
        """Test for sqlite-like behaviour, i.e. cstruct contains tuples."""
        comp_1 = MagicMock(
            comp_object_id="foo_1",
            parent_object_id="bar_1",
            cdb_object_id="baz_1",
            quantity="quantity_1",
        )
        comp_2 = MagicMock(
            comp_object_id="foo_2",
            parent_object_id="bar_2",
            cdb_object_id="baz_2",
            quantity="quantity_2",
        )
        top_comp = MagicMock(
            comp_object_id="foo_top",
            parent_object_id="bar_top",
            cdb_object_id="baz_top",
            quantity="quantity_top",
        )
        mock_calc = MagicMock(spec=Calculation, TopComponents=[top_comp])
        # Test for having two values in tuple
        mock_calc.get_components_from_structure = MagicMock(return_value=[(comp_1, comp_2)])
        mock_model = MagicMock(spec=CloneAttributes, calc=mock_calc)

        self.assertDictEqual(
            CloneAttributes.get_clone_attributes(mock_model),
            {
                "baz_top@|": {
                    "quantity": "quantity_top"
                },
                "foo_2@bar_2|baz_2": {
                    "quantity": "quantity_2"
                },
            }
        )
        # Test for having only one value in tuple
        mock_calc.get_components_from_structure = MagicMock(return_value=[(comp_1, None)])
        mock_model = MagicMock(spec=CloneAttributes, calc=mock_calc)

        self.assertDictEqual(
            CloneAttributes.get_clone_attributes(mock_model),
            {
                "baz_top@|": {
                    "quantity": "quantity_top"
                },
                "baz_1@bar_1|": {
                    "quantity": "quantity_1"
                },
            }
        )

    def test_get_clone_attributes_for_non_sqlite(self):
        """Test for non-sqlite-like behaviour, i.e. cstruct contains non-tuples"""
        comp = MagicMock(
            cdb_object_id="foo",
            combined_parent="bar",
            combined_id="baz",
            combined_quantity="quantity"
        )
        top_comp = MagicMock(
            comp_object_id="foo_top",
            parent_object_id="bar_top",
            cdb_object_id="baz_top",
            quantity="quantity_top"
        )
        mock_calc = MagicMock(spec=Calculation, TopComponents=[top_comp])
        # Test for having two values in tuple
        mock_calc.get_components_from_structure = MagicMock(return_value=[comp])
        mock_model = MagicMock(spec=CloneAttributes, calc=mock_calc)

        self.assertDictEqual(
            CloneAttributes.get_clone_attributes(mock_model),
            {
                "baz_top@|": {
                    "quantity": "quantity_top"
                },
                "foo@bar|baz": {
                    "quantity": "quantity"
                },
            }
        )


if __name__ == "__main__":
    unittest.main()
