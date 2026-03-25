# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

from cdb.objects import operations
from cdb.objects.operations import system_args
from cdb.platform.mom.relships import RelationshipDefinition
from cdb.platform.mom import SimpleArguments
from cdb.testcase import RollbackTestCase

from cs.vp.items import Item
from cs.vp.bom import AssemblyComponent, AssemblyComponentOccurrence
from cs.vp.bom.tests import generateItem, generateAssemblyComponent, generateAssemblyComponentOccurrence


class TestSkipOccurrencesForRbom(RollbackTestCase):
    """
    Tests that occurrences are not copied in the context of operations that create rBOM items.
    """

    def setUp(self):
        super(TestSkipOccurrencesForRbom, self).setUp()

        # Prepare a master eBOM with an assembled component
        self.ebom = generateItem()
        self.ebom_component = generateAssemblyComponent(self.ebom)

        # Prepare the derived mBOM.
        self.mbom = self.ebom.generate_mbom()

    def _check_relship_presence(self):
        # Check whether occurrence relship is present; skip tests otherwise.
        try:
            occurrence_relship = RelationshipDefinition("bom_item_to_occurrences")
            config_result = occurrence_relship.check_config()
            if not config_result[0]:
                self.skipTest(config_result[1])
        except AttributeError:
            self.skipTest('Relationship bom_item_to_occurrences is not configured')

    def test_if_occurrence_is_part_of_ebom(self):
        """
        Tests that BOM item's occurrences are existing as part of the BOM Item
        """
        self._check_relship_presence()

        bom_occurrence1 = generateAssemblyComponentOccurrence(self.ebom_component)
        self.ebom_component.Reload()
        self.assertEqual(self.ebom_component.Occurrences[0], bom_occurrence1)
        self.assertEqual(len(self.ebom_component.Occurrences), 1)

    def test_when_regular_copy_then_copy_occurrences(self):
        """
        Tests that when copying a BOM item outside of the xBOM manager context, occurrences relship objects
        are not skipped.
        """
        self._check_relship_presence()

        generateAssemblyComponentOccurrence(self.ebom_component)
        self.ebom_component.Reload()

        new_bom_item = operations.operation(
            "CDB_Copy",
            self.ebom_component,
            position=42
        )

        self.assertNotEqual(new_bom_item.Occurrences, [])

    def test_when_copy_with_false_flag_then_copy_occurrences(self):
        """
        Tests that BOM item's occurrences are copied when is_copy_to_rbom is explicitly set to False.
        """
        self._check_relship_presence()

        generateAssemblyComponentOccurrence(self.ebom_component)
        self.ebom_component.Reload()

        new_bom_item = operations.operation(
            "CDB_Copy",
            self.ebom_component,
            system_args(is_copy_to_rbom=False),
            baugruppe=self.mbom.teilenummer
        )

        self.assertNotEqual(new_bom_item.Occurrences, [])

    def test_when_copy_with_true_flag_then_skip_occurrences(self):
        """
        Tests that BOM item's occurrences are not copied when is_copy_to_rbom is explicitly set to True.
        """
        self._check_relship_presence()

        generateAssemblyComponentOccurrence(self.ebom_component)
        self.ebom_component.Reload()

        new_bom_item = operations.operation(
            "CDB_Copy",
            self.ebom_component,
            system_args(is_copy_to_rbom=True),
            baugruppe=self.mbom.teilenummer
        )

        self.assertEqual(new_bom_item.Occurrences, [])

    def test_when_copy_to_rbom_then_skip_occurrences(self):
        """
        Tests that when using the operation bommanager_batch_copy, the BOM item's occurrences are not copied
        to the new BOM item within the rBOM.
        """
        self._check_relship_presence()

        generateAssemblyComponentOccurrence(self.ebom_component)
        self.ebom_component.Reload()

        operations.operation(
            "bommanager_batch_copy",
            # We pass a list because of multi object operation.
            [self.ebom_component],
            # Tell operation onto what assembly we want to copy the BOM position.
            teilenummer=self.mbom.teilenummer,
            t_index=self.mbom.t_index
        )

        # bommanager_batch_copy should not have copied occurrences.
        copied_bom = AssemblyComponent.KeywordQuery(baugruppe=self.mbom.teilenummer)
        copied_occurences = AssemblyComponentOccurrence.KeywordQuery(bompos_object_id=copied_bom.cdb_object_id)

        self.assertEqual(len(copied_bom), 1)
        self.assertEqual(len(copied_occurences), 0)

    def test_when_copy_and_create_xbom_then_skip_occurrences(self):
        """
        Test that when using the operation bommanager_copy_and_create_xbom, the BOM item's occurrences are not
        copied to the new rBOM item.
        """
        self._check_relship_presence()

        generateAssemblyComponentOccurrence(self.ebom_component)
        self.ebom_component.Reload()

        operations.operation(
            "bommanager_copy_and_create_xbom",
            # We pass a list because of multi object operation.
            [self.ebom_component],
            # Tell operation onto what assembly we want to copy the BOM position.
            teilenummer=self.mbom.teilenummer,
            t_index=self.mbom.t_index
        )

        # bommanager_copy_and_create_xbom should not have copied occurrences.
        copied_bom = AssemblyComponent.KeywordQuery(baugruppe=self.mbom.teilenummer)
        copied_occurences = AssemblyComponentOccurrence.KeywordQuery(bompos_object_id=copied_bom.cdb_object_id)

        self.assertEqual(len(copied_bom), 1)
        self.assertEqual(len(copied_occurences), 0)

    def test_when_deriving_new_rbom_then_skip_occurrences(self):
        """
        Test that when using the operation bommanager_create_rbom, the BOM item's occurrences are not copied
        to the new rBOM item.
        """
        self._check_relship_presence()

        generateAssemblyComponentOccurrence(self.ebom_component)
        self.ebom_component.Reload()

        # Note: The result of the operation is NOT the new mbom!
        operations.operation("bommanager_create_rbom", self.ebom, SimpleArguments(copy_bom=1))
        derived_boms = Item.KeywordQuery(cdb_depends_on=self.ebom.cdb_object_id)
        # Ensure that there is only two derived BOMs (self.mbom and the new one).
        self.assertEqual(len(derived_boms), 2)
        # Get the derived BOM that is _not_ self.mbom.
        derived_bom = next((bom for bom in derived_boms if bom.teilenummer != self.mbom.teilenummer))

        # bommanager_create_rbom should not have copied occurrences.
        copied_bom = AssemblyComponent.KeywordQuery(baugruppe=derived_bom.teilenummer)
        copied_occurences = AssemblyComponentOccurrence.KeywordQuery(bompos_object_id=copied_bom.cdb_object_id)

        self.assertEqual(len(copied_bom), 1)
        self.assertEqual(len(copied_occurences), 0)
