# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from cdb.testcase import PlatformTestCase
import logging

# from cs.requirements.tests.utils import RequirementsTestCase
from cs.requirements.web.rest.specificationeditor.view import get_context_ids, \
    apply_bounds

LOG = logging.getLogger(__name__)


class TestSpecificationEditor(PlatformTestCase):

    def __init__(self, *args, **kwargs):
        super(TestSpecificationEditor, self).__init__(*args, **kwargs)

    def test_get_context_ids(self):
        with self.assertRaises(ValueError):
            _context_ids = get_context_ids([], 1, 1, 1)
        with self.assertRaises(ValueError):
            _context_ids = get_context_ids([2], 1, 1, 1)

        context_ids = get_context_ids([1], 1, 1, 1)
        self.assertEqual(context_ids, [1])

        context_ids = get_context_ids([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 5, 1, 1)
        self.assertEqual(context_ids, [4, 5, 6])

        context_ids = get_context_ids([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 5, 1, 1)
        self.assertEqual(context_ids, [4, 5, 6])

        context_ids = get_context_ids([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 5, 2, 2)
        self.assertEqual(context_ids, [3, 4, 5, 6, 7])

        context_ids = get_context_ids([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 1, 2, 2)
        self.assertEqual(context_ids, [1, 2, 3])

        context_ids = get_context_ids([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 10, 2, 2)
        self.assertEqual(context_ids, [8, 9, 10])

    def test_apply_bounds(self):
        response_orig = {}

        res = apply_bounds(all_ids=[], response=response_orig)
        self.assertEqual(res, response_orig)

        res = apply_bounds(all_ids=[1, 2, 3, 4], response=response_orig)
        self.assertEqual(res, {
            "first_id": 1,
            "last_id": 4
        })
