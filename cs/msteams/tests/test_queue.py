#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 2023 CONTACT Software GmbH.
# All rights reserved.
# https://www.contact-software.com/

"""
Test - mostly to make CI work
"""

import unittest

from cdb import rte
from cdb.testcase import RollbackTestCase
from cs.msteams import mq_worker_svc, queue


# Tests
class test_queue(unittest.TestCase):
    def setUp(self):
        self.old_queue_conf = rte.environ.get("CADDOK_MSTEAMS_QUEUE_DESC", "")
        rte.environ["CADDOK_MSTEAMS_QUEUE_DESC"] = "$CADDOK_BASE/etc/msteams_queue.json"

    def tearDown(self):
        rte.environ["CADDOK_MSTEAMS_QUEUE_DESC"] = self.old_queue_conf

    def test_ConnectionInfo(self):
        coninfo = queue.ConnectionInfo()
        con_params = coninfo.get("ConnectionParameters")
        self.assertTrue(isinstance(con_params, dict))
        self.assertEqual(con_params.get("host"), "localhost")


class test_service(RollbackTestCase):
    def setUp(self):
        self.old_queue_conf = rte.environ.get("CADDOK_MSTEAMS_QUEUE_DESC", "")
        rte.environ["CADDOK_MSTEAMS_QUEUE_DESC"] = "$CADDOK_BASE/etc/msteams_queue.json"

    def tearDown(self):
        rte.environ["CADDOK_MSTEAMS_QUEUE_DESC"] = self.old_queue_conf

    def test_ServiceInstall(self):
        # More a less a smoke test if the include is ok to please sonar
        mq_worker_svc.MQWorkerService.install(
            "cs.msteams.mq_worker_svc.MQWorkerService", "localhost", "default"
        )


# Allow running this testfile directly
if __name__ == "__main__":
    unittest.main()
