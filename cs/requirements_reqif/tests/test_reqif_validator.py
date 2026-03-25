# !/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
from io import BytesIO
import logging

from cs.requirements.tests.utils import RequirementsNoRollbackTestCase
from cs.requirements_reqif.exceptions import ReqIFValidationError
from cs.requirements_reqif.reqif_validator import ReqIFValidator

LOG = logging.getLogger(__name__)


class TestReqIFValidator(RequirementsNoRollbackTestCase):
    def _get_content(self, content):
        content = BytesIO(content.encode('utf-8'))
        return content

    def setUp(self):
        super(TestReqIFValidator, self).setUp()
        self.reqif_validator = ReqIFValidator()
        self.empty_div = '<xhtml:div></xhtml:div>'
        self.two_div_with_surrounding_div = '<xhtml:div><xhtml:div></xhtml:div><xhtml:div></xhtml:div></xhtml:div>'
        self.two_div_without_surrounding_div = '<xhtml:div></xhtml:div><xhtml:div></xhtml:div>'
        self.invalid_external_element = '<xhtml:div><xhtml:object><EXTERNAL:x xmlns:EXTERNAL="http://example.org/example.xsd"/></xhtml:object></xhtml:div>'
        self.valid_external_element = '<xhtml:div><xhtml:object data="http://www.example.com/myclock.class" type="application/x-java-applet"></xhtml:object></xhtml:div>'
        self.valid_object_chain = '<xhtml:div><xhtml:object data="obj1" type="application/svg+xml"><xhtml:object data="obj2" type="image/png">Alternative Textual Representation</xhtml:object></xhtml:object></xhtml:div>'

    def test_empty_richtext_with_empty_div(self):
        content = self._get_content(ReqIFValidator.dummy_reqif.format(self.empty_div))
        self.assertTrue(self.reqif_validator.is_valid(content))
        self.assertTrue(self.reqif_validator.has_valid_xhtml_field_content(self.empty_div))

    def test_empty_richtext(self):
        content = self._get_content(ReqIFValidator.dummy_reqif.format(''))
        with self.assertRaises(ReqIFValidationError):
            self.reqif_validator.is_valid(content)
        with self.assertRaises(ReqIFValidationError):
            self.reqif_validator.has_valid_xhtml_field_content('')

    def test_filled_two_div_with_surrounding_div(self):
        content = self._get_content(ReqIFValidator.dummy_reqif.format(
            self.two_div_with_surrounding_div))
        self.assertTrue(self.reqif_validator.is_valid(content))
        self.assertTrue(self.reqif_validator.has_valid_xhtml_field_content(
            self.two_div_with_surrounding_div))

    def test_filled_richtext_with_two_div_without_surrounding_div(self):
        content = self._get_content(ReqIFValidator.dummy_reqif.format(self.two_div_without_surrounding_div))
        with self.assertRaises(ReqIFValidationError):
            self.reqif_validator.is_valid((content))
        with self.assertRaises(ReqIFValidationError):
            self.reqif_validator.has_valid_xhtml_field_content(self.two_div_without_surrounding_div)

    def test_filled_richtext_with_invalid_external_element(self):
        content = self._get_content(ReqIFValidator.dummy_reqif.format(self.invalid_external_element))
        with self.assertRaises(ReqIFValidationError):
            self.reqif_validator.is_valid((content))
        with self.assertRaises(ReqIFValidationError):
            self.reqif_validator.has_valid_xhtml_field_content(self.invalid_external_element)

    def test_filled_richtext_with_valid_external_element(self):
        content = self._get_content(ReqIFValidator.dummy_reqif.format(self.valid_external_element))
        self.assertTrue(self.reqif_validator.is_valid((content)))
        self.assertTrue(self.reqif_validator.has_valid_xhtml_field_content(
            self.valid_external_element))

    def test_filled_richtext_with_valid_object_chain(self):
        content = self._get_content(ReqIFValidator.dummy_reqif.format(self.valid_object_chain))
        self.assertTrue(self.reqif_validator.is_valid((content)))
        self.assertTrue(self.reqif_validator.has_valid_xhtml_field_content(self.valid_object_chain))
