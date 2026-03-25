# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/
#
# Version:  $Id$

from webtest import TestApp as Client

from cdb import testcase
from cs.classification.tests import utils
from cs.platform.web.root import Root
from cs.classification.classes import ClassificationClass


class TestObjectPlanRestApi(utils.ClassificationTestCase):

    def setUp(self):
        super(TestObjectPlanRestApi, self).setUp()
        self.client = Client(Root())

    def _test_search(self, queryString, expected_class_codes):

        with testcase.error_logging_disabled():
            url = "/classification-objectplan/internal/class_search/"
            params = {
                "dataDictionaryClassName": "document",
                "queryString": queryString
            }
            result = self.client.get(url, params, status=200)
            self._assert_dict_keys(result.json, ["classPath", "classes"], True)

            expected_class_path = []
            expected_class_path.append({
                "code": None,
                "label": "Dokument"
            })
            self.assertListEqual(expected_class_path, result.json["classPath"])

            for class_code in expected_class_codes:
                clazz = [clazz for clazz in result.json["classes"] if clazz["code"] == class_code]
                self.assertIsNotNone(clazz, "Expected class " + class_code + " not found!")

    def _assert_dict_keys(self, test_me, expected_keys, shall_contain):
        for key in expected_keys:
            self.assertEqual(shall_contain, key in test_me)

    def test_search_for_top_level_classes(self):
        """ Test searching for top level document classes. """

        expected_class_codes = []
        for clazz in ClassificationClass.get_applicable_root_classes("document"):
            expected_class_codes.append(clazz["code"])

        self._test_search("", expected_class_codes)

    def test_search_for_classes(self):
        """ Test searching for document classes. """

        found_classes = ClassificationClass.search_applicable_classes(
            'document', 'RIVET', only_active=False, only_released=False
        )
        expected_class_codes = []
        for clazz in found_classes:
            expected_class_codes.append(clazz["code"])

        self._test_search("RIVET", expected_class_codes)

    def test_class_info(self):

        with testcase.error_logging_disabled():
            class_code = "TEST_CLASS_ARTICLE"
            url = "/classification-objectplan/internal/class_info/"
            params = {
                "dataDictionaryClassName": "document",
                "classCode": class_code
            }
            result = self.client.get(url, params, status=200)
            self._assert_dict_keys(result.json, ["classPath", "classes", "picture"], True)

            expected_class_path = [
                {'code': None, 'label': 'Dokument'},
                {'code': 'TEST_BASE_CLASS', 'label': 'TEST_BASE_CLASS'},
                {'code': 'TEST_CLASS_APPLICABLE', 'label': 'TEST_CLASS_APPLICABLE'},
                {'code': 'TEST_CLASS_ARTICLE', 'label': 'TEST_CLASS_ARTICLE'}
            ]
            self.assertListEqual(expected_class_path, result.json["classPath"])

            for sub_class_code in ClassificationClass.get_sub_class_codes(class_codes=[class_code]):
                subclass = [clazz for clazz in result.json["classes"] if clazz["code"] == sub_class_code]
                self.assertIsNotNone(subclass, "Expected sub class " + sub_class_code + " not found!")
