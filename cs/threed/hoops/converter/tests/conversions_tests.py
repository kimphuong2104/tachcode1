#!/usr/bin/env powerscript
# -*- python -*- coding: UTF-8 -*-
#
# Copyright (C) 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Tests for the conversions of cad documents to scz
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

# Exported objects
__all__ = ['Converter']

import os
import unittest

from cdb import acs
from cdb import cdbuuid
from cdb import sqlapi
from cdb import testcase

from cs.documents import Document

from cs.threed.hoops.converter.hoops import Converter
from cs.threed.hoops.converter.utils import get_job_params
from cs.threed.hoops.converter.tests import common

from cs.threed.hoops.converter import create_threed_batch_job, create_dependent_jobs, get_reconversion_docs, _release_order_with_params

class TestConversions(testcase.RollbackTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestConversions, cls).setUpClass()

    def create_document(self):
        self.main_doc = common.generateCADDocument(
            common.generateItem(),
            presets_custom={"erzeug_system": "SolidWorks:asm"}
        )
        self.create_file(self.main_doc, "sw_cm_assembly.sldasm", "SolidWorks:asm")
        self.create_file(self.main_doc, "sw_cm_part.sldprt", "SolidWorks:part", primary=False)

    def create_file(self, doc, filename, filetype, primary=True):
        filepath = os.path.join(common.files_dir, filename)

        return common.generateFile(
            doc, filepath, filetype,
            auto_disable_genonlycad=True,
            primary=primary
        )

    def create_documents_with_conversion_results(self, num=1, filetype="Hoops:SCZ"):

        doc_cols = ["cdb_object_id", "z_nummer", "z_index"]
        file_cols = ["cdb_object_id", "cdbf_object_id", "cdbf_type", "cdbf_derived_from"]

        docs = []
        for x in range(num):

            doc_oid = cdbuuid.create_uuid()
            doc_vals = [doc_oid, str(cdbuuid.create_uuid()[:19]), ""]

            sqlapi.SQLinsert("INTO zeichnung ({cols}) VALUES ('{vals}')".format(cols=", ".join(doc_cols), vals="', '".join(doc_vals)))

            doc = Document.ByKeys(cdb_object_id=doc_oid)
            primary_file = self.create_file(doc, "sw_cm_part.sldprt", "SolidWorks:part")

            docs.append(doc)

            if (x % 4) == 0:

                # wrong filetype + right derived
                if(x % 3) == 0:
                    file_vals = [cdbuuid.create_uuid(), doc_oid, "OTHER_FILETYPE", primary_file.cdb_object_id]
                    sqlapi.SQLinsert("INTO cdb_file ({cols}) VALUES ('{vals}')".format(cols=", ".join(file_cols), vals="', '".join(file_vals)))

                # right filetype + wrong derived
                elif(x % 3) == 1:
                    file_vals = [cdbuuid.create_uuid(), doc_oid, filetype, cdbuuid.create_uuid()]
                    sqlapi.SQLinsert("INTO cdb_file ({cols}) VALUES ('{vals}')".format(cols=", ".join(file_cols), vals="', '".join(file_vals)))

                # else no file at all

            # right filetype + right derived
            else:
                file_vals = [cdbuuid.create_uuid(), doc_oid, filetype, primary_file.cdb_object_id]
                sqlapi.SQLinsert("INTO cdb_file ({cols}) VALUES ('{vals}')".format(cols=", ".join(file_cols), vals="', '".join(file_vals)))

        return docs

    def create_dummy_conversion_configs(self):
        class Container(object):
            pass

        config = Container()
        config.ft_name = "HOOPS:SCZ"
        config.auto_convert = True
        configs = [config]
        return configs

    def test_create_threed_batch_job_with_filetypes(self):
        self.create_document()
        self.target = "threed_viewing"
        self.filetypes = ["Hoops:SCZ", "PNG", "Acrobat"]

        job = create_threed_batch_job([self.main_doc], target=self.target, filetypes=self.filetypes)
        self.assertIsNotNone(job, "No job was created")

        expected_params = {
            "doc_ids": [self.main_doc.cdb_object_id],
            "target": self.target,
            "reconvert_dependencies": False,
            "filetypes": self.filetypes
        }
        got_params = get_job_params(job.id())

        self.assertDictEqual(expected_params, got_params, "Job parameters are different than expected")


    def test_create_dependent_jobs(self):

        self.create_document()
        self.target = "threed_viewing"
        self.configs = self.create_dummy_conversion_configs()

        job = create_threed_batch_job([self.main_doc], target=self.target)
        self.assertIsNotNone(job, "No job was created")

        job_params = get_job_params(job.id())
        self.assertIsNotNone(job_params, "Missing job parameters")

        ret_code = create_dependent_jobs(job, self.configs)
        self.assertEqual(ret_code, 0, "Something went wrong")


    def test_get_reconversion_docs(self):

        self.target_filetype = "Hoops:SCZ"
        input_num = 50
        docs = self.create_documents_with_conversion_results(input_num, self.target_filetype)

        got = len(get_reconversion_docs(docs, [self.target_filetype]))
        expected = (input_num * 3) // 4

        self.assertEqual(got, expected, "expected %d reconversion docs but got %d" % (expected, got))


    def test_release_order_with_params(self):
        self.create_document()

        order = acs.Order(self.main_doc.cdb_object_id, "threed_viewing", self.main_doc.erzeug_system)
        expected_params = {"filetypes": ["PRC", "STEP"]}

        job = _release_order_with_params(order, expected_params)

        got_params = get_job_params(job.id())

        self.assertDictEqual(expected_params, got_params, "Job parameters are different than expected")


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
