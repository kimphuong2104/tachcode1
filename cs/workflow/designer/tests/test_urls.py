#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

from cdb import testcase
from cs.workflow.designer import urls
from cs.workflow.processes import Process
from cs.workflow.tasks import FilterParameter


def setup_module():
    testcase.run_level_setup()


class URLTestCase(testcase.RollbackTestCase):
    def test_quote(self):
        self.assertEqual(
            urls.quote("https://test?param=value&param2={'a b c'}"),
            "https%3A//test?param=value%26param2=%7B%27a%20b%20c%27%7D")
        self.assertEqual(
            urls.quote('/test?param=value&param2={"a b": "c"}'),
            "/test?param=value%26param2=%7B%22a%20b%22%3A%20%22c%22%7D")

        with self.assertRaises(TypeError):
            urls.quote(None)

    def test_get_protocol_url(self):
        baseUrl = "cdb:///byname/classname/cdbwf_protocol/CDB_Search/batch"
        for pid in ["PID", None, 1]:
            self.assertEqual(
                urls.get_protocol_url(pid),
                baseUrl if pid is None else baseUrl + "?cdbwf_protocol.cdb_process_id={}".format(pid)
            )

    def test_get_object_url(self):
        for obj in [None, 1, "TEST"]:
            with self.assertRaises(AttributeError):
                urls.get_object_url(obj)

        # non-persistent object (e.g. missing primary key)
        self.assertEqual(
            urls.get_object_url(Process()),
            "/info/workflow/None"
        )

        # REST API-activated object
        process = Process.Create(cdb_process_id="TEST")
        self.assertEqual(
            urls.get_object_url(process),
            "/info/workflow/TEST"
        )

        # non-REST API-activated object
        param = FilterParameter.Create(cdb_process_id="TEST")
        self.assertEqual(urls.get_object_url(param), None)
