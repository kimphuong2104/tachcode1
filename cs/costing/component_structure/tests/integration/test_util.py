#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest
from collections import defaultdict
from cdb import testcase, sqlapi
from cs.platform.web.root.main import _get_dummy_request

from cs.pcs.projects.web.rest_app.project_structure.models import StructureModel

from cs.costing.tests.common import generate_calculation
from cs.costing.tests.common import generate_comp2component
from cs.costing.tests.common import generate_step_component
from cs.costing.tests.common import generate_part_component


def generate_structure():

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


    calculation = generate_calculation("TEST_CALCULATION", status=0)
    calc_oid = calculation.cdb_object_id

    part_1 = generate_part_component(calc_oid, "1", cloned=0)
    step_1_1 = generate_step_component(calc_oid, "1-1", part_1.cdb_object_id, cloned=0)
    # 1-1-1 from under 1-1 was cloned under 1-2 therefore the component entries
    # of 1-1-1, 1-1-1-1 and 1-1-1-1-1 are marked as cloned ....
    part_1_1_1 = generate_part_component(calc_oid, "1-1-1", step_1_1.cdb_object_id, cloned=1)
    part_1_1_1_1 = generate_part_component(calc_oid, "1-1-1-1", part_1_1_1.cdb_object_id, cloned=1)
    part_1_1_1_1_1 = generate_part_component(calc_oid, "1-1-1-1-1", part_1_1_1_1.cdb_object_id, cloned=1)
    step_1_2 = generate_step_component(calc_oid, "1-2", part_1.cdb_object_id, cloned=0)

    cc_1 = generate_comp2component(calc_oid, part_1.cdb_object_id, '', 0, quantity=1)
    cc_1_1 = generate_comp2component(calc_oid, step_1_1.cdb_object_id, part_1.cdb_object_id, 0, quantity=1)
    cc_1_1_1 =generate_comp2component(calc_oid, part_1_1_1.cdb_object_id, step_1_1.cdb_object_id, 0, quantity=1)
    cc_1_1_1_1 =generate_comp2component(calc_oid, part_1_1_1_1.cdb_object_id, part_1_1_1.cdb_object_id, 0, quantity=1)
    cc_1_1_1_1_1 =generate_comp2component(calc_oid, part_1_1_1_1_1.cdb_object_id, part_1_1_1_1.cdb_object_id, 0, quantity=1)
    # ... and cc_1_1_1_c is marked as cloned
    #     and nodes 1-1-1-1 and 1-1-1-1-1 from 1-1 and 1-2 share the same comp2component entries
    cc_1_2 = generate_comp2component(calc_oid, step_1_2.cdb_object_id, part_1.cdb_object_id, 0, quantity=1)
    cc_1_1_1_c =generate_comp2component(calc_oid, part_1_1_1.cdb_object_id, step_1_2.cdb_object_id, 1, quantity=1)

    return calc_oid, cc_1, cc_1_1, cc_1_1_1, cc_1_1_1_1, cc_1_1_1_1_1, cc_1_2, cc_1_1_1_c


