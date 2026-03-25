# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import unittest

from cdb import constants
from cdb.objects import operations
from cdb.testcase import RollbackTestCase

from cs.vp import items
from cs.vp.bom.productstructure import ProductStructure, xBOMQuantityDiff
from cs.vp.bom.tests import generateAssemblyComponent, generateItem


class TestProductStructure(RollbackTestCase):

    def setUp(self):
        def fixture_installed():
            try:
                import cs.vptests
                return True
            except ImportError:
                return False

        if not fixture_installed():
            raise unittest.SkipTest("Fixture package cs.vptests not installed")

        super(TestProductStructure, self).setUp()
        self.rootLeft = items.Item.ByKeys(teilenummer="293000")
        self.rootRight = items.Item.ByKeys(teilenummer="293025")
        self.scenario1Left = items.Item.ByKeys(teilenummer="293001")
        self.scenario2Left = items.Item.ByKeys(teilenummer="293004")
        self.scenario3Left = items.Item.ByKeys(teilenummer="293007")
        self.scenario4Left = items.Item.ByKeys(teilenummer="293010")
        self.scenario5Left = items.Item.ByKeys(teilenummer="293013")
        self.scenario6Left = items.Item.ByKeys(teilenummer="293021")
        self.scenario7Left = items.Item.ByKeys(teilenummer="293026")
        self.scenario8Left = items.Item.ByKeys(teilenummer="293031")
        self.scenario1Right = items.Item.ByKeys(teilenummer="293016")
        self.scenario2Right = items.Item.ByKeys(teilenummer="293017")
        self.scenario3Right = items.Item.ByKeys(teilenummer="293018")
        self.scenario4Right = items.Item.ByKeys(teilenummer="293019")
        self.scenario5Right = items.Item.ByKeys(teilenummer="293020")
        self.scenario6Right = items.Item.ByKeys(teilenummer="293024")
        self.scenario7Right = items.Item.ByKeys(teilenummer="293030")
        self.scenario8Right = items.Item.ByKeys(teilenummer="293034")
        self.loopRootLeft = items.Item.ByKeys(teilenummer="293036")
        self.loopRootRight = items.Item.ByKeys(teilenummer="293039")
        self.quantitiesRootLeft = items.Item.ByKeys(teilenummer="293040")
        self.quantitiesRootRight = items.Item.ByKeys(teilenummer="293047")


    def test_tree_node(self):
        ps = ProductStructure(self.rootLeft)
        tree = ps.tree
        paths = []
        for child in tree.children:
            path_from_root = child.path_from_root()
            paths.append(path_from_root)
            for sub_child in child.children:
                path_from_root_sub = sub_child.path_from_root()
                paths.append(path_from_root_sub)
                if len(sub_child.children) > 0:
                    for sub_sub_child in sub_child.children:
                        path_from_root_sub_sub = sub_sub_child.path_from_root()
                        paths.append(path_from_root_sub_sub)

        assert len(paths) == 30
        assert paths[0] == ['7cb35924-ff82-11ed-a5c0-145afc3fd66e']
        assert paths[3] == ['81c72433-ff82-11ed-bdd3-145afc3fd66e']
        assert paths[7] == ['85cd1e9b-ff82-11ed-8778-145afc3fd66e', '52b9280d-ff7e-11ed-9ea3-145afc3fd66e']
        assert paths[10] == ['8a5e65b3-ff82-11ed-a2b5-145afc3fd66e']
        assert paths[15] == ['907489e5-ff82-11ed-bbc3-145afc3fd66e']
        assert paths[23] == ['517f947f-0048-11ee-ac11-145afc3fd66e']
        assert paths[29] == ['5a80e67e-0048-11ee-b320-145afc3fd66e', '1a78ffe0-0047-11ee-8703-145afc3fd66e',
                             '06ab6154-0047-11ee-88c8-145afc3fd66e']

    def test_get_paths(self):
        ps = ProductStructure(self.rootRight)

        path_with_index = ps.get_paths('293005', 'a')
        path_without_index = ps.get_paths('293005', '')

        assert len(path_with_index[0]) == 2
        assert path_with_index[0][0] == '2f1dbafb-ff91-11ed-a953-145afc3fd66e'
        assert path_with_index[0][1] == 'af052b1d-ff83-11ed-9196-145afc3fd66e'

        assert len(path_without_index[0]) == 2
        assert path_without_index[0][0] == '2f1dbafb-ff91-11ed-a953-145afc3fd66e'
        assert path_without_index[0][1] == '9809db4d-ff83-11ed-8b22-145afc3fd66e'

    def test_get_diff(self):
        lps = ProductStructure(self.quantitiesRootLeft)
        rps = ProductStructure(self.quantitiesRootRight)
        differ = xBOMQuantityDiff(lps, rps)
        diffs = differ.get_diffs()
        assert len(diffs) == 2
        # assert diffs['293041', ''] == -0.001
        # assert diffs['293041', 'a'] == 1

    def test_get_differences_data(self):
        lps = ProductStructure(self.rootLeft)
        rps = ProductStructure(self.rootRight)
        differ = xBOMQuantityDiff(lps, rps)
        diffs = differ.get_diffs()
        diffs2 = differ.get_differences_data()

        assert len(diffs) == len(diffs2)

        for dif1, dif2 in zip(diffs, diffs2):
            assert dif1 == dif2

    def test_get_differences_data_loop(self):
        lps = ProductStructure(self.loopRootLeft)
        rps = ProductStructure(self.loopRootRight)
        differ = xBOMQuantityDiff(lps, rps)
        diffs = differ.get_differences_data()
        assert len(diffs) == 0


    def test_get_quantities(self):
        ps = ProductStructure(self.quantitiesRootLeft)
        quantities = ps.get_quantities(False)
        assert len(quantities) == 2
        assert quantities['293041'][''] == 1.5
        assert quantities['293042'][''] == 1.123
        # assert quantities['293042']['a'] == 0.001

    def test_get_quantities_impreciese(self):
        ps = ProductStructure(self.scenario2Right)
        quantities = ps.get_quantities(True)
        assert len(quantities) == 2
        assert quantities['293005']['a'] == 1.0
        assert quantities['293005']['IMP'] == 1.0
        assert quantities['293006'][''] == 1

    """
    Scenarios
    - Beispiele Mengenkonsolidierung und Sichtenunabhängigkeit - (Szenario 1)
        test_example_quantity_consolidation_and_view_independence
    - Mixed precise und imprecise Vorkommen - (Szenario 2)
        test_mixed_precise_and_imprecise_occurrence
    - Mengenkonsolidierung mit mehreren Indexständen der Master BOM - (Szenario 3)
        test_quantity_consolidation_with_multiple_index_stands_of_the_master_BOM
    - Imprecise Mengenkonsolidierung mit Imprecise Mengenüberschuß - (Szenario 4)
        test_imprecise_quantity_consolidation_with_quantity_surplus
    - Mengenkonsolidierung mit Imprecise Mengendefizit- (Szenario 5)
        test_quantity_consolidation_with_imprecise_quantity_deficit
    - Anzeige der Einzeldiffs - (Szenario 6)
        test_display_of_single_diffs
    - Subbaugruppen mit eigenständiger Ableitung (cdb_depends_on Beziehung) - (Szenario 7)
        Sub assemblies with independent derivation
    - Unabhängige Subbaugruppen des Ableitungstyps - (Szenario 8)
        Independent subassemblies of the derivation type
    
    """

    def test_example_quantity_consolidation_and_view_independence(self):
        lps = ProductStructure(self.scenario1Left)
        rps = ProductStructure(self.scenario1Right)
        differ = xBOMQuantityDiff(lps, rps)
        diffs = differ.get_diffs()
        assert len(diffs) == 1, \
            "There must be 1 difference"
        assert diffs[('293003', '')] == -1, \
            "The part 293003 must be 2 times on the left side and 1 time on the right side"

    def test_mixed_precise_and_imprecise_occurrence(self):
        lps = ProductStructure(self.scenario2Left)
        rps = ProductStructure(self.scenario2Right)
        differ = xBOMQuantityDiff(lps, rps)
        diffs = differ.get_diffs()
        assert len(diffs) == 2
        assert diffs[('293005', '')] == -1
        assert diffs[('293005', 'a')] == 1

    def test_quantity_consolidation_with_multiple_index_stands_of_the_master_bom(self):
        lps = ProductStructure(self.scenario3Left)
        rps = ProductStructure(self.scenario3Right)
        differ = xBOMQuantityDiff(lps, rps)
        diffs = differ.get_diffs()
        assert len(diffs) == 0

    def test_imprecise_quantity_consolidation_with_quantity_surplus(self):
        lps = ProductStructure(self.scenario4Left)
        rps = ProductStructure(self.scenario4Right)
        differ = xBOMQuantityDiff(lps, rps)
        diffs = differ.get_diffs()
        assert len(diffs) == 3, \
            "There must be 3 differences"
        assert diffs[('293011', 'IMP')] == 1
        assert diffs[('293012', 'IMP')] == 1
        assert diffs[('293012', 'b')] == 1

    def test_quantity_consolidation_with_imprecise_quantity_deficit(self):
        lps = ProductStructure(self.scenario5Left)
        rps = ProductStructure(self.scenario5Right)
        differ = xBOMQuantityDiff(lps, rps)
        diffs = differ.get_diffs()
        assert len(diffs) == 1
        assert diffs[('293014', 'IMP')] == -2

    def test_display_of_single_diffs(self):
        lps = ProductStructure(self.scenario6Left)
        rps = ProductStructure(self.scenario6Right)
        differ = xBOMQuantityDiff(lps, rps)
        diffs = differ.get_diffs()
        assert len(diffs) == 4
        assert diffs[('293022', '')] == -2
        assert diffs[('293022', 'a')] == -1
        assert diffs[('293022', 'b')] == 1
        assert diffs[('293022', 'IMP')] == 1

    def test_Sub_assemblies_with_independent_derivation(self):
        lps = ProductStructure(self.scenario7Left)
        rps = ProductStructure(self.scenario7Right)
        differ = xBOMQuantityDiff(lps, rps)
        diffs = differ.get_diffs()
        assert len(diffs) == 0

    def test_Independent_subassemblies_of_the_derivation_type(self):
        lps = ProductStructure(self.scenario8Left)
        rps = ProductStructure(self.scenario8Right)
        differ = xBOMQuantityDiff(lps, rps)
        diffs = differ.get_diffs()
        assert len(diffs) == 0

    def test_all(self):
        lps = ProductStructure(self.rootLeft)
        rps = ProductStructure(self.rootRight)
        differ = xBOMQuantityDiff(lps, rps)
        diffs = differ.get_diffs()
        assert len(diffs) == 11
        assert diffs[('293003', '')] == -1
        assert diffs[('293005', '')] == -1
        assert diffs[('293005', 'a')] == 1
        assert diffs[('293011', 'IMP')] == 1
        assert diffs[('293012', 'IMP')] == 1
        assert diffs[('293012', 'b')] == 1
        assert diffs[('293014', 'IMP')] == -2
        assert diffs[('293022', '')] == -2
        assert diffs[('293022', 'a')] == -1
        assert diffs[('293022', 'b')] == 1
        assert diffs[('293022', 'IMP')] == 1

    def test_when_moving_mbom_pos_then_diff_computes_correctly(self):
        ebom_root = generateItem()
        ebom_child_1 = generateItem()
        generateAssemblyComponent(ebom_root, ebom_child_1, menge=1.0, is_imprecise=0)
        ebom_child_2 = generateItem()
        generateAssemblyComponent(ebom_root, ebom_child_2, menge=1.0, is_imprecise=0)

        mbom_root = ebom_root.generate_mbom()
        mbom_child_1 = ebom_child_1.generate_mbom()
        mbom_child_2 = ebom_child_2.generate_mbom()
        mbom_bom_item_1 = generateAssemblyComponent(mbom_root, mbom_child_1, menge=2.0, is_imprecise=0)
        mbom_bom_item_2 = generateAssemblyComponent(mbom_root, mbom_child_2, menge=2.0, is_imprecise=0)

        lps = ProductStructure(ebom_root)
        rps = ProductStructure(mbom_root)
        differ = xBOMQuantityDiff(lps, rps)
        diffs = differ.get_diffs()
        self.assertEqual(2, len(diffs))
        self.assertEqual(1.0, diffs[(ebom_child_1.teilenummer, ebom_child_1.t_index)])
        self.assertEqual(1.0, diffs[(ebom_child_2.teilenummer, ebom_child_2.t_index)])

        # Move the second BOM item below the first. The first BOM item should be set its baugruppenart to
        # 'Baugruppe' and the diff should thus change.
        operations.operation(
            constants.kOperationModify,
            mbom_bom_item_2,
            baugruppe=mbom_bom_item_1.teilenummer,
            b_index=mbom_bom_item_1.t_index

        )

        lps = ProductStructure(ebom_root)
        rps = ProductStructure(mbom_root)
        differ = xBOMQuantityDiff(lps, rps)
        diffs = differ.get_diffs()
        self.assertEqual(2, len(diffs))
        self.assertEqual(1.0, diffs[(ebom_child_1.teilenummer, ebom_child_1.t_index)])
        self.assertEqual(3.0, diffs[(ebom_child_2.teilenummer, ebom_child_2.t_index)])
