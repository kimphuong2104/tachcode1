# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Test maxbom instantiation
"""

from cdb import testcase

from cs.vp.variants.tests import common

__docformat__ = "restructuredtext en"
__revision__ = "$Id: python_template 4042 2019-08-27 07:30:13Z js $"


class TestInstantiation(testcase.RollbackTestCase):
    def make_product(self):
        self.product = common.generateProduct()

        def make_prop_value(prop, name):
            return common.generateProductPropertyValue(
                prop,
                user_input={
                    "name": name,
                    "value_txt_de": name,
                    "value_txt_en": name,
                }
            )

        def make_prop(name):
            prop = common.generateProductProperty(
                self.product,
                user_input={
                    'data_type': 'alphanumeric',
                    'name_de': name
                }
            )

            make_prop_value(prop, "VALUE 1")
            make_prop_value(prop, "VALUE 2")

            return prop

        make_prop("PROP_1")
        make_prop("PROP_2")
        self.variant = common.generateNVariants(self.product, 1)[0]

        # maxbom
        # |-> comp with predicate
        # |-> subassembly without predicates
        #     | -> comp with predicate
        #     | -> comp without predicate

        self.maxbom = common.generateItem()
        self.maxbom_comp = common.generateAssemblyComponent(self.maxbom)
        common.generateStringPredicate(self.maxbom_comp, self.product, "1 == 0")

        self.subassembly = common.generateItem()
        self.maxbom_subassembly_comp = common.generateAssemblyComponent(self.maxbom, self.subassembly)
        self.subassembly_comp = common.generateAssemblyComponent(self.subassembly)
        common.generateAssemblyComponent(self.subassembly)
        common.generateStringPredicate(self.subassembly_comp, self.product, "1 == 0")

        common.generateProductAssemblyLink(self.product, self.maxbom)

    def setUp(self):
        super(TestInstantiation, self).setUp()

        self.make_product()

    def make_assertions_new_instance(self, instance):
        got = len(instance.Components)
        assert got == 1, \
            "The instance as an unexpected number of components (expected 1, got %s)" % got

        subinstance = instance.Components[0].Item
        assert subinstance.MaxBOM is not None, "The subassembly is not a variant instance"

        assert (
            subinstance.MaxBOM.teilenummer == self.subassembly.teilenummer
            and subinstance.MaxBOM.t_index == self.subassembly.t_index
        ), "The subassembly is not an instance of the submaxbom "\
            "(expected %s %s got %s %s)" % (
                self.subassembly.teilenummer,
                self.subassembly.t_index,
                subinstance.MaxBOM.teilenummer,
                subinstance.MaxBOM.t_index
            )

        got = len(subinstance.Components)
        assert got == 1, \
            "The subinstance as an unexpected number of components (expected 1, got %s)" % got

    def test_instantiation_with_new(self):
        "The instantiate_bom method will create new items for the subinstances"

        data = [{
            "instance": "NEW",
            "path": [self.maxbom_subassembly_comp]
        }]

        instance = self.maxbom.instantiate_bom(self.variant, data)
        self.make_assertions_new_instance(instance)

    def test_instantiation_with_replace(self):
        "The instantiate_bom method will reuse old instances for the subassemblies"

        subinstance = self.subassembly.instantiate_bom(self.variant)
        data = [{
            "instance": subinstance,
            "path": [self.maxbom_subassembly_comp]
        }]

        instance = self.maxbom.instantiate_bom(self.variant, data)
        self.make_assertions_new_instance(instance)

        got = instance.Components[0].Item
        assert got.cdb_object_id == subinstance.cdb_object_id, "The subinstance has not been reused"

    def test_reinstantiate_bom(self):
        "The instantiate_bom method will reinstatiate the structure of an existing instance"

        data = [{
            "instance": "NEW",
            "path": [self.maxbom_subassembly_comp]
        }]

        instance = self.maxbom.instantiate_bom(self.variant, data)

        # change predicate to test the new structure
        self.maxbom_comp.VPMPredicates[0].expression = "1 == 1"

        # test regression for E054009: create position with unconventional position number
        new_comp = common.generateAssemblyComponent(self.maxbom, user_input_custom={"position":42})
        common.generateStringPredicate(new_comp, self.product, "1 == 0")

        new_instance = self.maxbom.instantiate_bom(self.variant, data, instance=instance)

        # check that the structure has be recomputed
        got = len(instance.Components)
        assert got == 2, \
            "The instance as an unexpected number of components (expected 2, got %s)" % got

        assert instance.cdb_object_id == new_instance.cdb_object_id, \
            "The instance has not been updated. A new part has been instanciated."
