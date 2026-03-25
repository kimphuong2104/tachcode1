# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tests for the mapping of ebom bom-positions to mbom bom-positions
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import cdbwrapc
import unittest

from cdb import constants
from cdb import sqlapi
from cdb import testcase
from cdb._ctx import message_box
from cdb.objects import operations
from cdb.testcase import RollbackTestCase

from cs.vp import bom
from cs.vp import items
from cs.vp.bom.tests import generateItem, generateAssemblyComponent

# Exported objects
__all__ = []


# def setup():
#     from cdb import testcase
#     testcase.run_level_setup()

class TestMapping(RollbackTestCase):
    def setUp(self):
        def fixture_installed():
            try:
                import cs.vptests
                return True
            except ImportError:
                return False

        if not fixture_installed():
            raise unittest.SkipTest("Fixture package cs.vptests not installed")

        super(TestMapping, self).setUp()

        self.ebom = items.Item.ByKeys(teilenummer="9502657", t_index="")
        self.mbom = items.Item.ByKeys(teilenummer="9504560", t_index="")

        self.ebom_position = bom.AssemblyComponent.ByKeys(
            baugruppe=self.ebom.teilenummer,
            b_index=self.ebom.t_index,
            teilenummer="9502659",
            position=2
        )
        self.mbom_position = bom.AssemblyComponent.ByKeys(
            baugruppe=self.ebom.teilenummer,
            b_index=self.ebom.t_index,
            teilenummer="9502659",
            position=2
        )

    def test_sql_statements_for_mbom_mapping_tag(self):
        with testcase.max_sql(20):
            new_position = operations.operation(
                constants.kOperationNew,
                bom.AssemblyComponent,
                baugruppe=self.ebom_position.baugruppe,
                b_index=self.ebom_position.b_index,
                teilenummer=self.ebom_position.teilenummer,
                t_index=self.ebom_position.t_index,
                menge=self.ebom_position.menge,
                variante=self.ebom_position.variante,
                auswahlmenge=self.ebom_position.auswahlmenge,
                position=112
            )

    def test_create_new_ebom_position(self):
        """when a new ebom-position is created, a new not already existent mapping tag is created"""
        new_position = operations.operation(
            constants.kOperationNew,
            bom.AssemblyComponent,
            baugruppe=self.ebom_position.baugruppe,
            b_index=self.ebom_position.b_index,
            teilenummer=self.ebom_position.teilenummer,
            t_index=self.ebom_position.t_index,
            menge=self.ebom_position.menge,
            variante=self.ebom_position.variante,
            auswahlmenge=self.ebom_position.auswahlmenge,
            position=111
        )

        self._check_unique(new_position)

    def test_copy_an_ebom_position(self):
        """when an ebom-position is copied, a new not already existent mapping tag is created"""
        new_position = operations.operation(
            constants.kOperationCopy,
            self.ebom_position,
            position=100
        )

        self._check_unique(new_position)

    def test_create_ebom(self):
        """when an mbom is created, its position have the correct mapping tag"""
        mbom = operations.operation(
            constants.kOperationNew,
            items.Item,
            operations.system_args(
                cdb_create_mbom="1",
                question_copy_stl_relship_1st_level=message_box.MessageBoxMixin.MessageBox.kMsgBoxResultYes,
                item_object_id=self.ebom.cdb_object_id
            ),
            **self._make_mbom_args(self.ebom)
        )

        self.assertEqual(
            len(mbom.Components), len(self.ebom.Components),
            "The BOM has not been copied"
        )

        for mpos, epos in zip(
            sorted(mbom.Components, key=lambda c: c.position),
            sorted(self.ebom.Components, key=lambda c: c.position)
        ):
            self.assertEqual(
                mpos.mbom_mapping_tag, epos.mbom_mapping_tag,
                "The mapping tag does not coincide with that of the ebom"
            )

    def test_replace_mbom_position_create(self):
        """
        Test that the mapping tag is copied over when copy-and-creating an rBOM position from an lBOM
        position.
        """

        # Prepare lBOM and rBOM root.
        lbom = generateItem()
        lbom_component = generateAssemblyComponent(lbom)
        rbom = lbom.generate_mbom()

        # Run copy-and-create on the lBOM's component onto the rBOM.
        operations.operation(
            "bommanager_copy_and_create_xbom",
            # We pass a list because of multi object operation.
            [lbom_component],
            # Tell operation onto what assembly we want to copy the BOM position.
            teilenummer=rbom.teilenummer,
            t_index=rbom.t_index
        )

        # Check that mapping tag was correctly copied over from lBOM component to rBOM component.
        rbom_components = bom.AssemblyComponent.KeywordQuery(baugruppe=rbom.teilenummer)
        self.assertEqual(len(rbom_components), 1)
        self.assertEqual(
            rbom_components[0].mbom_mapping_tag,
            lbom_component.mbom_mapping_tag,
            "The mapping tag does not coincide"
        )

    def test_create_mbom_position(self):
        """when an mbom-position without an ebom-reference is created, the mapping tag is empty"""
        mpos = operations.operation(
            constants.kOperationNew,
            bom.AssemblyComponent,
            baugruppe=self.mbom.teilenummer,
            b_index=self.mbom.t_index,
            teilenummer="9504561",
            t_index="",
            variante="",
            auswahlmenge=0.0,
            position=1111
        )

        self.assertTrue(
            mpos.mbom_mapping_tag is None or mpos.mbom_mapping_tag == "",
            "mapping field is not empty %s" % mpos.mbom_mapping_tag
        )

    def test_change_mapping_tag(self):
        """when the mapping tag of an ebom-position is changed, the mapping tag of its mboms is also updated"""
        operations.operation(
            constants.kOperationModify,
            self.ebom_position,
            mbom_mapping_tag="NEWVALUE"
        )
        self.ebom_position.Reload()
        self.mbom_position.Reload()
        self.assertEqual(
            self.ebom_position.mbom_mapping_tag, self.mbom_position.mbom_mapping_tag,
            "mapping tag has not been updated"
        )

    def _make_mbom_args(self, ebom):
        blacklist = [
            'cdb_object_id',
            'teilenummer',
            't_index',
            'status',
            'cdb_status_txt',
            't_ersatz_fuer',
            't_ersatz_durch',
            't_pruefer',
            't_pruef_datum'
        ]

        cldef = cdbwrapc.CDBClassDef('teile_stamm')
        args = {}
        for attr in cldef.getAttributeDefs():
            attr_name = attr.getName()
            if attr_name not in blacklist:
                args[attr_name] = getattr(ebom, attr_name)
        args.update(
            cdb_depends_on=ebom.cdb_object_id,
            cdb_copy_of_item_id=ebom.cdb_object_id,
            type_object_id=bom.get_mbom_bom_type().cdb_object_id,
            materialnr_erp=ebom.materialnr_erp
        )
        return args

    def _check_unique(self, new_position):
        self.assertIsNotNone(new_position.mbom_mapping_tag, "mbom_mapping_tag is None")
        self.assertNotEqual(new_position.mbom_mapping_tag, "", "mbom_mapping_tag is empty")

        rs = sqlapi.RecordSet2(
            table="einzelteile",
            condition="mbom_mapping_tag='%s'" % new_position.mbom_mapping_tag,
            columns=["count(*) as n"]
        )
        N = rs[0].n
        self.assertGreaterEqual(N, 1, "mbom_mapping_tag was not set")
        self.assertLessEqual(N, 1, "mbom_mapping_tag is not unique")
