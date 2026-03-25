# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

import mock

from cdb import testcase
from cdb.objects.cdb_file import CDB_File

from cs.vp.cad import Model

from cs.threed.hoops.converter import SCZ_FILE_FORMAT


class TestDocumentExtensions(testcase.PlatformTestCase):
    def setUp(self):
        super(TestDocumentExtensions, self).setUp()

        self.model = Model()

    def test_get_scz_file_returns_none_if_no_files(self):
        """ If the model does not contain any files, get_scz_file returns None """
        with mock.patch.object(Model, 'Files', new_callable=mock.PropertyMock) as mocked_files:
            mocked_files.return_value = []
            self.assertIsNone(self.model.get_scz_file())

    def test_get_scz_file_returns_none_if_no_primary_files(self):
        """ If the model contains no primary files, get_scz_file returns None """
        with mock.patch.object(Model, 'Files', new_callable=mock.PropertyMock) as mocked_files:
            mocked_files.return_value = [CDB_File(), CDB_File()]
            self.assertIsNone(self.model.get_scz_file())

    def test_get_scz_file_returns_derived_from_primary(self):
        """ get_scz_file returns a SCZ file that is derived from the primary file, if it exists """
        with mock.patch.object(Model, 'Files', new_callable=mock.PropertyMock) as mocked_files:
            f1 = CDB_File()
            f2 = CDB_File()
            f1.cdbf_primary = '1'
            f1.cdb_object_id = 'primary_object_id'
            f2.cdbf_derived_from = 'primary_object_id'
            f2.cdbf_type = SCZ_FILE_FORMAT

            mocked_files.return_value = [f1, f2]
            self.assertEqual(self.model.get_scz_file(), f2)


