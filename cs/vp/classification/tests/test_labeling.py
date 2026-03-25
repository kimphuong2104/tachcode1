# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tests for the labeling of parts with sml
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Some imports
from cdb.testcase import RollbackTestCase
from cdb.objects import operations

from cs.vp import classification
from cs.vp.classification import sml
import cs.vp.classification.tests as common


# Exported objects
__all__ = []


# def setup():
#     from cdb import testcase
#     testcase.run_level_setup()


class TestLabeling(RollbackTestCase):
    def setUp(self):
        super(TestLabeling, self).setUp()

        self.propset = common.generatePropertySet()
        self.prop = common.generateProperty(
            din4001_mm_dt="Z",
            din4001_mm_v1=2,
            din4001_mm_n1=2
        )
        common.assignPropertyToSet(self.prop, self.propset)

        operations.operation(
            "cdbsml_mkpset",
            classification.PropertySet
        )

        self.part = common.generateItem(sachgruppe=self.propset.pset_id)
        common.setProperty(self.part, self.propset.pset_id, self.prop, value=3.14)

    def test_strip_trailing_zeros(self):
        """trailing zeros for float properties are stripped in the computed label"""
        properties = sml.LoadProperties(self.part)

        expected = "3.14"
        got = sml.BuildDescriptiveText("[test]", self.part, properties)
        assert got == expected, "wrong label: expected '%s', got '%s'" % (expected, got)
