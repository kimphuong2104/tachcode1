#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Test Module test_docref_resolver

This is the documentation for the tests.
"""


__docformat__ = "restructuredtext en"


import unittest

from cdb import testcase
from cdb.objects import NULL
from cs.documents import Document, docref_resolver_registry
from cs.documents.docref_resolver_base import BaseStrategy


# Tests
class Test_docref_resolver(testcase.RollbackTestCase):
    """
    Some smoke tests for the docref resolver
    """

    def setUp(self):
        super(Test_docref_resolver, self).setUp()
        self.pdf = Document.Create(
            z_nummer="TEST_0001", z_index="", erzeug_system="TXT"
        )
        self.none = Document.Create(
            z_nummer="TEST_0001", z_index="a", erzeug_system=NULL
        )

    def test_getStrategy(self):
        """
        Try to retrieve a resolver strategy - evenf for an object without
        ``erzeug_system`` (E045273)
        """
        for doc in [self.pdf, self.none]:
            strategy = docref_resolver_registry.Registry.getStrategy(doc)
            self.assertTrue(strategy)
            self.assertTrue(isinstance(strategy, BaseStrategy))


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
