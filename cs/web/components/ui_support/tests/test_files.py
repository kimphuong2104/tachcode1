#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import
__revision__ = "$Id$"

import datetime
import hashlib
import os
import unittest
from webtest import TestApp as Client

from cdb.objects.cdb_file import CDB_File
from cdb import testcase
from cs.platform.web.root import Root


_FILENAME = os.path.join(os.path.dirname(__file__), 'a_test_file.txt')


class TestWithFiles(testcase.RollbackTestCase):

    # we want to see the complete JSON diff, not truncated
    maxDiff = None

    def setUp(self):
        try:
            from cs.restgenericfixture import Complex
        except ImportError:
            raise unittest.SkipTest("this test needs cs.restgenericfixture")
        super(TestWithFiles, self).setUp()
        self.obj = Complex.Create(attr_int=4711, attr_c10='with files')
        self.file_obj = CDB_File.NewFromFile(self.obj.cdb_object_id, _FILENAME, True)
        self.blob_ids = [self.file_obj.cdbf_blob_id]
        stat_data = os.stat(_FILENAME)
        self.fdate = datetime.datetime.utcfromtimestamp(stat_data.st_mtime)
        self.fsize = stat_data.st_size
        m = hashlib.md5()
        with open(_FILENAME, 'rb') as f:
            m.update(f.read())
        self.filehash = m.hexdigest()

    def tearDown(self):
        super(TestWithFiles, self).tearDown()
        for blob_id in self.blob_ids:
            CDB_File._deleteFromBlobStore(blob_id)

    def test_read_file_content(self):
        app = Root()
        c = Client(app)
        response = c.get(u'http://localhost/api/v1/collection/restcomplex/%s/files/%s'
                         % (self.obj.attr_int, self.file_obj.cdb_object_id),
                         headers={'Accept': 'application/json;cdb-meta-only=1'})
        json_data = response.json
        self.assertIsNotNone(json_data['system:ui_link'])

        response = c.get(json_data['system:ui_link'], headers={'Accept': '*/*'})
        self.assertEqual(response.content_type, "text/plain")
        self.assertEqual(response.content_length, self.fsize)
        m = hashlib.md5()
        m.update(response.body)
        self.assertEqual(m.hexdigest(), self.filehash)
