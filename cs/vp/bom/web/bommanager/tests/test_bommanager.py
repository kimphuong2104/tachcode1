# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tests for bommanager.__init__
"""
import collections
import mock

import cs.vp.bom.tests as common

from cdb.testcase import PlatformTestCase
from cdb.testcase import rollback
from cdb.testcase import skip_dbms
from cdb import sqlapi
from cdb import ue

from cs.vp.bom import AssemblyComponent, BomType
from cs.vp.bom.web import bommanager


MockPartDialog = collections.namedtuple("MockPartDialog", ["teilenummer", "t_index"])
MockAssemblyComponentDialog = collections.namedtuple("MockAssemblyComponentDialog", ["cdb_object_id"])
MockContext = collections.namedtuple("MockContext", ["dialog"])


class TestObject(PlatformTestCase):
    def setUp(self):
        super(TestObject, self).setUp()
        BomType.GetBomTypeForCode(code="sBOM").is_enabled = 0
        bommanager.set_active_bom_type_setting('mBOM')

    def tearDown(self):
        super(TestObject, self).tearDown()
        BomType.GetBomTypeForCode(code="sBOM").is_enabled = 0
        bommanager.set_active_bom_type_setting('mBOM')

    def assertContainsComponents(self, container, components, msg=None):
        items = [(c.teilenummer, c.t_index) for c in container]
        for comp in components:
            self.assertIn((comp.teilenummer, comp.t_index), items, msg)

    def assertNotContainsComponents(self, container, components, msg=None):
        items = [(c.teilenummer, c.t_index) for c in container]
        for comp in components:
            self.assertNotIn((comp.teilenummer, comp.t_index), items, msg)

    @rollback
    def test_batch_copy_operation(self):
        """
        GIVEN the children of an ebom WHEN copied to a mbom \
        THEN children should be added to mbom AND also stay in ebom
        """
        new_dest = common.generateMBomComponent(baugruppe="9504560", teilenummer="9502666")
        src_positions = AssemblyComponent.KeywordQuery(baugruppe="9502662", b_index="")
        assert len(src_positions) > 0, "Faulty testdata! Assumption not met for test."

        ctx = MockContext(MockPartDialog(teilenummer=new_dest.teilenummer,
                                         t_index=new_dest.t_index))
        bommanager.bommanager_batch_copy(src_positions, ctx)

        src_positions_after = AssemblyComponent.KeywordQuery(baugruppe="9502662", b_index="")
        self.assertContainsComponents(src_positions_after, src_positions,
            "Item should stay in its original assembly")
        dest_children_after = AssemblyComponent.KeywordQuery(baugruppe=new_dest.teilenummer,
                                                             b_index=new_dest.t_index)
        self.assertContainsComponents(dest_children_after, src_positions,
            "Item should be in the target assembly after copy")

    @rollback
    def test_automatically_select_the_mbom(self):
        "If an ebom has only one mbom, the bommanager should automatically select the mbom"
        ebom = common.generateItem()
        mbom = ebom.generate_mbom()
        ctx = mock.MagicMock()

        bommanager._open_bommanager_now(ebom, ctx)
        expected_url = "/bommanager/{lbom_oid}?rbom={rbom_oid}".format(
            lbom_oid=ebom.cdb_object_id,
            rbom_oid=mbom.cdb_object_id
        )
        ctx.url.assert_called_with(expected_url)

    def _make_sync_test_data(self):
        ebom_assembly = common.generateItem()
        ebom_component = common.generateAssemblyComponent(ebom_assembly)
        mbom = ebom_assembly.generate_mbom()
        mbom_component = common.generateAssemblyComponent(mbom)
        mbom_component.Item.type_object_id = BomType.GetBomTypeForCode('mBOM').cdb_object_id

        mbom.Reload()

        self.assertTrue(mbom_component.Item.IsDerived())
        self.assertEqual(len(mbom.Components), 1)

        ctx = MockContext(dialog=MockAssemblyComponentDialog(cdb_object_id=mbom_component.cdb_object_id))

        return ebom_component, mbom_component, ctx

    @rollback
    def test_sync_mapping_copies_tag(self):
        "sync mapping copies the mapping tag from the lbom to the rbom"
        ebom_component, mbom_component, ctx = self._make_sync_test_data()
        mbom_component.mbom_mapping_tag = ""

        bommanager.bommanager_synch_mapping(ebom_component, ctx)

        self.assertEqual(mbom_component.mbom_mapping_tag, ebom_component.mbom_mapping_tag)

    @rollback
    def test_sync_mapping_creates_both_tags_if_needed(self):
        "If the lbom position does not have a mapping tag, it is created during sync"
        ebom_component, mbom_component, ctx = self._make_sync_test_data()
        ebom_component.mbom_mapping_tag = ""
        mbom_component.mbom_mapping_tag = ""

        bommanager.bommanager_synch_mapping(ebom_component, ctx)

        self.assertNotIn(ebom_component.mbom_mapping_tag, [None, ""])
        self.assertEqual(mbom_component.mbom_mapping_tag, ebom_component.mbom_mapping_tag)

    @rollback
    def test_mapping_fails_if_the_bom_position_has_not_the_active_bom_type(self):
        "Sync fails if the bom position has a different type as the one the user has set"
        ebom_component, _, ctx = self._make_sync_test_data()

        BomType.GetBomTypeForCode(code="sBOM").is_enabled = 1
        bommanager.set_active_bom_type_setting('sBOM')

        with self.assertRaises(ue.Exception):
            bommanager.bommanager_synch_mapping(ebom_component, ctx)

    @rollback
    def test_active_bom_type_setting(self):
        from cdb import util
        # no valid json
        util.PersonalSettings().setValue(bommanager.BOM_TYPE_SETTING_1, bommanager.BOM_TYPE_SETTING_2, '')
        self.assertEqual("mBOM", bommanager.get_active_bom_type_setting()["code"])
        # no code
        util.PersonalSettings().setValue(bommanager.BOM_TYPE_SETTING_1, bommanager.BOM_TYPE_SETTING_2, '{}')
        self.assertEqual("mBOM", bommanager.get_active_bom_type_setting()["code"])
        # not existing bom type
        util.PersonalSettings().setValue(bommanager.BOM_TYPE_SETTING_1, bommanager.BOM_TYPE_SETTING_2, '{"code": "illegalBOMType"}')
        self.assertEqual("mBOM", bommanager.get_active_bom_type_setting()["code"])
        # inactive bom type
        util.PersonalSettings().setValue(bommanager.BOM_TYPE_SETTING_1, bommanager.BOM_TYPE_SETTING_2, '{"code": "sBOM"}')
        self.assertEqual("mBOM", bommanager.get_active_bom_type_setting()["code"])
        # active bom type
        BomType.GetBomTypeForCode(code="sBOM").is_enabled = 1
        util.PersonalSettings().setValue(bommanager.BOM_TYPE_SETTING_1, bommanager.BOM_TYPE_SETTING_2, '{"code": "sBOM"}')
        active_bom_type = bommanager.get_active_bom_type_setting()["code"]
        self.assertEqual("sBOM", active_bom_type)
