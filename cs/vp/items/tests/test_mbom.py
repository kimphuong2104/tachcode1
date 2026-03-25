# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from cdb import testcase, ElementsError
from cdb.platform.gui import Message

from cs.vp.items.tests import generateItem
from cs.vp.bom import get_ebom_bom_type, get_mbom_bom_type, get_sbom_bom_type


class TestMbom(testcase.RollbackTestCase):

    def test_rbom_materialnr_from_master(self):
        # When creating an rbom from the master, it is expected that the newly derived rbom has the same
        # materialnr_erp as the master.
        ebom = generateItem()
        mbom = ebom.generate_mbom()
        self.assertEqual(mbom.materialnr_erp, ebom.materialnr_erp)

    def test_rbom_materialnr_from_mbom_same_master(self):
        # When creating an rbom from another mbom, it is expected that the newly derived rbom has the
        # materialnr_erp of the current master instead of the mbom's master.
        ebom = generateItem()
        mbom = ebom.generate_mbom()
        mbom2 = mbom.generate_mbom(depends_on=ebom.cdb_object_id)

        self.assertEqual(mbom2.materialnr_erp, ebom.materialnr_erp)

    def test_rbom_materialnr_from_mbom_different_masters(self):
        # When creating an rbom from another mbom, it is expected that the newly derived rbom has the
        # materialnr_erp of the current master instead of the mbom's master.
        ebom = generateItem()
        mbom = ebom.generate_mbom()

        ebom2 = generateItem()
        mbom2 = mbom.generate_mbom(depends_on=ebom2.cdb_object_id)
        self.assertEqual(mbom2.materialnr_erp, ebom2.materialnr_erp)

    def test_succeed_derive_mbom_index_from_same_ebom(self):
        # Prepare eBOM.
        ebom = generateItem()

        # Prepare mBOM.
        mbom = ebom.generate_mbom()

        # Indexing an mBOM derived from the same eBOM should work.
        mbom_index = mbom.generate_mbom(depends_on=ebom.cdb_object_id, create_index=True)

        self.assertEqual(mbom_index.cdb_depends_on, ebom.cdb_object_id)
        self.assertEqual(mbom_index.materialnr_erp, ebom.materialnr_erp)

    def test_fail_mbom_index_from_different_ebom(self):
        # Prepare eBOMs with different teilenummern.
        ebom_1 = generateItem(type_object_id=get_ebom_bom_type().cdb_object_id)
        ebom_2 = generateItem(type_object_id=get_ebom_bom_type().cdb_object_id)

        # Prepare mBOM.
        mbom = ebom_1.generate_mbom()

        # Indexing an mBOM derived from another eBOM should fail validation.
        expected_msg = Message.GetMessage(
            "cdb_deriving_index_from_invalid_master",
            ebom_2.teilenummer,
            mbom.teilenummer,
            ebom_1.teilenummer
        )
        with self.assertRaisesRegex(ElementsError, str(expected_msg)):
            mbom.generate_mbom(depends_on=ebom_2.cdb_object_id, create_index=True)

    def test_fail_mbom_index_from_underived_ebom(self):
        # Prepare eBOM.
        ebom = generateItem(type_object_id=get_ebom_bom_type().cdb_object_id)

        # Prepare mBOM to derive from, but without own master.
        mbom = generateItem(type_object_id=get_mbom_bom_type().cdb_object_id)

        # Indexing an mBOM derived from another eBOM should fail validation.
        expected_msg = Message.GetMessage(
            "cdb_deriving_index_from_underived_master",
            ebom.teilenummer,
            mbom.teilenummer
        )
        with self.assertRaisesRegex(ElementsError, str(expected_msg)):
            mbom.generate_mbom(depends_on=ebom.cdb_object_id, create_index=True)

    def test_fail_deriving_index_with_changed_bomtype(self):
        ebom = generateItem(type_object_id=get_ebom_bom_type().cdb_object_id)

        mbom = ebom.generate_mbom()
        # Indexing e.g. an mBOM derived from an sBOM should fail validation.
        expected_msg = Message.GetMessage(
            "cdb_deriving_index_with_changed_bom_type",
            get_sbom_bom_type().name,
            get_mbom_bom_type().name
        )
        with self.assertRaisesRegex(ElementsError, str(expected_msg)):
            mbom.generate_sbom(depends_on=ebom.cdb_object_id, create_index=True)
