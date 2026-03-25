# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
import logging
import os
from cs.requirements.tests.utils import RequirementsNoRollbackTestCase
from cs.requirements_reqif.reqif_parser import ReqIFParser
LOG = logging.getLogger(__name__)


class TestReqIFParser(RequirementsNoRollbackTestCase):
    def test_attribute_value_enumeration_with_empty_values_tag(self):
        reqif_files = [os.path.join(os.path.dirname(__file__), "E075261.reqif")]
        with ReqIFParser(
            reqif_files=reqif_files,
        ) as parser_result:
            self.assertEqual(len(parser_result.specifications), 1)
            self.assertEqual(len(parser_result.spec_objects), 1)
            spec_objects = list(parser_result.spec_objects.values())
            self.assertEqual(len(spec_objects[0]["values"]), 1)
            self.assertEqual(spec_objects[0]["values"][0]["definition"], "_4718")
            self.assertIn("values", spec_objects[0]["values"][0])
            self.assertEqual(spec_objects[0]["values"][0]["values"], [])
