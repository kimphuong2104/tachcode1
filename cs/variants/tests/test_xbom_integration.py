# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import collections
import datetime

from cdb.objects.operations import form_input, operation
from cs.variants.selection_condition import SelectionCondition
from cs.variants.tests import common
from cs.vp.bom import AssemblyComponent
from cs.vp.bom.bomqueries import flat_bom


class TestXBomIntegration(common.VariantsTestCase):
    def create_second_variability_model(self):
        props = collections.OrderedDict(
            [
                ("PROP3_%s" % self.timestamp, ["VALUE1", "VALUE2"]),
            ]
        )
        variability_model = common.create_variability_model(
            self.product, props, class_code="CS_VARIANTS_TEST2"
        )
        return variability_model

    def test_copy_ebom_added_as_maxbom(self):
        self.assertEquals(len(self.variability_model.MaxBOMs), 1)

        operation("CDB_Copy", self.maxbom, teilenummer="#")

        self.variability_model.Reload()
        self.assertEquals(len(self.variability_model.MaxBOMs), 2)

    def test_copy_part_copies_all_selection_conditions_on_first_level(self):
        item = common.generate_part()
        comp = common.generate_assembly_component(self.maxbom, item)
        common.generate_selection_condition(
            self.variability_model, comp, self.expression
        )

        ref_object_ids = [comp.cdb_object_id, self.subassembly_comp.cdb_object_id]
        maxbom_rules_first_level = SelectionCondition.KeywordQuery(
            ref_object_id=ref_object_ids
        )
        self.assertEquals(len(maxbom_rules_first_level), 1)

        # Modify dates to make compare robust
        maxbom_rules_first_level[0].cdb_mdate = datetime.datetime.min
        maxbom_rules_first_level[0].cdb_cdate = datetime.datetime.min

        new_bom = operation("CDB_Copy", self.maxbom, teilenummer="#")
        ref_object_ids = new_bom.Components.cdb_object_id
        self.assertEquals(len(ref_object_ids), 2)

        new_bom_rules_first_level = SelectionCondition.KeywordQuery(
            ref_object_id=ref_object_ids
        )
        self.assertEquals(len(new_bom_rules_first_level), 1)

        self.assertNotEqual(
            new_bom_rules_first_level[0].cdb_mdate,
            maxbom_rules_first_level[0].cdb_mdate,
        )
        self.assertNotEqual(
            new_bom_rules_first_level[0].cdb_cdate,
            maxbom_rules_first_level[0].cdb_cdate,
        )

    def test_index_part_copies_all_selection_conditions_on_first_level(self):
        item = common.generate_part()
        comp = common.generate_assembly_component(self.maxbom, item)
        common.generate_selection_condition(
            self.variability_model, comp, self.expression
        )

        ref_object_ids = [comp.cdb_object_id, self.subassembly_comp.cdb_object_id]
        maxbom_rules_first_level = SelectionCondition.KeywordQuery(
            ref_object_id=ref_object_ids
        )
        self.assertEquals(len(maxbom_rules_first_level), 1)

        # Modify dates to make compare robust
        maxbom_rules_first_level[0].cdb_mdate = datetime.datetime.min
        maxbom_rules_first_level[0].cdb_cdate = datetime.datetime.min

        new_bom = operation("CDB_Index", self.maxbom)
        ref_object_ids = new_bom.Components.cdb_object_id
        self.assertEquals(len(ref_object_ids), 2)

        new_bom_rules_first_level = SelectionCondition.KeywordQuery(
            ref_object_id=ref_object_ids
        )
        self.assertEquals(len(new_bom_rules_first_level), 1)

        self.assertNotEqual(
            new_bom_rules_first_level[0].cdb_mdate,
            maxbom_rules_first_level[0].cdb_mdate,
        )
        self.assertNotEqual(
            new_bom_rules_first_level[0].cdb_cdate,
            maxbom_rules_first_level[0].cdb_cdate,
        )

    def test_delete_part_deletes_all_selection_conditions_only_on_first_level(self):
        item = common.generate_part()
        comp = common.generate_assembly_component(self.maxbom, item)
        common.generate_selection_condition(
            self.variability_model, comp, self.expression
        )

        ref_object_ids = [comp.cdb_object_id, self.subassembly_comp.cdb_object_id]
        maxbom_rules = SelectionCondition.KeywordQuery(ref_object_id=ref_object_ids)
        self.assertEquals(len(maxbom_rules), 1)

        operation("CDB_Delete", self.maxbom)
        components_first_level = AssemblyComponent.KeywordQuery(
            cdb_object_id=ref_object_ids
        )
        self.assertEquals(len(components_first_level), 0)
        components_deeper_level = AssemblyComponent.KeywordQuery(
            cdb_object_id=self.comp.cdb_object_id
        )
        self.assertEquals(len(components_deeper_level), 1)

        new_bom_rules_after_delete_first_level = SelectionCondition.KeywordQuery(
            ref_object_id=ref_object_ids
        )
        self.assertEquals(len(new_bom_rules_after_delete_first_level), 0)

        new_bom_rules_after_delete_deeper = SelectionCondition.KeywordQuery(
            ref_object_id=self.comp.cdb_object_id
        )
        self.assertEquals(len(new_bom_rules_after_delete_deeper), 1)

    def test_index_ebom_added_as_maxbom(self):
        self.assertEquals(len(self.variability_model.MaxBOMs), 1)

        operation("CDB_Index", self.maxbom)

        self.variability_model.Reload()
        self.assertEquals(len(self.variability_model.MaxBOMs), 2)

    def test_create_mbom_added_as_maxbom_no_copy_bom(self):
        self.assertEquals(len(self.variability_model.MaxBOMs), 1)
        args = form_input(self.maxbom, copy_bom=False)

        # Note: The result of the operation is NOT the new mbom!
        operation("bommanager_create_rbom", self.maxbom, args)

        self.variability_model.Reload()
        self.assertEquals(len(self.variability_model.MaxBOMs), 2)

    def test_create_mbom_added_as_maxbom_with_copy_bom(self):
        self.assertEquals(len(self.variability_model.MaxBOMs), 1)
        args = form_input(self.maxbom, copy_bom=True)

        # Note: The result of the operation is NOT the new mbom!
        operation("bommanager_create_rbom", self.maxbom, args)

        self.variability_model.Reload()
        self.assertEquals(len(self.variability_model.MaxBOMs), 2)

    def test_create_mbom_added_as_maxbom_with_multiple_var_models(self):
        self.assertEquals(len(self.variability_model.MaxBOMs), 1)

        var_model = self.create_second_variability_model()
        common.generate_product_bom(self.maxbom, var_model)
        self.assertEquals(len(var_model.MaxBOMs), 1)

        args = form_input(self.maxbom, copy_bom=False)

        # Note: The result of the operation is NOT the new mbom!
        operation("bommanager_create_rbom", self.maxbom, args)

        self.variability_model.Reload()
        self.assertEquals(len(self.variability_model.MaxBOMs), 2)

        var_model.Reload()
        self.assertEquals(len(var_model.MaxBOMs), 2)

    def test_create_new_mbom_does_not_copy_rules(self):
        item = common.generate_part()
        comp = common.generate_assembly_component(self.maxbom, item)
        common.generate_selection_condition(
            self.variability_model, comp, self.expression
        )

        ref_object_ids = [each["cdb_object_id"] for each in flat_bom(self.maxbom)]
        num_rules = SelectionCondition.KeywordQuery(ref_object_id=ref_object_ids)
        self.assertGreater(len(num_rules), 0, "maxbom has no rules")

        args = form_input(self.maxbom, copy_bom=False)
        # Note: The result of the operation is NOT the new mbom!
        operation("bommanager_create_rbom", self.maxbom, args)
        self.variability_model.Reload()

        mbom = None
        for each in self.variability_model.MaxBOMs:
            if each.teilenummer != self.maxbom.teilenummer:
                mbom = each

        self.assertIsNotNone(mbom, "can not find newly created mbom")
        ref_object_ids = [each["cdb_object_id"] for each in flat_bom(mbom)]
        num_rules = SelectionCondition.KeywordQuery(ref_object_id=ref_object_ids)
        self.assertEquals(len(num_rules), 0)

    def test_create_new_mbom_does_copy_rules(self):
        item = common.generate_part()
        comp = common.generate_assembly_component(self.maxbom, item)
        common.generate_selection_condition(
            self.variability_model, comp, self.expression
        )

        ref_object_ids = [each["cdb_object_id"] for each in flat_bom(self.maxbom)]
        num_rules = SelectionCondition.KeywordQuery(ref_object_id=ref_object_ids)
        self.assertGreater(len(num_rules), 0, "maxbom has no rules")

        args = form_input(self.maxbom, copy_bom=True)
        # Note: The result of the operation is NOT the new mbom!
        operation("bommanager_create_rbom", self.maxbom, args)
        self.variability_model.Reload()

        mbom = None
        for each in self.variability_model.MaxBOMs:
            if each.teilenummer != self.maxbom.teilenummer:
                mbom = each

        self.assertIsNotNone(mbom, "can not find newly created mbom")
        ref_object_ids = [each["cdb_object_id"] for each in flat_bom(mbom)]
        num_rules2 = SelectionCondition.KeywordQuery(ref_object_id=ref_object_ids)
        self.assertEquals(len(num_rules2), len(num_rules))
