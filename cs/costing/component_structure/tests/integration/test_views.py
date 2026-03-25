#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
import unittest
from cdb import testcase
from cdb.objects import ByID

from cs.costing.component_structure import views
from cs.costing.component_structure.tests.integration.test_util \
    import generate_structure

# Structure
# Part 1 - Comp2Comp_1
# L Step 1-1 - Comp2Comp_1_1
#   L Part 1-1-1 - Comp2Comp_1_1_1
#     L Part 1-1-1-1 - Comp2Comp_1_1_1_1
#       L Part 1-1-1-1-1 - Comp2Comp_1_1_1_1_1
# L Step 1-2 - Comp2Comp_1_2
#   L Part 1-1-1 (c) - Comp2Comp_1_1_1_c
#     L Part 1-1-1-1 (c) - Comp2Comp_1_1_1_1_c
#       L Part 1-1-1-1-1 (c) - Comp2Comp_1_1_1_1_1


class CostTreeView(testcase.RollbackTestCase):
    maxDiff = None

    def _rest_id(self, obj):
        return "/api/v1/collection/cdbpco_comp2component/{}".format(
            obj.cdb_object_id)

    def _structure(self):
        result = []

        def add_obj(obj, level=0):
            result.append(
                "{0}{1} {2.name} {2.sort_order}".format(
                    "  " * level, level, obj))
            for child in obj.AllChildren:
                add_obj(child, level +1)

        for comp in self.calc.TopComponents:
            add_obj(comp)

        return result

    def _create_testdata(self):
        self.testdata = generate_structure()
        self.calc = ByID(self.testdata[0])
        self.cc_1_1 = self.testdata[2]
        self.cc_1_1_1 = self.testdata[3]
        self.cc_1_2 = self.testdata[6]

        self.assertEqual(self._structure(), [
            '0 1 None',
            '  1 1-1 None',
            '    2 1-1-1 None',
            '      3 1-1-1-1 None',
            '        4 1-1-1-1-1 None',
            '  1 1-2 None',
            '    2 1-1-1 None',
            '      3 1-1-1-1 None',
            '        4 1-1-1-1-1 None',
        ])

    def test_persist_drop(self):
        "D&D move (children): Step 1-2 underneath Step 1-1"
        self._create_testdata()

        parent = self._rest_id(self.cc_1_1)
        target = self._rest_id(self.cc_1_2)
        children = [self._rest_id(self.cc_1_1_1), target]

        self.assertIsNone(
            views.CostTreeView.persist_drop(
                target, parent, children, None, True)
        )

        self.assertEqual(self._structure(), [
            '0 1 None',
            '  1 1-1 None',
            '    2 1-1-1 None',
            '      3 1-1-1-1 None',
            '        4 1-1-1-1-1 None',
            '    2 1-2 None',
            '      3 1-1-1 None',
            '        4 1-1-1-1 None',
            '          5 1-1-1-1-1 None',
        ])


if __name__ == "__main__":
    unittest.main()
