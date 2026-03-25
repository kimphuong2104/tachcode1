#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Test Module acs

"""
__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import os
import shutil

from cdb import sqlapi
from cdb import constants
from cdb import testcase
from cdb.objects import operations

from cs.threed.hoops.utils import SQL_MAX_CHUNK_SIZE
from cs.threed.hoops.converter import JSON_FILE_FORMAT, SCZ_FILE_FORMAT, XML_FILE_FORMAT
from cs.threed.hoops.converter.acs import get_identical_jobs
from cs.threed.hoops.converter.configurations import get_configurations
from cs.threed.hoops.converter.tests import common, DisableFileTypeGenOnlyCad

# Tests
class AcsJobTests(testcase.RollbackTestCase):
    "Unit tests for conversion jobs"

    def setUp(self):
        self.src_fname = None
        self.to_delete = []

    def tearDown(self):
        if self.src_fname:
            shutil.rmtree(os.path.join(os.path.dirname(self.src_fname)))
            self.src_fname = None

        with DisableFileTypeGenOnlyCad():
            for obj in self.to_delete:
                operations.operation(
                    constants.kOperationDelete,
                    obj
                )

    def create_document(self, fname=None, ftype=None, addtl_files=1):
        self.main_doc = common.generateCADDocument(
            common.generateItem()
        )

        if fname and ftype:
            self.create_file(self.main_doc, fname, ftype)
        else:
            self.create_file(self.main_doc, "sw_cm_assembly.sldasm", "SolidWorks:asm")

            for _ in range(addtl_files):
                self.create_file(self.main_doc, "sw_cm_part.sldprt", "SolidWorks:part", primary=False)

        self.to_delete.append(self.main_doc)

    def create_file(self, doc, filename, filetype, primary=True):
        filepath = os.path.join(common.files_dir, filename)

        common.generateFile(
            doc, filepath, filetype,
            auto_disable_genonlycad=True,
            primary=primary
        )

    def create_job(self):
        from cdb.acs.acstools import cli_testplg
        self.job = cli_testplg("hoops", self.main_doc.z_nummer, self.main_doc.z_index, "threed_viewing")

    @testcase.skip_dbms(sqlapi.DBMS_MSSQL)
    def test_get_identical_jobs(self):
        """the get_identical_jobs method tries to get the number of identical jobs"""
        self.create_document(addtl_files=SQL_MAX_CHUNK_SIZE)
        self.create_job()
        self.assertTrue(type(get_identical_jobs(self.job, self.main_doc.Files)) is list, "something went wrong")

    def test_acs_scz_conversion(self):
        """the conversion job creates the files for the conversion results"""
        self.create_document()
        self.create_job()

        # this should only work for the default auto_convert formats
        expected_ftypes = [JSON_FILE_FORMAT, SCZ_FILE_FORMAT, XML_FILE_FORMAT]
        all_auto_convert_ftypes = [conf.ft_name for conf in get_configurations() if conf.auto_convert]
        self.assertIn(SCZ_FILE_FORMAT, all_auto_convert_ftypes)

        for ftype in expected_ftypes:

            res_file = None
            for f in self.main_doc.Files:
                if f.cdbf_type == ftype:
                    res_file = f
                    break

            self.assertTrue(res_file is not None, "The %s File was not created" % ftype)

    def test_acs_scz_conversion_with_existing_results(self):
        """the conversion job removes existing files"""
        self.create_document()
        self.create_job()
        self.create_job()

        # this should only work for the default auto_convert formats
        expected_ftypes = [JSON_FILE_FORMAT, SCZ_FILE_FORMAT, XML_FILE_FORMAT]
        all_auto_convert_ftypes = [conf.ft_name for conf in get_configurations() if conf.auto_convert]
        self.assertIn(SCZ_FILE_FORMAT, all_auto_convert_ftypes)

        for ftype in expected_ftypes:
            files = 0
            for f in self.main_doc.Files:
                if f.cdbf_type == ftype:
                    files = files + 1

            self.assertTrue(files == 1, "Expected exactly 1 conversion result for %s, but found %d" % (ftype, files))

    def test_acs_scz_conversion_unicode_filename(self):
        """the conversion job creates the files for the conversion results with unicode filename"""

        self.create_document("ínventör-прт-狼.ipt", "inventor:prt")
        self.create_job()

        expected_ftypes = [JSON_FILE_FORMAT, SCZ_FILE_FORMAT, XML_FILE_FORMAT]
        for ftype in expected_ftypes:

            res_file = None
            for f in self.main_doc.Files:
                if f.cdbf_type == ftype:
                    res_file = f
                    break

            self.assertTrue(res_file is not None, "The %s File was not created" % ftype)
