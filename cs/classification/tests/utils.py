# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

"""
Module test_validation

This is the documentation for the test_validation module.
"""

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import datetime
import logging
import os
import tempfile
import time
import unittest

from cdb.objects.operations import operation
from cdb import constants
from cs import documents

from cdb import CADDOK, testcase, cdbuuid
from cdb.platform.uberserver import Services

from cs.classification.scripts.solr_resync import resync_schema, reindex_objects
from cs.classification.scripts.solr_update_managed_schema import update_xml


LOG = logging.getLogger(__name__)
OBJ_REF_VALUE = cdbuuid.create_uuid()
SOLR_RESYNC = True


class ClassificationTestCase(testcase.RollbackTestCase):

    @classmethod
    def ensure_running_classification_core(cls, timeout=120):
        from cs.classification import solr
        solr_connection = solr._get_solr_connection()
        t = time.time()
        while t + timeout > time.time():
            try:
                testcase.without_error_logging(solr_connection.get_fields)()
                break
            except Exception: # pylint: disable=W0703
                time.sleep(1)
        else:
            raise IOError("Solr did not start up within %d seconds" % timeout)

    @classmethod
    def setUpClass(cls):
        super(ClassificationTestCase, cls).setUpClass()

        testcase.require_service("cdb.uberserver.services.index.IndexService")
        cls.ensure_running_classification_core()

        global SOLR_RESYNC
        if SOLR_RESYNC and not os.getenv("DONT_RESYNC_SOLR"):
            resync_schema(LOG.info, False)
            reindex_objects(LOG.info, False)
            SOLR_RESYNC = False
            return
            search_index_path = os.path.abspath(os.path.join(CADDOK.BASE, 'storage', 'index', 'search'))
            indexService = Services.ByKeys(svcname='cdb.uberserver.services.index.IndexService')
            if indexService and indexService.get_option('--workdir'):
                search_index_path = indexService.get_option('--workdir')
            if os.path.isdir(search_index_path):
                managed_schema_file = os.path.join(search_index_path, 'classification', 'conf', 'managed-schema')
                if os.path.isfile(managed_schema_file):
                    _, output_file = tempfile.mkstemp()
                    update_xml(managed_schema_file, output_file)

    def setUp(self):
        def fixture_installed():
            try:
                import cs.classificationtests
                return True
            except ImportError:
                return False
        if not fixture_installed():
            raise unittest.SkipTest("Fixture package cs.classificationtests not installed")
        super(ClassificationTestCase, self).setUp()

    def create_document(self, title="Test Doc"):
        doc = operation(
            constants.kOperationNew,
            documents.Document,
            titel=title,
            z_categ1="142",
            z_categ2="153"
        )
        assert doc, 'document to classify could not be created!'
        return doc

    def check_property_values(self, properties):
        for prop_code in list(properties.keys()):
            prop_value = properties[prop_code][0]
            prop_type = prop_value["property_type"]
            if "block" == prop_type:
                self.check_property_values(prop_value["value"]["child_props"])
            elif "float" == prop_type:
                self.assertAlmostEqual(123.456, prop_value["value"]["float_value"])
            elif "float_range" == prop_type:
                self.assertAlmostEqual(123.456, prop_value["value"]["min"]["float_value"])
                self.assertAlmostEqual(456.789, prop_value["value"]["max"]["float_value"])
            elif "boolean" == prop_type:
                self.assertEqual(True, prop_value["value"])
            elif "datetime" == prop_type:
                self.assertEqual(datetime.datetime(2002, 3, 11, 0, 0), prop_value["value"])
            elif "integer" == prop_type:
                self.assertEqual(123, prop_value["value"])
            elif "multilang" == prop_type:
                self.assertEqual(prop_code + "_de", prop_value["value"]["de"]["text_value"])
                self.assertEqual(prop_code + "_en", prop_value["value"]["en"]["text_value"])
            elif "objectref" == prop_type:
                self.assertEqual(OBJ_REF_VALUE, prop_value["value"])
            elif "text" == prop_type:
                self.assertEqual(prop_code, prop_value["value"])

    def set_property_values(self, properties):
        for prop_code in list(properties.keys()):
            prop_value = properties[prop_code][0]
            prop_type = prop_value["property_type"]
            if "block" == prop_type:
                self.set_property_values(prop_value["value"]["child_props"])
            elif "float" == prop_type:
                prop_value["value"]["float_value"] = 123.456
            elif "float_range" == prop_type:
                prop_value["value"]["min"]["float_value"] = 123.456
                prop_value["value"]["max"]["float_value"] = 456.789
            elif "boolean" == prop_type:
                prop_value["value"] = True
            elif "datetime" == prop_type:
                prop_value["value"] = datetime.date(2002, 3, 11)
            elif "integer" == prop_type:
                prop_value["value"] = 123
            elif "multilang" == prop_type:
                prop_value["value"]["de"]["text_value"] = prop_code + "_de"
                prop_value["value"]["en"]["text_value"] = prop_code + "_en"
            elif "objectref" == prop_type:
                prop_value["value"] = OBJ_REF_VALUE
            elif "text" == prop_type:
                prop_value["value"] = prop_code



class ClassificationNoRollbackTestCase(testcase.PlatformTestCase):
    pass
