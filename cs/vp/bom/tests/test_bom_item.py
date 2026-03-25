"""
Tests for the bom items
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

from datetime import datetime

from cdb import constants, ElementsError
from cdb.objects import operations
from cdb.platform import gui
from cdb.testcase import RollbackTestCase
from cdb.validationkit import run_with_roles
from mock import patch, MagicMock

from cs.vp.bom import AssemblyComponent
from cs.vp.items import Item
from cs.vp.items.tests import generateItem


class TestBomItem(RollbackTestCase):

    def _createAssemblyComponent(self, is_imprecise=None):
        assembly = generateItem(benennung="assembly")
        component = generateItem(benennung="component")
        args = {
            "baugruppe": assembly.teilenummer,
            "b_index": assembly.t_index,
            "teilenummer": component.teilenummer,
            "t_index": component.t_index,
            "is_imprecise": is_imprecise,
            "position": 10,
        }
        return operations.operation(
            constants.kOperationNew,
            AssemblyComponent,
            **args
        )

    @patch.object(AssemblyComponent, 'get_bom_mode')
    def test_is_imprecise(self, mock_get_bom_mode):
        mock_get_bom_mode.return_value = 'precise'
        bom_item = self._createAssemblyComponent()
        self.assertEqual(bom_item.is_imprecise, 0)

        mock_get_bom_mode.return_value = 'preferred_precise'
        bom_item = self._createAssemblyComponent()
        self.assertEqual(bom_item.is_imprecise, 0)

        mock_get_bom_mode.return_value = 'imprecise'
        bom_item = self._createAssemblyComponent()
        self.assertEqual(bom_item.is_imprecise, 1)

        mock_get_bom_mode.return_value = 'preferred_imprecise'
        bom_item = self._createAssemblyComponent()
        self.assertEqual(bom_item.is_imprecise, 1)

    def test_when_adding_position_then_mark_assembly(self):
        assembly = generateItem()
        self.assertIsNone(assembly.baugruppenart)

        component = generateItem()
        operations.operation(
            constants.kOperationNew,
            AssemblyComponent,
            baugruppe=assembly.teilenummer,
            b_index=assembly.t_index,
            teilenummer=component.teilenummer,
            t_index=component.t_index,
            position=10
        )

        assembly.Reload()
        component.Reload()
        self.assertEqual('Baugruppe', assembly.baugruppenart)
        self.assertIsNone(component.baugruppenart)

    def test_when_copying_position_then_mark_other_assembly(self):
        bom_item = self._createAssemblyComponent()

        other_assembly = generateItem()
        self.assertIsNone(other_assembly.baugruppenart)

        # Copy existing BOM Item to another assembly. We expect that baugruppenart gets set for that assembly.
        operations.operation(
            constants.kOperationCopy,
            bom_item,
            baugruppe=other_assembly.teilenummer,
            b_index=other_assembly.t_index,
        )
        other_assembly.Reload()
        self.assertEqual('Baugruppe', other_assembly.baugruppenart)

    def test_when_changing_assembly_then_mark_as_assembly(self):
        bom_item = self._createAssemblyComponent()

        other_assembly = generateItem()
        self.assertIsNone(other_assembly.baugruppenart)

        # Modify existing BOM Item to be in another assembly. We expect that baugruppenart gets set for the
        # new assembly.
        operations.operation(
            constants.kOperationModify,
            bom_item,
            baugruppe=other_assembly.teilenummer,
            b_index=other_assembly.t_index,
        )
        other_assembly.Reload()
        self.assertEqual('Baugruppe', other_assembly.baugruppenart)

    def test_when_changing_assembly_index_then_mark_as_assembly(self):
        assembly = generateItem()
        assembly_index = operations.operation(constants.kOperationIndex, assembly)
        component = generateItem()

        bom_item = operations.operation(
            constants.kOperationNew,
            AssemblyComponent,
            baugruppe=assembly.teilenummer,
            b_index=assembly.t_index,
            teilenummer=component.teilenummer,
            t_index=component.t_index,
            position=10
        )

        self.assertEqual('', assembly_index.baugruppenart)

        # Modify existing BOM Item to be in another index of the assembly. We expect that baugruppenart gets
        # set for the new assembly.
        operations.operation(constants.kOperationModify, bom_item, b_index=assembly_index.t_index)

        assembly_index.Reload()
        self.assertEqual('Baugruppe', assembly_index.baugruppenart)

    @patch('cs.vp.bom.sqlapi.SQLupdate')
    def test_when_not_changing_assembly_then_skip_query(self, sql_update_mock: MagicMock):
        bom_item = self._createAssemblyComponent()

        operations.operation(constants.kOperationModify, bom_item, menge=2.0)
        sql_update_mock.assert_not_called()

    def test_when_changing_assembly_then_update_source_change_control(self):
        bom_item = self._createAssemblyComponent()
        assembly = Item.ByKeys(teilenummer=bom_item.baugruppe, t_index=bom_item.b_index)

        # Set change control attributes to dummy data so we can assert against it later more easily.
        assembly.cdb_m2date = datetime(2000, 1, 1)
        assembly.cdb_m2persno = 'dummy_user'
        self.assertEqual(datetime(2000, 1, 1), assembly.cdb_m2date)
        self.assertEqual('dummy_user', assembly.cdb_m2persno)

        # Modify existing BOM Item to be in another assembly. We expect that the change control on the source
        # assembly (m2date / m2persno) updated.
        other_assembly = generateItem()
        operations.operation(
            constants.kOperationModify,
            bom_item,
            baugruppe=other_assembly.teilenummer,
            b_index=other_assembly.t_index,
        )
        assembly.Reload()

        self.assertTrue(assembly.cdb_m2date > datetime(2000, 1, 1))
        self.assertNotEqual('dummy_user', assembly.cdb_m2persno)

    def test_when_changing_assembly_then_update_target_change_control(self):
        bom_item = self._createAssemblyComponent()

        # Modify existing BOM Item to be in another assembly. We expect that the change control on the source
        # assembly (m2date / m2persno) updated.
        other_assembly = generateItem()

        # Set change control attributes to dummy data so we can assert against it later more easily.
        other_assembly.cdb_m2date = datetime(2000, 1, 1)
        other_assembly.cdb_m2persno = 'dummy_user'
        self.assertEqual(datetime(2000, 1, 1), other_assembly.cdb_m2date)
        self.assertEqual('dummy_user', other_assembly.cdb_m2persno)

        operations.operation(
            constants.kOperationModify,
            bom_item,
            baugruppe=other_assembly.teilenummer,
            b_index=other_assembly.t_index,
        )
        other_assembly.Reload()

        self.assertTrue(other_assembly.cdb_m2date > datetime(2000, 1, 1))
        self.assertNotEqual('dummy_user', other_assembly.cdb_m2persno)

    @run_with_roles(['public', 'Engineering'])
    def test_when_source_assembly_released_then_save_bom_prevents_change(self):
        """
        Tests access check with the standard configured access domain. Removing the BOM item should raise
        error due to save_bom right not being granted for the released source assembly.
        """
        bom_item = self._createAssemblyComponent()
        # Release component.
        bom_item.Item.ChangeState(200)
        # Release assembly.
        bom_item.Assembly.ChangeState(200)

        other_assembly = generateItem()

        with patch('cs.vp.bom.AssemblyComponent.handle_change_assembly') as mock_handler:
            with self.assertRaises(ElementsError) as raise_context:
                operations.operation(
                    constants.kOperationModify,
                    bom_item,
                    baugruppe=other_assembly.teilenummer,
                    b_index=other_assembly.t_index,
                )

            from cdb.platform.mom.operations import OperationInfo
            op_label: str = OperationInfo('bom_item', 'CDB_Modify').get_label().strip()
            expected_msg = gui.Message.GetMessage('authorization_fail', op_label, 'teile_stamm', 'save_bom')

            self.assertIn(expected_msg, str(raise_context.exception))

            # Since access is checked on the CDB_Modify call, we expect the handler to not even be executed.
            mock_handler.assert_not_called()

    def test_when_source_assembly_released_then_delete_bom_prevents_change(self):
        """
        Tests access check for delete_bom right in handle_change_assembly() handler. Removing the BOM item
        should raise error due to delete_bom right not being granted for the released source assembly.
        """
        bom_item = self._createAssemblyComponent()
        # Release component.
        bom_item.Item.ChangeState(200)
        # Release assembly.
        bom_item.Assembly.ChangeState(200)

        other_assembly = generateItem()

        # We need to run this test as caddok, otherwise the standard access domain would raise the save_bom
        # access error before calling handle_change_assembly() (see test case above). To still check for our
        # custom delete_bom access error, we're creating a mock and mock its CheckAccess() function to return
        # False.
        with patch('cs.vp.bom.Item.ByKeys') as mock_by_keys:
            mock_item = MagicMock()
            mock_item.CheckAccess.return_value = False
            mock_by_keys.return_value = mock_item

            with self.assertRaises(ElementsError) as raise_context:
                operations.operation(
                    constants.kOperationModify,
                    bom_item,
                    baugruppe=other_assembly.teilenummer,
                    b_index=other_assembly.t_index,
                )

            from cdb.platform.mom.operations import OperationInfo
            op_label: str = OperationInfo('bom_item', 'CDB_Modify').get_label().strip()
            expected_msg = gui.Message.GetMessage('authorization_fail', op_label, 'teile_stamm', 'delete_bom')

            self.assertEqual(expected_msg, str(raise_context.exception))

    @run_with_roles(['public', 'Engineering'])
    def test_deny_moving_position_to_released_assembly(self):
        """
        Tests custom access check in mark_as_assembly().
        """
        bom_item = self._createAssemblyComponent()

        other_assembly = generateItem()
        # Release other assembly.
        other_assembly.ChangeState(200)

        with self.assertRaises(ElementsError) as raise_context:
            operations.operation(
                constants.kOperationModify,
                bom_item,
                baugruppe=other_assembly.teilenummer,
                b_index=other_assembly.t_index,
            )

        from cdb.platform.mom.operations import OperationInfo
        op_label: str = OperationInfo('bom_item', 'CDB_Modify').get_label().strip()
        expected_msg = gui.Message.GetMessage('authorization_fail', op_label, 'teile_stamm', 'create_bom')

        self.assertEqual(expected_msg, str(raise_context.exception))
