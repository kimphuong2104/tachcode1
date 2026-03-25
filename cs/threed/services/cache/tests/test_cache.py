# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
Module test_cache

Test module for cs.threed.hoops.server.StreamCache
"""

import mock
import unittest

from cdb.objects.cdb_file import CDB_File

from cs.vp.cad import Model

from cs.threed.services import cache

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


class TestInstanceConfig(unittest.TestCase):
    def test_no_config_file(self):
        """If the config file doesn't exist, return an empty dictionary"""
        with mock.patch('os.path.exists') as os_path_exists:
            os_path_exists.return_value = False
            got = cache.get_instance_config()
            self.assertEqual(got, {}, "got non empty object %s" % got)

    def test_no_config(self):
        """If the config file exists but doesn't contain any configuration, return an empty dictionary"""
        with mock.patch('os.path.exists') as os_path_exists:
            with mock.patch('io.open'):
                with mock.patch('json.load') as json_load:
                    os_path_exists.return_value = True
                    json_load.return_value = {"not-interesting": "configuration"}

                    got = cache.get_instance_config()
                    self.assertEqual(got, {}, "got non empty object %s" % got)

    def test_invalid_json(self):
        """If the config file exists but contains invalid json, return an empty dictionary"""
        with mock.patch('os.path.exists') as os_path_exists:
            with mock.patch('io.open'):
                with mock.patch('json.load') as json_load:
                    os_path_exists.return_value = True
                    json_load.side_effect = ValueError("No JSON object could be decoded")

                    got = cache.get_instance_config()
                    self.assertEqual(got, {}, "got non empty object %s" % got)

    def test_valid_config(self):
        """If the config file exists and is valid, return its content"""
        config = {
            "stream_cache": {
                "--sc_export_attributes": "false"
            }
        }
        with mock.patch('os.path.exists') as os_path_exists:
            with mock.patch('io.open'):
                with mock.patch('json.load') as json_load:
                    os_path_exists.return_value = True
                    json_load.return_value = config

                    got = cache.get_instance_config()
                    self.assertEqual(
                        got, config["stream_cache"],
                        "got invalid configuration %s" % got
                    )


class TestStreamCache(unittest.TestCase):
    def setUp(self):
        self.sc = cache.StreamCache()

        self.file = CDB_File()
        self.file.checkout_file = mock.MagicMock()

        self.model = Model()
        self.model.getPrimaryFile = mock.MagicMock(return_value=CDB_File())
        self.model.get_scz_file = mock.MagicMock(return_value=self.file)

        self.sc._get_model = mock.MagicMock(return_value=self.model)
        self.sc._get_cache_name = mock.MagicMock(return_value='cache_name')
        self.sc.get_path_to_cache_file = mock.MagicMock(return_value='cache_file_path')

    def test_get_model_value_error(self):
        """ _get_model raises a ValueError if no model can be found """
        with self.assertRaises(ValueError):
            cache.StreamCache._get_model('some_nonexisting_id')

    def test_cache_state_no_scz(self):
        """ cache_state returns cache miss if no scz file can be found """
        self.model.get_scz_file = mock.MagicMock(return_value=None)

        cache_miss, _ = self.sc.cache_state('some_document_id')
        self.assertTrue(cache_miss)

    def test_cache_state_scz_in_blobstore(self):
        """ cache_state return cache miss if the scz file exists in the blobstore, but not on the file system"""
        with mock.patch('os.path.isfile') as os_path_isfile:
            os_path_isfile.return_value = False

            cache_miss, _ = self.sc.cache_state('some_document_id')
            self.assertTrue(cache_miss)

    def test_cache_state_scz_on_filesystem(self):
        """ cache_state return cache hit if the scz file exists on the file system"""
        self.sc._get_scz_file = mock.MagicMock(return_value=self.file)

        with mock.patch('os.path.isfile') as os_path_isfile:
            os_path_isfile.return_value = True

            cache_miss, cache_name = self.sc.cache_state('some_document_id')
            self.assertFalse(cache_miss)
            self.assertEqual(cache_name, 'cache_name')

    def test_register_model_model_converted(self):
        """ register_model checks out the SCZ file if the model is converted"""
        self.sc._get_scz_file = mock.MagicMock(return_value=self.file)
        cache_name = self.sc.register_model('some_document_id')
        self.assertEqual(cache_name, 'cache_name')
        self.file.checkout_file.assert_called()
