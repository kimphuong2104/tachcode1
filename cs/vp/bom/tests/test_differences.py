# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tests for computing the
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import cdbwrapc
from cdb import testcase, util

from cs.vp.bom import differences
from cs.vp.bom.tests import generateItem, generateComponent

# Exported objects
__all__ = []


class TestMultiplePaths(testcase.RollbackTestCase):
    def setUp(self):
        super(TestMultiplePaths, self).setUp()

        self.ebom = generateItem()
        self.subassembly = generateItem()
        self.part = generateItem()

        self.comp = generateComponent(
            baugruppe=self.ebom.teilenummer,
            b_index=self.ebom.t_index,
            teilenummer=self.subassembly.teilenummer,
            t_index=self.subassembly.t_index,
            menge=1,
            position=12
        )

        generateComponent(
            baugruppe=self.ebom.teilenummer,
            b_index=self.ebom.t_index,
            teilenummer=self.subassembly.teilenummer,
            t_index=self.subassembly.t_index,
            menge=1,
            position=24
        )

        self.subcomp = generateComponent(
            baugruppe=self.subassembly.teilenummer,
            b_index=self.subassembly.t_index,
            teilenummer=self.part.teilenummer,
            t_index=self.part.t_index,
            menge=1,
            position=12
        )

        self.mbom = self.ebom.generate_mbom(question_copy_stl_relship_1st_level=1)
        self.mbom_comp = generateComponent(
            baugruppe=self.mbom.teilenummer,
            b_index=self.mbom.t_index,
            teilenummer=self.subassembly.teilenummer,
            t_index=self.subassembly.t_index,
            menge=1,
            position=42
        )

    def assertCompEquals(self, lhs, rhs):
        cdef = cdbwrapc.CDBClassDef("bom_item")
        for key in cdef.getKeyNames():
            if (key not in lhs) != (key not in rhs):  # xor
                self.fail("Mismatching types\n\t%s\n\t%s" % (lhs, rhs))
            elif key in lhs and lhs[key] != rhs[key]:
                self.fail("Found difference\n\t%s\n\t%s" % (lhs, rhs))

    def assertPathEquals(self, lhs, rhs):
        if len(lhs) != len(rhs):
            self.fail("Mismatching path lengths, %s != %s" % (len(lhs), len(rhs)))

        for lcomp, rcomp in zip(lhs, rhs):
            self.assertCompEquals(lcomp, rcomp)


class TestHintImpl(testcase.PlatformTestCase):
    def setUp(self):
        super(TestHintImpl, self).setUp()

        self.hint_impl = differences.HintImpl()

    def test_format_float_whole_number(self):
        "format_float correctly formats whole numbers"
        self.assertEqual(self.hint_impl.format_float(1.0), "1")

    def test_format_float_floating_number(self):
        "format_float correctly formats floating point numbers"
        self.assertEqual(self.hint_impl.format_float(0.1 + 0.2), "0.3")
        self.assertEqual(self.hint_impl.format_float(3.1415), "3.1415")

    def test_when_missing_quantities_then_no_hint(self):
        mock_diffs = [
            {
                'teilenummer': '001',
                't_index': 'a',
                'lbom_quantity': 1,
                'rbom_quantity': 0
            },
            {
                'teilenummer': '002',
                't_index': 'a'
            },
            {
                'teilenummer': '003',
                't_index': 'a',
                'lbom_quantity': 0,
                'rbom_quantity': 1
            }
        ]
        diffs_with_hints = self.hint_impl.calculate(mock_diffs, None, None)
        self.assertEqual(3, len(diffs_with_hints))
        self.assertTrue('hint' in diffs_with_hints[0])
        self.assertFalse('hint' in diffs_with_hints[1])
        self.assertIsNotNone('hint' in diffs_with_hints[2])

    def test_when_index_differs_then_extend_hint(self):
        mock_diffs = [
            {
                'teilenummer': '001',
                't_index': 'a',
                'lbom_quantity': 1,
                'rbom_quantity': 0
            },
            {
                'teilenummer': '001',
                't_index': 'b',
                'lbom_quantity': 0,
                'rbom_quantity': 1
            }
        ]
        diffs_with_hints = self.hint_impl.calculate(mock_diffs, None, None)

        expected_hint = util.get_label('cdbvp_elink_diffutil_index_exchange')
        self.assertEqual(f'+1, {expected_hint}', diffs_with_hints[0]['hint'])
        self.assertEqual(f'-1, {expected_hint}', diffs_with_hints[1]['hint'])
