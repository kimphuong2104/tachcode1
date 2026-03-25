#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tests for the converter tool
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = ['Converter']

import io
import os
import shutil
import sys
import tempfile
import unittest
from collections import namedtuple

from cs.threed.hoops.converter.csconvert import Converter
from cdb import testcase
from cs.documents import Document


DocumentMock = namedtuple("DocumentMock", "titel z_nummer z_index")
DocumentMock.GetFieldByName = Document.GetFieldByName


class TestConverter(testcase.PlatformTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestConverter, cls).setUpClass()
        module_dir = os.path.dirname(
            __file__)
        cls.files_dir = os.path.join(module_dir, "..", "..", "..", "..", "..",
                                     "tests", "accepttests", "files")

    def setUp(self):
        self.wsp_dir = tempfile.mkdtemp(prefix="tmp_test_")
        self.converter = Converter(wsp_path=self.wsp_dir, service_mode=False)

    def tearDown(self):
        if self.wsp_dir:
            shutil.rmtree(self.wsp_dir)
            self.wsp_dir = None
        self.converter = None

    def test_check_health(self):
        Converter.test()

    @unittest.skipIf(sys.platform != "win32", "There is a bug @ TS3D")
    def test_conversion_jt(self):
        filename = "CatiaV5-Part.CATPart"
        self.converter.new_conversion(
            os.path.join(self.files_dir, filename))
        self.converter.add_task("jt", {
            "output": "test.jt"
        })
        self.converter.run()
        result_path = os.path.join(self.wsp_dir, "test.jt")
        self.assertTrue(os.path.exists(result_path), "Conversion result "
                                                     "should exist")
        statinfo = os.stat(result_path)
        self.assertGreater(statinfo.st_size, 0, "Result should not be empty")

    def test_conversion_step(self):
        filename = "CatiaV5-Part.CATPart"
        self.converter.new_conversion(
            os.path.join(self.files_dir, filename))
        self.converter.add_task("step", {
            "output": "test.step"
        })
        self.converter.run()
        result_path = os.path.join(self.wsp_dir, "test.step")
        self.assertTrue(os.path.exists(result_path), "Conversion result "
                                                     "should exist")
        statinfo = os.stat(result_path)
        self.assertGreater(statinfo.st_size, 0, "Result should not be empty")

    def test_conversion_pdf(self):
        filename = "CatiaV5-Part.CATPart"
        self.converter.models = [DocumentMock(titel="Fahrersitz",
                                              z_nummer="900066-1",
                                              z_index="a")]
        mod = sys.modules.get("cs.threed.hoops.converter")
        self.assertTrue(mod, "Should find converter module")
        tmpl_path = os.path.join(os.path.dirname(mod.__file__),
                                 "cdb_template.pdf")
        self.converter.new_conversion(
            os.path.join(self.files_dir, filename))
        self.converter.add_task("pdf", {
            "output": "test.pdf",
            "template_file": tmpl_path,
            "db_attribute_map": {
                "title": "titel",
                "number": "z_nummer",
                "index": "z_index"
            },
            "cad_attribute_map": {
            },
        })
        self.converter.run()
        result_path = os.path.join(self.wsp_dir, "test.pdf")
        self.assertTrue(os.path.exists(result_path), "Conversion result "
                                                     "should exist")
        statinfo = os.stat(result_path)
        self.assertGreater(statinfo.st_size, 0, "Result should not be empty")

    def test_conversion_prc(self):
        filename = "CatiaV5-Part.CATPart"
        self.converter.new_conversion(
            os.path.join(self.files_dir, filename))
        self.converter.add_task("prc", {
            "output": "test.prc"
        })
        self.converter.run()
        result_path = os.path.join(self.wsp_dir, "test.prc")
        self.assertTrue(os.path.exists(result_path), "Conversion result "
                                                     "should exist")
        statinfo = os.stat(result_path)
        self.assertGreater(statinfo.st_size, 0, "Result should not be empty")

    def test_conversion_prc_basename(self):
        from cs.threed.hoops.converter.acs import _make_substitutions
        filename = "CatiaV5-Part.CATPart"
        src_fname = os.path.join(self.files_dir, filename)

        # use output dir as path for src_basename to make this work
        src_basename = os.path.splitext(os.path.join(self.wsp_dir, filename))[0]

        self.converter.new_conversion(
            src_fname, substitutions=_make_substitutions(self.wsp_dir, src_basename))
        self.converter.add_task("prc", {
            "output": "$(SRC_BASENAME).prc"
        })
        self.converter.run()
        result_path = os.path.join(self.wsp_dir, "CatiaV5-Part.prc")
        self.assertTrue(os.path.exists(result_path), "Conversion result "
                                                     "should exist")
        statinfo = os.stat(result_path)
        self.assertGreater(statinfo.st_size, 0, "Result should not be empty")

    def test_conversion_stl_basename_prefix(self):
        from cs.threed.hoops.converter.acs import _make_substitutions
        filename = "CatiaV5-Part.CATPart"
        src_fname = os.path.join(self.files_dir, filename)

        # use output dir as path for src_basename to make this work
        src_basename = os.path.splitext(os.path.join(self.wsp_dir, filename))[0]

        self.converter.new_conversion(
            src_fname, substitutions=_make_substitutions(self.wsp_dir, src_basename))
        self.converter.add_task("stl", {
            "output": "prefix_$(SRC_BASENAME).stl"
        })
        self.converter.run()
        result_path = os.path.join(self.wsp_dir, "prefix_CatiaV5-Part.stl")
        self.assertTrue(os.path.exists(result_path), "Conversion result "
                                                     "should exist")
        statinfo = os.stat(result_path)
        self.assertGreater(statinfo.st_size, 0, "Result should not be empty")

    def test_conversion_step_basename_suffix(self):
        from cs.threed.hoops.converter.acs import _make_substitutions
        filename = "CatiaV5-Part.CATPart"
        src_fname = os.path.join(self.files_dir, filename)

        # use output dir as path for src_basename to make this work
        src_basename = os.path.splitext(os.path.join(self.wsp_dir, filename))[0]

        self.converter.new_conversion(
            src_fname, substitutions=_make_substitutions(self.wsp_dir, src_basename))
        self.converter.add_task("step", {
            "output": "$(SRC_BASENAME)_suffix.step"
        })
        self.converter.run()
        result_path = os.path.join(self.wsp_dir, "CatiaV5-Part_suffix.step")
        self.assertTrue(os.path.exists(result_path), "Conversion result "
                                                     "should exist")
        statinfo = os.stat(result_path)
        self.assertGreater(statinfo.st_size, 0, "Result should not be empty")

    def test_conversion_stl(self):
        filename = "CatiaV5-Part.CATPart"
        self.converter.new_conversion(
            os.path.join(self.files_dir, filename))
        self.converter.add_task("stl", {
            "output": "test.stl"
        })
        self.converter.run()
        result_path = os.path.join(self.wsp_dir, "test.stl")
        self.assertTrue(os.path.exists(result_path), "Conversion result "
                                                     "should exist")
        statinfo = os.stat(result_path)
        self.assertGreater(statinfo.st_size, 0, "Result should not be empty")

    def test_conversion_jpg(self):
        filename = "CatiaV5-Part.CATPart"
        self.converter.new_conversion(
            os.path.join(self.files_dir, filename))
        self.converter.add_task("jpg", {
            "output": "test.jpg"
        })
        self.converter.run()
        result_path = os.path.join(self.wsp_dir, "test.jpg")
        self.assertTrue(os.path.exists(result_path), "Conversion result "
                                                     "should exist")
        statinfo = os.stat(result_path)
        self.assertGreater(statinfo.st_size, 0, "Result should not be empty")


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
