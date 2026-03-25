# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tests for the tools document_cycle_finder
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from cdb import sqlapi
from cdb.testcase import RollbackTestCase, skip_dbms
import cs.vp.bom.tests as common

from cs.vp.bom.tools.document_cycle_finder import get_cycles


class TestCycleFinder(RollbackTestCase):
    def setUp(self):
        super(TestCycleFinder, self).setUp()
        self.test_root = common.generateDocument()
        self.test_document_a = common.generateDocument()
        self.test_document_b = common.generateDocument()
        self.test_document_c = common.generateDocument()
        self.test_document_d = common.generateDocument()

        # Build a document structure
        common.generateDocumentStructure(self.test_root, self.test_document_a)
        common.generateDocumentStructure(self.test_document_a, self.test_document_b)
        common.generateDocumentStructure(self.test_document_b, self.test_document_c)
        common.generateDocumentStructure(self.test_root, self.test_document_d)

    @skip_dbms(sqlapi.DBMS_SQLITE)
    def test_get_document_cycles_none_there(self):
        """
        GIVEN a bom without cyclicity
        WHEN get_cycles is run on the bom
        THEN result length is 0
        """
        result = get_cycles(self.test_root)
        self.assertEqual(0, len(result))

    @skip_dbms(sqlapi.DBMS_SQLITE)
    def test_get_document_cycles_exists(self):
        common.generateDocumentStructure(self.test_document_c, self.test_document_a)

        result = get_cycles(self.test_root)
        self.assertEqual(1, len(result))

        expected = "z_nummer2={nr_a}, z_index2=, z_nummer={nr_c}, z_index=, path=,{nr_a}@,{nr_b}@,{nr_c}@,{nr_a}@," \
            .format(nr_root=self.test_root.z_nummer,
                    nr_a=self.test_document_a.z_nummer,
                    nr_b=self.test_document_b.z_nummer,
                    nr_c=self.test_document_c.z_nummer)
        self.assertEqual(expected, str(result[0]))
