# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module util

This module contains test methods for the utility functions.
"""

import unittest

from cdb.testcase import RollbackTestCase

from cs.documents import Document  # @UnresolvedImport

from cs.classification import util


class TestUtil(RollbackTestCase):

    def setUp(self):
        super(TestUtil, self).setUp()

    def test_check_classification_object_valid_object(self):
        """ Check classification object for valid object passes """
        d = Document.Query()[0]
        util.check_classification_object(d)

    def test_check_classification_object_none_given(self):
        """ Check classification object with none fails """
        with self.assertRaisesRegex(ValueError, "Object has no cdb_object_id"):
            util.check_classification_object(None)

    def test_check_classification_object_object_collection_given(self):
        """ Check classification object with ObjectCollection fails """
        d = Document.Query()
        with self.assertRaisesRegex(ValueError, "The cdb_object_id of the given object has to be a string"):
            util.check_classification_object(d)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
