#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

import unittest

import mock
import pytest
from cdb import sqlapi, testcase
from cdb.objects import ByID
from cs.baselining.support import BaselineTools

from cs.pcs.timeschedule.web.models import baseline_model


@pytest.mark.integration
class BaselineModel(testcase.RollbackTestCase):
    def __get_baselines(self, *project_uuids):
        request = mock.Mock(
            json={
                "projectOIDs": list(project_uuids),
            }
        )
        baseline_model.BaselineModel().get_baselines(request)
        return request

    def test_get_baselines_no_project(self):
        request = self.__get_baselines("this is not a project UUID")
        self.assertEqual(request.view.call_count, 0)

    def test_get_baselines_no_baseline(self):
        sqlapi.SQLdelete(
            "FROM cdbpcs_project"
            " WHERE cdb_project_id='Ptest.msp.big'"
            " AND ce_baseline_id > ''"
        )
        # Ptest.msp.big
        request = self.__get_baselines("b5235905-94e0-11e9-833d-d0577b2793bc")
        self.assertEqual(request.view.call_count, 0)

    def test_get_baselines(self):
        # Ptest.baselining
        project_uuid = "2b8ffb08-1258-11ed-8ea1-8cc681401f4f"
        BaselineTools.create_baseline(
            obj=ByID(project_uuid),
            name="BL 2",
        )
        request = self.__get_baselines(project_uuid)
        self.assertEqual(request.view.call_count, 2)

        baselines = [
            {
                "ce_baselined_object_id": call[1][0].ce_baselined_object_id,
                "ce_baseline_name": call[1][0].ce_baseline_name,
            }
            for call in request.view.mock_calls
        ]

        self.assertEqual(
            baselines,
            [
                {
                    "ce_baselined_object_id": project_uuid,
                    "ce_baseline_name": "BL 2",
                },
                {
                    "ce_baselined_object_id": project_uuid,
                    "ce_baseline_name": "BL 1",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
