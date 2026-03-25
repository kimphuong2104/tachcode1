#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import subprocess  # nosec

import mock

from cdb import auth, sqlapi, testcase
from cdb.rte import runtime_tool
from cs.taskmanager.userdata import ReadStatus, Tags
from cs.taskmanager.web.tests.integration import load_json, make_request


class Utility(testcase.RollbackTestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super(Utility, cls).setUpClass()
        # reset user settings, read status and tags (WARNING: will not be rolled back)
        sqlapi.SQLdelete(
            "FROM cdb_usr_setting "
            "WHERE setting_id='cs.taskmanager' "
            "AND personalnummer='{}'".format(auth.persno)
        )
        ReadStatus.KeywordQuery(persno=auth.persno).Delete()
        Tags.KeywordQuery(persno=auth.persno).Delete()

    def validate_request_response(self, file_name, req_type):
        json = load_json(file_name)
        request = json["request"]
        response = make_request(request["url"], request["params"], req_type)
        self.assertDictEqual(
            json["response"], response.json[0] if file_name == "data" else response.json
        )

    def test_settings(self):
        self.validate_request_response("settings", "get")

    def _request_data(self):
        # log in "faraway" so substituted tasks are found
        subprocess.check_call(  # nosec
            [
                runtime_tool("powerscript"),
                "--user",
                "faraway",
                "-c",
                "pass",
            ]
        )
        sqlapi.SQLupdate(
            "cs_tasks_test_olc SET cdb_mdate = {}".format(
                sqlapi.SQLdate_literal("01.01.2022 10:11:12")
            )
        )
        json = load_json("data")
        request = json["request"]
        response = make_request(request["url"], request["params"], "post_json")
        return response.json[0]

    def test_data(self):
        data = self._request_data()
        json = load_json("data")
        self.assertDictEqual(json["response"], data)

    @mock.patch("cs.taskmanager.web.models.data.get_max_tasks", return_value=3)
    def test_data_limited(self, _):
        data = self._request_data()
        self.assertEqual(len(data["objects"]), 3)
        self.assertEqual(data["title"], "Begrenzt auf 3 Suchergebnisse")

    def test_webdata(self):
        self.validate_request_response("webdata", "post_json")
