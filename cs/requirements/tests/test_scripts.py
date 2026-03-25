# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
import logging

from cs.requirements.scripts.find_invalid_richtexts import find_invalid_elements

from .utils import RequirementsTestCase


LOG = logging.getLogger(__name__)


class TestScripts(RequirementsTestCase):

    def __init__(self, *args, **kwargs):
        kwargs['need_uberserver'] = False
        super(TestScripts, self).__init__(*args, **kwargs)

    def test_find_invalid_richtexts_ignore_empty_not_found(self):
        """ Check whether there are (no) invalid richtexts in the whole system """
        self.assertEqual(0, find_invalid_elements(spec_ids=None, verbose=True, ignore_empty=True))

    def test_find_invalid_richtexts_found(self):
        """ Check whether there are 9 invalid richtexts in ST000000000 when not ignoring empty ones"""
        self.assertEqual(9, find_invalid_elements(
            spec_ids='ST000000000',
            verbose=True,
            ignore_empty=False)
        )
