# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com


import unittest

from cs.vp.cad.file_type_list import parse_file_types, FileTypeList


class TestParseFileTypes(unittest.TestCase):

    def test_parse_invalid_lists(self):
        self.assertEqual([], parse_file_types(None))
        self.assertEqual([], parse_file_types(""))
        self.assertEqual([], parse_file_types(" "))
        self.assertEqual([], parse_file_types(","))
        self.assertEqual([], parse_file_types(",,"))

    def test_parse_single_type(self):
        self.assertEqual(["PNG"], parse_file_types("PNG"))

    def test_parse_single_type_leading_comma(self):
        self.assertEqual(["PNG"], parse_file_types(",PNG"))

    def test_parse_single_type_trailing_comma(self):
        self.assertEqual(["PNG"], parse_file_types("PNG,"))

    def test_parse_multiple_types(self):
        self.assertEqual(["PNG", "JPG", "JPEG", "Acrobat"], parse_file_types("PNG, JPG, JPEG, Acrobat"))


class TestFileTypeList(unittest.TestCase):

    def test_initialize(self):
        self.assertEqual([], FileTypeList().file_types)
        self.assertEqual([], FileTypeList(None).file_types)
        self.assertEqual([], FileTypeList("").file_types)
        self.assertEqual([], FileTypeList(" ").file_types)
        self.assertEqual(["Acrobat"], FileTypeList("Acrobat").file_types)
        self.assertEqual(["Acrobat", "PNG"], FileTypeList("Acrobat", "PNG").file_types)

    def test_initialize_clean_types(self):
        self.assertEqual(["Acrobat", "PNG"], FileTypeList("", "  Acrobat", "PNG  ").file_types)

    def test_initialize_from_string(self):
        self.assertEqual(["Acrobat"], FileTypeList.from_string("Acrobat").file_types)
        self.assertEqual(["Acrobat", "PNG"], FileTypeList.from_string("Acrobat, PNG").file_types)

    def test_contains(self):
        self.assertTrue(FileTypeList("Acrobat", "PNG").contains("PNG"))
        self.assertFalse(FileTypeList("Acrobat", "PNG").contains("JPG"))

    def test_contains_case_insensitive(self):
        self.assertTrue(FileTypeList("Acrobat").contains("aCrObAt"))
