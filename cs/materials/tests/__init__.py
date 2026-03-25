# flake8: noqa

import time
import unittest

from cdb import testcase


class MaterialsTestCase(testcase.RollbackTestCase):
    @classmethod
    def ensure_running_classification_core(cls, timeout=120):
        from cs.classification import solr

        testcase.require_service("cdb.uberserver.services.index.IndexService")
        solr_connection = solr._get_solr_connection()  # pylint: disable=W0212
        t = time.time()
        while t + timeout > time.time():
            try:
                testcase.without_error_logging(solr_connection.get_fields)()
                break
            except Exception:  # pylint: disable=W0703
                time.sleep(1)
        else:
            raise IOError("Solr did not start up within %d seconds" % timeout)

    @classmethod
    def setUpClass(cls):
        super(MaterialsTestCase, cls).setUpClass()
        cls.ensure_running_classification_core()

    def setUp(self):
        def fixture_installed():
            try:
                import cs.materialstests  # pylint: disable=W0611

                return True
            except ImportError:
                return False

        if not fixture_installed():
            raise unittest.SkipTest("Fixture package cs.materialstests not installed.")
        super(MaterialsTestCase, self).setUp()