class ResolveRecordsTestCase(testcase.RollbackTestCase):
    def test_resolve(self):
        '''Test general resolving of a simple structure'''

        self.maxDiff = None

        calc_oid, cc_1, cc_1_1, cc_1_1_1, cc_1_1_1_1, cc_1_1_1_1_1, cc_1_2, cc_1_1_1_c = generate_structure()

        view = "costing_structure"
        request = _get_dummy_request(path="")
        structuremodel = StructureModel(request, view, calc_oid)
        response = structuremodel.resolve(request)
        response_nodes = response["nodes"]
        response_objects = response["objects"]

        # construct ids for accessing the response entries
        cc_1__1 = str(cc_1.cdb_object_id) + '--1'
        cc_1_1__1 = str(cc_1_1.cdb_object_id) + '--1'
        cc_1_2__1 = str(cc_1_2.cdb_object_id) + '--1'
        cc_1_1_1__1 = str(cc_1_1_1.cdb_object_id) + '--1'
        cc_1_1_1_1__1 = str(cc_1_1_1_1.cdb_object_id) + '--1'
        cc_1_1_1_1_1__1 = str(cc_1_1_1_1_1.cdb_object_id) + '--1'
        cc_1_1_1_c__1 = str(cc_1_1_1_c.cdb_object_id) + '--1'
        cc_1_1_1_1__2 = str(cc_1_1_1_1.cdb_object_id) + '--2'
        cc_1_1_1_1_1__2 = str(cc_1_1_1_1_1.cdb_object_id) + '--2'

        # NOTE: The db records order and thus the occurence ids may vary
        #       depending on the dbms.
        #       Therefore we just check the general structure of the adjacency
        #       list; without caring much about if the occurence id is correct
        #       as long as the oid is
        self.assertEqual(
            response_nodes[str(calc_oid)][0].split('--')[0],
            str(cc_1.cdb_object_id)
        )
        self.assertListEqual(
            [e.split('--')[0] for e in response_nodes[cc_1__1]],
            [str(cc_1_1.cdb_object_id), str(cc_1_2.cdb_object_id)]
        )
        self.assertEqual(
            response_nodes[cc_1_1__1][0].split('--')[0],
            str(cc_1_1_1.cdb_object_id)
        )
        self.assertEqual(
            response_nodes[cc_1_2__1][0].split('--')[0],
            str(cc_1_1_1_c.cdb_object_id)
        )
        self.assertEqual(
            response_nodes[cc_1_1_1__1][0].split('--')[0],
            str(cc_1_1_1_1.cdb_object_id)
        )
        self.assertEqual(
            response_nodes[cc_1_1_1_c__1][0].split('--')[0],
            str(cc_1_1_1_1.cdb_object_id)
        )
        self.assertEqual(
            response_nodes[cc_1_1_1_1__1][0].split('--')[0],
            str(cc_1_1_1_1_1.cdb_object_id)
        )
        self.assertEqual(
            response_nodes[cc_1_1_1_1__2][0].split('--')[0],
            str(cc_1_1_1_1_1.cdb_object_id)
        )

        # check attributes of resolved objects
        # NOTE: Depending on dbms quantity part of label is either Long or Float
        dbtype = sqlapi.SQLdbms()
        self.assertListEqual(
            [
                response_objects[calc_oid]["label"],
                bool(response_objects[calc_oid]["cloned"])
            ],
            [
                'TEST_CALCULATION',
                False
            ]
        )
        self.assertListEqual(
            [
                response_objects[cc_1__1]["label"],
                bool(response_objects[cc_1__1]["cloned"])
            ],
            [
                '1 (x1)' if (dbtype == sqlapi.DBMS_SQLITE) else '1 (x1.0)',
                False
            ]
        )
        self.assertListEqual(
            [
                response_objects[cc_1_1__1]["label"],
                bool(response_objects[cc_1_1__1]["cloned"])
            ],
            [
                '1-1 (x1)' if (dbtype == sqlapi.DBMS_SQLITE) else '1-1 (x1.0)',
                False
            ]
        )
        self.assertListEqual(
            [
                response_objects[cc_1_2__1]["label"],
                bool(response_objects[cc_1_2__1]["cloned"])
            ],
            [
                '1-2 (x1)' if (dbtype == sqlapi.DBMS_SQLITE) else '1-2 (x1.0)',
                False
            ]
        )
        self.assertListEqual(
            [
                response_objects[cc_1_1_1__1]["label"],
                bool(response_objects[cc_1_1_1__1]["cloned"])
            ],
            [
                '1-1-1 (x1)' if (dbtype == sqlapi.DBMS_SQLITE) else '1-1-1 (x1.0)',
                True
            ]
        )
        self.assertListEqual(
            [
                response_objects[cc_1_1_1_c__1]["label"],
                bool(response_objects[cc_1_1_1_c__1]["cloned"])
            ],
            [
                '1-1-1 (x1)' if (dbtype == sqlapi.DBMS_SQLITE) else '1-1-1 (x1.0)',
                True
            ]
        )
        self.assertListEqual(
            [
                response_objects[cc_1_1_1_1__1]["label"],
                bool(response_objects[cc_1_1_1_1__1]["cloned"])
            ],
            [
                '1-1-1-1 (x1)' if (dbtype == sqlapi.DBMS_SQLITE) else '1-1-1-1 (x1.0)',
                True
            ]
        )
        self.assertListEqual(
            [
                response_objects[cc_1_1_1_1__2]["label"],
                bool(response_objects[cc_1_1_1_1__2]["cloned"])
            ],
            [
                '1-1-1-1 (x1)' if (dbtype == sqlapi.DBMS_SQLITE) else '1-1-1-1 (x1.0)',
                True
            ]
        )
        self.assertListEqual(
            [
                response_objects[cc_1_1_1_1_1__1]["label"],
                bool(response_objects[cc_1_1_1_1_1__1]["cloned"])
            ],
            [
                '1-1-1-1-1 (x1)' if (dbtype == sqlapi.DBMS_SQLITE) else '1-1-1-1-1 (x1.0)',
                True
            ]
        )
        self.assertListEqual(
            [
                response_objects[cc_1_1_1_1_1__2]["label"],
                bool(response_objects[cc_1_1_1_1_1__2]["cloned"])
            ],
            [
                '1-1-1-1-1 (x1)' if (dbtype == sqlapi.DBMS_SQLITE) else '1-1-1-1-1 (x1.0)',
                True
            ]
        )

# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
