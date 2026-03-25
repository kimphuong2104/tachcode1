from datetime import datetime, timedelta

from cdb import sqlapi
from cdb.testcase import RollbackTestCase

from cs.vp.bom.bomqueries import get_sort_key, get_path_sort_key
from cs.vp.bom.tests import generateItem, generateAssemblyComponent


class TestBomItemSorting(RollbackTestCase):

    def test_sort_key_for_none(self):
        self.assertIsNone(get_sort_key(None))

    def test_sort_key_for_empty_dict(self):
        self.assertEqual((float('-inf'), '', ''), get_sort_key({}))

    def test_sort_key_for_dict(self):
        test_dict = {
                'position': 42,
                'teilenummer': '007',
                'cdb_cdate': '2023-01-01T00:00:00'
        }
        self.assertEqual(
            (test_dict['position'], test_dict['teilenummer'], test_dict['cdb_cdate']),
            get_sort_key(test_dict)
        )

    def test_sort_key_for_object_without_position(self):
        root = generateItem()
        self.assertEqual((float('-inf'), root.teilenummer, root.cdb_cdate), get_sort_key(root))

    def test_sort_key_for_object_with_position(self):
        root = generateItem()
        child = generateItem()
        bom_item_child = generateAssemblyComponent(root, child)
        self.assertEqual(
            (bom_item_child.position, child.teilenummer, bom_item_child.cdb_cdate),
            get_sort_key(bom_item_child)
        )

    def test_sort_key_for_record(self):
        root = generateItem()
        child = generateItem()
        bom_item_child = generateAssemblyComponent(root, child)
        record = sqlapi.RecordSet2('einzelteile', f'cdb_object_id=\'{bom_item_child.cdb_object_id}\'')[0]
        self.assertEqual(
            (bom_item_child.position, child.teilenummer, bom_item_child.cdb_cdate),
            get_sort_key(record)
        )

    # Regression test for E074336.
    def test_sort_key_for_missing_values(self):
        root = generateItem()
        root.cdb_cdate = None

        # Test that sort key has empty string even when cdb_cdate is None, e.g. for test fixture data.
        self.assertEqual((float('-inf'), root.teilenummer, ''), get_sort_key(root))


    def test_sorting_with_sort_key(self):
        root = generateItem()
        bom_1 = generateAssemblyComponent(root, generateItem(), position=1)
        bom_2 = generateAssemblyComponent(root, generateItem(), position=2)
        bom_3 = generateAssemblyComponent(root, generateItem(), position=3)
        self.assertEqual(
            [root, bom_1, bom_2, bom_3],
            sorted([bom_2, bom_1, bom_3, root], key=get_sort_key)
        )

    def test_sorting_with_same_positions_and_different_teilenummer(self):
        root = generateItem()
        bom_1 = generateAssemblyComponent(root, generateItem(teilenummer='M-001'), position=5)
        bom_2 = generateAssemblyComponent(root, generateItem(teilenummer='M-002'), position=5)
        bom_3 = generateAssemblyComponent(root, generateItem(teilenummer='M-003'), position=5)
        self.assertEqual(
            [root, bom_1, bom_2, bom_3],
            sorted([bom_2, root, bom_3, bom_1], key=get_sort_key)
        )

    def test_sorting_with_same_positions_and_teilenummer(self):
        root = generateItem()
        child = generateItem()

        bom_1 = generateAssemblyComponent(root, child, position=5)
        bom_2 = generateAssemblyComponent(root, child, position=5)
        bom_3 = generateAssemblyComponent(root, child, position=5)

        # Fake creation dates to be apart 1 day each.
        now = datetime.utcnow()
        for i, bom in enumerate([bom_1, bom_2, bom_3]):
            bom.cdb_cdate = now + timedelta(days=i)

        self.assertEqual(
            [root, bom_1, bom_2, bom_3],
            sorted([bom_3, bom_1, root, bom_2], key=get_sort_key)
        )

    def test_path_sort_key_for_empty(self):
        self.assertEqual([], get_path_sort_key([]))

    def test_path_sort_key_for_single_component(self):
        root = generateItem()
        self.assertEqual([(float('-inf'), root.teilenummer, root.cdb_cdate)], get_path_sort_key([root]))

    def test_path_sort_key(self):
        root = generateItem()
        child_1 = generateItem()
        child_1_1 = generateItem()
        child_1_2 = generateItem()

        bom_item_1 = generateAssemblyComponent(root, child_1, position=1)
        bom_item_1_1 = generateAssemblyComponent(child_1, child_1_1, position=2)
        bom_item_1_2 = generateAssemblyComponent(child_1, child_1_2, position=3)

        n_inf = float('-inf')
        self.assertEqual(
            [(n_inf, root.teilenummer, root.cdb_cdate)],
            get_path_sort_key([root])
        )
        self.assertEqual(
            [
                (n_inf, root.teilenummer, root.cdb_cdate),
                (1, bom_item_1.teilenummer, bom_item_1.cdb_cdate)
            ],
            get_path_sort_key([root, bom_item_1])
        )
        self.assertEqual(
            [
                (n_inf, root.teilenummer, root.cdb_cdate),
                (1, bom_item_1.teilenummer, bom_item_1.cdb_cdate),
                (2, bom_item_1_1.teilenummer, bom_item_1_1.cdb_cdate)
            ],
            get_path_sort_key([root, bom_item_1, bom_item_1_1])
        )
        self.assertEqual(
            [
                (n_inf, root.teilenummer, root.cdb_cdate),
                (1, bom_item_1.teilenummer, bom_item_1.cdb_cdate),
                (2, bom_item_1_1.teilenummer, bom_item_1_1.cdb_cdate),
                (3, bom_item_1_2.teilenummer, bom_item_1_2.cdb_cdate)
            ],
            get_path_sort_key([root, bom_item_1, bom_item_1_1, bom_item_1_2])
        )
        # Also test without root.
        self.assertEqual(
            [
                (1, bom_item_1.teilenummer, bom_item_1.cdb_cdate),
                (2, bom_item_1_1.teilenummer, bom_item_1_1.cdb_cdate),
                (3, bom_item_1_2.teilenummer, bom_item_1_2.cdb_cdate)
            ],
            get_path_sort_key([bom_item_1, bom_item_1_1, bom_item_1_2])
        )

    def test_sorting_paths_same_length(self):
        root = generateItem()
        child_1 = generateItem()

        bom_item_1 = generateAssemblyComponent(root, child_1, position=1)

        bom_item_1_1 = generateAssemblyComponent(child_1, generateItem(), position=1)
        bom_item_1_2 = generateAssemblyComponent(child_1, generateItem(), position=2)
        bom_item_1_3 = generateAssemblyComponent(child_1, generateItem(), position=3)

        path_1 = [root, bom_item_1, bom_item_1_1]
        path_2 = [root, bom_item_1, bom_item_1_2]
        path_3 = [root, bom_item_1, bom_item_1_3]

        self.assertEqual([path_1, path_2, path_3], sorted([path_3, path_1, path_2], key=get_path_sort_key))

    def test_sorting_paths_unequal_length(self):
        # root
        # |
        # |_ 1: child_1
        #    |
        #    |_ 1: child_1_1
        #    |
        #    |_ 2: child_1_2
        #    |  |
        #    |  |_ 1: child_1_2_1
        #    |
        #    |_ 3: child_1_3

        root = generateItem()
        child_1 = generateItem()
        bom_item_1 = generateAssemblyComponent(root, child_1, position=1)

        bom_item_1_1 = generateAssemblyComponent(child_1, generateItem(), position=1)

        child_1_2 = generateItem()
        bom_item_1_2 = generateAssemblyComponent(child_1, child_1_2, position=2)
        bom_item_1_2_1 = generateAssemblyComponent(child_1_2, generateItem(), position=1)

        bom_item_1_3 = generateAssemblyComponent(child_1, generateItem(), position=3)

        path_0 = [root, bom_item_1]
        path_1 = [root, bom_item_1, bom_item_1_1]
        path_2 = [root, bom_item_1, bom_item_1_2]
        path_3 = [root, bom_item_1, bom_item_1_2, bom_item_1_2_1]
        path_4 = [root, bom_item_1, bom_item_1_3]

        self.assertEqual(
            [path_0, path_1, path_2, path_3, path_4],
            sorted([path_4, path_2, path_3, path_1, path_0], key=get_path_sort_key)
        )

    def test_sorting_paths_by_teilenummer(self):
        root = generateItem()
        child_1 = generateItem()

        bom_item_1 = generateAssemblyComponent(root, child_1, position=1)

        bom_item_1_1 = generateAssemblyComponent(child_1, generateItem(), position=1)
        bom_item_1_2 = generateAssemblyComponent(child_1, generateItem(), position=1)
        bom_item_1_3 = generateAssemblyComponent(child_1, generateItem(), position=1)

        path_0 = [root, bom_item_1]
        path_1 = [root, bom_item_1, bom_item_1_1]
        path_2 = [root, bom_item_1, bom_item_1_2]
        path_3 = [root, bom_item_1, bom_item_1_3]

        self.assertEqual(
            [path_0, path_1, path_2, path_3],
            sorted([path_1, path_0, path_3, path_2], key=get_path_sort_key)
        )

    def test_sorting_paths_by_date(self):
        root = generateItem()
        child_1 = generateItem()
        child_1_1 = generateItem()

        bom_item_1 = generateAssemblyComponent(root, child_1, position=1)

        bom_item_1_1 = generateAssemblyComponent(child_1, child_1_1, position=1)
        bom_item_1_2 = generateAssemblyComponent(child_1, child_1_1, position=1)
        bom_item_1_3 = generateAssemblyComponent(child_1, child_1_1, position=1)

        now = datetime.utcnow()
        bom_item_1.cdb_cdate = now + timedelta(days=1)
        # Fake creation dates to be apart 1 day each.
        for i, bom in enumerate([bom_item_1_1, bom_item_1_2, bom_item_1_3]):
            bom.cdb_cdate = now + timedelta(days=i)

        path_0 = [root, bom_item_1]
        path_1 = [root, bom_item_1, bom_item_1_1]
        path_2 = [root, bom_item_1, bom_item_1_2]
        path_3 = [root, bom_item_1, bom_item_1_3]

        self.assertEqual(
            [path_0, path_1, path_2, path_3],
            sorted([path_3, path_1, path_2, path_0], key=get_path_sort_key)
        )
