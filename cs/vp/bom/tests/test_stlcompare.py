# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module test_stlcompare

This is the documentation for the test_stlcompare module.
"""

import cdbwrapc

from cdb import constants
from cdb import sqlapi
from cdb import testcase
from cdb.objects import operations
from cdb.platform import mom
from cdb.validationkit.op import make_argument_list

from cs.vp.bom.tests import generateItem, generateComponent


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class TestSTLCompare(testcase.RollbackTestCase):
    def setUp(self):
        super(TestSTLCompare, self).setUp()

        rs = sqlapi.RecordSet2(columns=["max(session_id) as max_id"], table="cdb_partslist_comp")
        self.max_id = rs[0].max_id if rs[0].max_id is not None else -1

    def make_fixture_float_to_db(self):
        self.assembly1 = generateItem()
        self.part1 = generateItem()
        generateComponent(
            baugruppe=self.assembly1.teilenummer,
            b_index=self.assembly1.t_index,
            teilenummer=self.part1.teilenummer,
            t_index=self.part1.t_index,
            menge=1.1,
        )

        self.assembly2 = operations.operation(
            constants.kOperationCopy,
            self.assembly1,
            teilenummer="#"
        )

        self.assembly2.Components[0].menge = 1.2

    def test_insert_float_to_db(self):
        "The cdbstlcompare module will insert float differences to the database in decimal notation"

        self.make_fixture_float_to_db()

        # multiselect operations currently do not work with cdb.objects.operations (E042390)
        # so we have to use the good old internal cdbwrapc API
        op = cdbwrapc.Operation(
            "cdb_parts_list_comparison",
            [self.assembly1.ToObjectHandle(), self.assembly2.ToObjectHandle()],
            mom.SimpleArgumentList()
        )
        op_args = make_argument_list(None, {})
        dlg_args = make_argument_list(None, {})
        op.runAsTest(op_args, dlg_args, True)

        rs = sqlapi.RecordSet2(
            table="cdb_partslist_cval",
            condition="session_id > %s" % self.max_id
        )
        assert len(rs) == 1, "Found %s differences, expected %s" % (len(rs), 1)

        diff = rs[0]
        assert diff.wert1 == "1.1", "wert1 is not in decimal notation, got %s" % diff.wert1
        assert diff.wert2 == "1.2", "wert2 is not in decimal notation, got %s" % diff.wert2

    def make_fixture_orphan_assembly_component(self):
        self.assembly1 = generateItem()
        self.part1 = generateItem()
        generateComponent(
            baugruppe=self.assembly1.teilenummer,
            b_index=self.assembly1.t_index,
            teilenummer=self.part1.teilenummer,
            t_index=self.part1.t_index,
            menge=1.1,
        )

        self.part2 = generateItem()
        # orphan assembly component
        from cs.vp.bom import AssemblyComponent
        AssemblyComponent.Create(
            baugruppe="",
            b_index="",
            teilenummer=self.part2.teilenummer,
            t_index=self.part2.t_index,
            menge=1,
            position=10,
            variante="",
            auswahlmenge=0,
            is_imprecise=0
        )

    def test_orphan_assembly_component(self):
        "The cdbstlcompare module will not loop on orphan assembly components (regression test for E053026)"
        self.make_fixture_orphan_assembly_component()

        # multiselect operations currently do not work with cdb.objects.operations (E042390)
        # so we have to use the good old internal cdbwrapc API
        op = cdbwrapc.Operation(
            "cdb_parts_list_comparison",
            [self.assembly1.ToObjectHandle(), self.part2.ToObjectHandle()],
            mom.SimpleArgumentList()
        )
        op_args = make_argument_list(None, {})
        dlg_args = make_argument_list(None, {})
        op.runAsTest(op_args, dlg_args, True)

        rs = sqlapi.RecordSet2(
            table="cdb_partslist_comp",
            condition="session_id > %s" % self.max_id
        )
        assert len(rs) == 2, "Found %s differences, expected %s" % (len(rs), 2)
