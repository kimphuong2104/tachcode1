# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tests for the tools bom_cycle_finder
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import sqlapi
from cdb.testcase import RollbackTestCase, skip_dbms
import cs.vp.bom.tests as common

from cs.vp.bom.tools.bom_cycle_finder import get_cycles


class TestCycleFinder(RollbackTestCase):
    def setUp(self):
        super(TestCycleFinder, self).setUp()
        self.test_root = common.generateItem()
        self.test_item_a = common.generateItem()
        self.test_item_b = common.generateItem()
        self.test_item_c = common.generateItem()
        self.test_item_d = common.generateItem()

        # Build the bom
        common.generateComponent(baugruppe=self.test_root.teilenummer,
                                 teilenummer=self.test_item_a.teilenummer)
        common.generateComponent(baugruppe=self.test_item_a.teilenummer,
                                 teilenummer=self.test_item_b.teilenummer)
        common.generateComponent(baugruppe=self.test_item_b.teilenummer,
                                 teilenummer=self.test_item_c.teilenummer)
        common.generateComponent(baugruppe=self.test_root.teilenummer,
                                 teilenummer=self.test_item_d.teilenummer)

    @skip_dbms(sqlapi.DBMS_SQLITE)
    def test_get_cycles_none_there(self):
        """
        GIVEN a bom without cyclicity WHEN get_cycles is run on the bom \
        THEN result length is 0
        """
        result = get_cycles(self.test_root)
        self.assertEqual(0, len(result))

    @skip_dbms(sqlapi.DBMS_SQLITE)
    def test_get_cycles_exists(self):
        """
        GIVEN a bom with cyclicity
        WHEN get_cycles is run on the bom
        THEN result length matches the number of cycles
             AND the path matches the expected cycle
        """

        common.generateComponent(baugruppe=self.test_item_c.teilenummer,
                                 teilenummer=self.test_item_a.teilenummer)

        result = get_cycles(self.test_root)
        self.assertEqual(len(result), 1)

        expected = "teilenummer={nr_a}, t_index=, baugruppe={nr_c}, b_index=, path=,{nr_a}@,{nr_b}@,{nr_c}@,{nr_a}@," \
                   .format(nr_root=self.test_root.teilenummer,
                           nr_a=self.test_item_a.teilenummer,
                           nr_b=self.test_item_b.teilenummer,
                           nr_c=self.test_item_c.teilenummer)
        self.assertEqual(expected, str(result[0]))
