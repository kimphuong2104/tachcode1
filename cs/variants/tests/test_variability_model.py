# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import collections
import time

from cdb import constants, testcase
from cdb.objects import operations
from cs.variants import VariabilityModel
from cs.variants.tests import common


class TestVariabilityModel(testcase.RollbackTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestVariabilityModel, cls).setUpClass()
        testcase.require_service("cdb.uberserver.services.index.IndexService")

    def test_create_applicability(self):
        """When a variability model is created, the class applicability for cs_variants is created"""
        product = common.generate_product()

        # the prop codes need to be unique.
        # otherwise you will get on second run an error from the index server,
        # since there's not rollback on the index server.
        timestamp = ("%s" % time.time()).replace(".", "")
        prop1 = "PROP1_%s" % timestamp
        prop2 = "PROP2_%s" % timestamp
        props = collections.OrderedDict(
            [
                (prop1, ["VALUE1", "VALUE2"]),
                (prop2, ["VALUE1", "VALUE2"]),
            ]
        )

        clazz = common.generate_class_with_props(
            props, code="CS_VARIANTS_TEST_CLASS_%s" % timestamp
        )

        # generate a variability model
        operations.operation(
            constants.kOperationNew,
            VariabilityModel,
            product_object_id=product.cdb_object_id,
            class_object_id=clazz.cdb_object_id,
        )

        applicabilities = clazz.Applicabilities.KeywordQuery(dd_classname="cs_variant")
        assert applicabilities, "The applicability has not been created"

        applicabilities = clazz.Applicabilities.KeywordQuery(dd_classname="part")
        assert applicabilities, "The applicability has not been created"
