#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tests for the hoops converter tool
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = ['Converter']

import os
import sys
import tempfile
import unittest

from cs.threed.hoops.converter.hoops import Converter


class TestConverter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestConverter, cls).setUpClass()
        module_dir = os.path.dirname(
            __file__)
        cls.files_dir = os.path.join(module_dir, "..", "..", "..", "..", "..",
                                     "tests", "accepttests", "files")

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="tmp_test_")

    def _test_conversion(self, input_basepath, params, output_path, output_suffix=None):

        input_path = os.path.join(self.files_dir, input_basepath)

        converter = Converter(
            input_path=input_path,
            params=params,
            service_mode=False
        )
        converter.execute()

        if output_suffix is not None:
            output_path = output_path + output_suffix

        self.assertTrue(os.path.exists(output_path), "Conversion result should exist")
        statinfo = os.stat(output_path)
        self.assertGreater(statinfo.st_size, 0, "Result should not be empty")


    def test_conversion_jt(self):
        input_basepath = "ProE-Part.prt"
        output_path = os.path.join(self.temp_dir, "test.jt")

        params = [
            ("output_jt", output_path),
            ("jt_level_of_detail", "1"),
        ]

        self._test_conversion(input_basepath, params, output_path)


    def test_conversion_pdf(self):
        input_basepath = "SolidWorks-part.sldprt"
        output_path = os.path.join(self.temp_dir, "test.pdf")

        params = [
            ("output_pdf", output_path),
        ]

        self._test_conversion(input_basepath, params, output_path)


    def test_conversion_png(self):
        input_basepath = "Bauteil.ipt"
        output_path = os.path.join(self.temp_dir, "test.png")

        params = [
            ("output_png", output_path),
            ("background_color", "0.75,0.86,0.97"),
            ("output_png_resolution", "1280x720")
        ]

        self._test_conversion(input_basepath, params, output_path)


    def test_conversion_prc(self):
        input_basepath = "Baugruppe.iam"
        output_path = os.path.join(self.temp_dir, "test.prc")

        params = [
            ("output_prc", output_path)
        ]

        self._test_conversion(input_basepath, params, output_path)


    def test_conversion_scz(self):
        input_basepath = "sw_cm_assembly.sldasm"
        output_path = os.path.join(self.temp_dir, "test")

        params = [
            ("output_sc", output_path),
            ("sc_create_scz", "1"),
            ("sc_compress_scz", "1"),
            ("sc_export_attributes", "1"),
            ("load_all_configurations", "1")
        ]

        self._test_conversion(input_basepath, params, output_path, ".scz")


    def test_conversion_step(self):
        input_basepath = "CatiaV5-Part.CATPart"
        output_path = os.path.join(self.temp_dir, "test.step")

        params = [
            ("output_step", output_path)
        ]

        self._test_conversion(input_basepath, params, output_path)


    def test_conversion_stl(self):
        input_basepath = "building.ifc"
        output_path = os.path.join(self.temp_dir, "test.stl")

        params = [
            ("output_stl", output_path)
        ]

        self._test_conversion(input_basepath, params, output_path)


    def test_conversion_xml(self):
        input_basepath = "assembly_with_non_ascii_chars.asm"
        output_path = os.path.join(self.temp_dir, "test.xml")

        params = [
            ("output_xml_assemblytree", output_path),
            ("export_exchange_ids", "1"),
        ]

        self._test_conversion(input_basepath, params, output_path)


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
