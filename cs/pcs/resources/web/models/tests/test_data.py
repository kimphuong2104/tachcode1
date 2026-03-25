#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import unittest

import mock
import pytest
from webob.exc import HTTPBadRequest, HTTPForbidden
from webtest import TestApp as Client

from cdb import testcase
from cdb.objects.operations import operation
from cdb.objects.org import Organization, Person
from cs.pcs.resources.web.models import data
from cs.platform.web.root import Root

RES_SCHEDULE = "36b2f02c-5e01-11ee-a775-9c2dcd48e5ae"
SUB_POOL_2 = "e091083a-2ab6-11ed-9d7f-207918bb3392"
RESOURCE_1_1 = "8a4c7525-2aba-11ed-9d7f-207918bb3392"
RESOURCE_2_1 = "c93063a7-2aba-11ed-9d7f-207918bb3392"
RESOURCE_2_2 = "d505c949-2aba-11ed-9d7f-207918bb3392"
DEMAND_6 = "93fb8716-2ac3-11ed-9d7f-207918bb3392"
DEMAND_7 = "93fb8718-2ac3-11ed-9d7f-207918bb3392"
ALLOC_20 = "37884af7-2ce6-11ed-9d7f-207918bb3392"
ALLOC_21 = "519e26d3-2ce6-11ed-9d7f-207918bb3392"
ALLOC_26 = "cb910d81-2ce6-11ed-9d7f-207918bb3392"


def http_post(url, payload):
    "sends POST request to mock http server"
    client = Client(Root())
    response = client.post_json(url, payload)
    return response.json


def setup_module():
    testcase.run_level_setup()


def _post_to_data_backend(from_quarter, from_year, expected_uuids):
    url = f"/internal/timeschedule/{RES_SCHEDULE}/data"
    payload = {
        "extraDataProps": {
            "timeFrameStartQuarter": from_quarter,
            "timeFrameStartYear": from_year,
            "timeFrameUntilQuarter": 1,
            "timeFrameUntilYear": 2023,
        },
    }
    response = http_post(url, payload)

    assert {x["cdb_object_id"] for x in response["objects"]} == expected_uuids
    assert set(response["grid"]["data"].keys()) == expected_uuids
    assert set(response["grid"]["day"].keys()) == expected_uuids
    assert set(response["grid"]["week"].keys()) == expected_uuids
    assert set(response["grid"]["month"].keys()) == expected_uuids
    assert set(response["grid"]["quarter"].keys()) == expected_uuids

    return response


@pytest.mark.cept
def test_data_outside_time_frame():
    """
    acceptance test:

    resource schedule backend is expected to filter out
    demands, allocations and pool assignments
    outside of the requested time frame
    """
    response = _post_to_data_backend(1, 2023, {
        SUB_POOL_2,
        RESOURCE_2_2,
        DEMAND_7,
        ALLOC_26,
    })

    assert [(row["rowNumber"], row["id"]) for row in response["rows"]] == [
        (0, f"{SUB_POOL_2}@{SUB_POOL_2}"),
        (1, f"{RESOURCE_2_2}@{SUB_POOL_2}"),
        (2, f"{DEMAND_7}@{RESOURCE_2_2}@{SUB_POOL_2}"),
        (3, f"{ALLOC_26}@{RESOURCE_2_2}@{SUB_POOL_2}"),
    ]
    assert response["treeNodes"] == [{
        "id": f"{SUB_POOL_2}@{SUB_POOL_2}",
        "rowNumber": 0,
        "expanded": True,
        "children": [
            {
                "id": f"{RESOURCE_2_2}@{SUB_POOL_2}",
                "rowNumber": 1,
                "expanded": True,
                "children": [
                    {
                        "id": f"{DEMAND_7}@{RESOURCE_2_2}@{SUB_POOL_2}",
                        "rowNumber": 2,
                        "expanded": True,
                        "children": [],
                    },
                    {
                        "id": f"{ALLOC_26}@{RESOURCE_2_2}@{SUB_POOL_2}",
                        "rowNumber": 3,
                        "expanded": True,
                        "children": [],
                    }
                ],
            },
        ],
    }]


@pytest.mark.cept
def test_data_in_time_frame():
    """
    acceptance test

    variant of test_data_outside_time_frame,
    this time including all data
    """
    response = _post_to_data_backend(1, 2022, {
        SUB_POOL_2,
        ALLOC_20,
        RESOURCE_1_1,
        RESOURCE_2_1,
        ALLOC_21,
        RESOURCE_2_2,
        DEMAND_6,
        DEMAND_7,
        ALLOC_26,
    })

    assert [(row["rowNumber"], row["id"]) for row in response["rows"]] == [
        (0, f'{SUB_POOL_2}@{SUB_POOL_2}'),
        (1, f'{ALLOC_20}@{SUB_POOL_2}@{SUB_POOL_2}'),
        (2, f'{RESOURCE_1_1}@{SUB_POOL_2}'),
        (3, f'{RESOURCE_2_1}@{SUB_POOL_2}'),
        (4, f'{ALLOC_21}@{RESOURCE_2_1}@{SUB_POOL_2}'),
        (5, f'{RESOURCE_2_2}@{SUB_POOL_2}'),
        (6, f'{DEMAND_6}@{RESOURCE_2_2}@{SUB_POOL_2}'),
        (7, f'{DEMAND_7}@{RESOURCE_2_2}@{SUB_POOL_2}'),
        (8, f'{ALLOC_26}@{RESOURCE_2_2}@{SUB_POOL_2}'),
    ]
    assert response["treeNodes"] == [{
        'id': f'{SUB_POOL_2}@{SUB_POOL_2}',
        'rowNumber': 0,
        'expanded': True,
        'children': [
            {
                'id': f'{ALLOC_20}@{SUB_POOL_2}@{SUB_POOL_2}',
                'rowNumber': 1,
                'expanded': True,
                'children': [],
            },
            {
                'id': f'{RESOURCE_1_1}@{SUB_POOL_2}',
                'rowNumber': 2,
                'expanded': True,
                'children': [],
            },
            {
                'id': f'{RESOURCE_2_1}@{SUB_POOL_2}',
                'rowNumber': 3,
                'expanded': True,
                'children': [
                    {
                        'id': f'{ALLOC_21}@{RESOURCE_2_1}@{SUB_POOL_2}',
                        'rowNumber': 4,
                        'expanded': True,
                        'children': [],
                    },
                ],
            },
            {
                'id': f'{RESOURCE_2_2}@{SUB_POOL_2}',
                'rowNumber': 5,
                'expanded': True,
                'children': [
                    {
                        'id': f'{DEMAND_6}@{RESOURCE_2_2}@{SUB_POOL_2}',
                        'rowNumber': 6,
                        'expanded': True,
                        'children': [],
                    },
                    {
                        'id': f'{DEMAND_7}@{RESOURCE_2_2}@{SUB_POOL_2}',
                        'rowNumber': 7,
                        'expanded': True,
                        'children': [],
                    },
                    {
                        'id': f'{ALLOC_26}@{RESOURCE_2_2}@{SUB_POOL_2}',
                        'rowNumber': 8,
                        'expanded': True,
                        'children': [],
                    },
                ],
            },
        ],
    }]


@pytest.mark.unit
class TestResourceScheduleDataModel(unittest.TestCase):
    maxDiff = None

    @mock.patch.object(data.fls, "get_license", return_value=False)
    @mock.patch.object(data.ResourceScheduleHelper, "get_schedule")
    def test_init_no_licence(self, get_schedule, get_license):
        with self.assertRaises(HTTPForbidden):
            data.ResourceScheduleDataModel("some ID")

        get_license.assert_called_once_with(data.RESOURCE_SCHEDULE_LICENCE)
        get_schedule.assert_not_called()

    @mock.patch.object(data.fls, "get_license")
    @mock.patch.object(data.ResourceScheduleHelper, "get_schedule", return_value=None)
    def test_init_no_schedule(self, get_schedule, get_license):
        with self.assertRaises(HTTPBadRequest):
            data.ResourceScheduleDataModel("some ID")

        get_license.assert_called_once_with(data.RESOURCE_SCHEDULE_LICENCE)
        get_schedule.assert_called_once_with("some ID")

    @mock.patch.object(data.fls, "get_license")
    @mock.patch.object(data.ResourceScheduleHelper, "get_schedule")
    def test_init_no_read_access(self, get_schedule, get_license):
        get_schedule.return_value.CheckAccess.return_value = False

        with self.assertRaises(HTTPForbidden):
            data.ResourceScheduleDataModel("some ID")

        get_license.assert_called_once_with(data.RESOURCE_SCHEDULE_LICENCE)
        get_schedule.assert_called_once_with("some ID")
        get_schedule.return_value.CheckAccess.assert_called_once_with("read")

    @mock.patch.object(data.fls, "get_license")
    @mock.patch.object(data.ResourceScheduleHelper, "get_schedule")
    def test_init_good(self, get_schedule, get_license):
        model = data.ResourceScheduleDataModel("some ID")

        get_license.assert_called_once_with(data.RESOURCE_SCHEDULE_LICENCE)
        get_schedule.assert_called_once_with("some ID")
        get_schedule.return_value.CheckAccess.assert_called_once_with("read")
        self.assertEqual(model.schedule, get_schedule.return_value)

    def _get_mock_objects(self):
        mock_objs = {}
        labels = []
        expected_result = {}
        for label, classname in [
            ("demand", "cdbpcs_prj_demand"),
            ("alloc", "cdbpcs_prj_alloc"),
            ("pool", "cdbpcs_resource_pool"),
            ("org", "cdb_organization"),
            ("person", "cdb_person"),
            ("pool_asgn", "cdbpcs_pool_assignment"),
        ]:
            obj_mock = mock.Mock(person_id="foo", classname=classname)
            mock_objs[label] = obj_mock
            labels.append(label)
            if label == "alloc":
                expected_result["alloc"] = {
                    "assignment_oid": obj_mock.assignment_oid,
                    "cdb_demand_id": obj_mock.cdb_demand_id,
                    "classname": classname,
                    "isAlloc": True,
                    "pool_oid": obj_mock.pool_oid,
                    "project_id": obj_mock.cdb_project_id,
                    "task_id": obj_mock.task_id,
                }
            elif label == "demand":
                expected_result["demand"] = {
                    "assignment_oid": obj_mock.assignment_oid,
                    "cdb_demand_id": obj_mock.cdb_demand_id,
                    "classname": classname,
                    "isDemand": True,
                    "pool_oid": obj_mock.pool_oid,
                    "project_id": obj_mock.cdb_project_id,
                    "task_id": obj_mock.task_id,
                }
            elif label == "org":
                expected_result["org"] = {
                    "cdb_object_id": obj_mock.cdb_object_id,
                    "classname": classname,
                }
            elif label == "person":
                expected_result["person"] = {
                    "cdb_object_id": obj_mock.cdb_object_id,
                    "classname": classname,
                }
            elif label == "pool":
                expected_result["pool"] = {
                    "cdb_object_id": obj_mock.cdb_object_id,
                    "classname": classname,
                    "parent_oid": obj_mock.parent_oid,
                }
            elif label == "pool_asgn":
                expected_result["pool_asgn"] = {
                    "classname": classname,
                    "person_id": obj_mock.person_id,
                    "pool_oid": obj_mock.pool_oid,
                }
        return mock_objs, labels, expected_result

    @mock.patch.object(data.TeamMember, "Query", return_value=[
        mock.Mock(cdb_person_id="foo", cdb_project_id="bar"),
        mock.Mock(cdb_person_id="FOO", cdb_project_id="BAR"),
    ])
    @mock.patch.object(data, "resolveRSContentObj")
    @mock.patch.object(data, "getObjectHandlesFromObjectIDs")
    def test_get_object_data(self, get_handles, resolveRSContentObj, _):
        "calls resolving function and adds mapped_projects to mappings with 'person_id'"
        mock_handle = mock.Mock()
        mock_handle.getClassDef.return_value.getRootClass.return_value.getClassname.return_value = "bam_classname"
        get_handles.return_value = {"bam": mock_handle}
        model = mock.MagicMock(spec=data.ResourceScheduleDataModel)
        resolveRSContentObj.return_value = {"person_id": "foo"}
        result = data.ResourceScheduleDataModel.get_object_data(model, "uuids")
        self.assertEqual(
            result,
            {
                "bam": {
                    "person_id": "foo",
                    "mapped_projects":["bar"]
                }
            },
            f"unexpected result: {result}"
        )
        resolveRSContentObj.assert_called_once_with("bam_classname", mock_handle, [])

    @mock.patch.object(data.TeamMember, "Query")
    @mock.patch.object(data.logging, "error")
    @mock.patch.object(data, "getObjectHandlesFromObjectIDs")
    def test_get_object_data_error(self, get_handles, log_error, _):
        "raises collected error messages, when resolving RS content fails"
        get_handles.return_value = {"bam": mock.Mock(), "bom": mock.Mock(), "bum": mock.Mock()}
        model = mock.MagicMock(spec=data.ResourceScheduleDataModel)
        with mock.patch.object(
            data,
            "resolveRSContentObj",
            side_effect=[Exception('foo'), Exception('bar'), Exception('baz')]
        ):
            with self.assertRaises(data.HTTPInternalServerError):
                data.ResourceScheduleDataModel.get_object_data(model, "uuids")
        log_error.assert_called_once_with("foo\nbar\nbaz")

    def test_resolveRSContentObj(self):
        "resolves all valid object classes one by one"
        mock_objs, labels, expected_results = self._get_mock_objects()
        for label in labels:
            all_person_ids = []
            mock_obj = mock_objs[label]
            expected_result = expected_results[label]
            result = data.resolveRSContentObj(mock_obj.classname, mock_obj, all_person_ids)
            self.assertEqual(
                result,
                expected_result
            )
            if label == "pool_asgn":
                self.assertListEqual(all_person_ids, ["foo"])
            else:
                self.assertListEqual(all_person_ids, [])

    @mock.patch.object(data.logging, "error")
    def test_resolveRSContentObj_invalid(self, log_error):
        "logs error msg, when encountering unsupported class"
        result = data.resolveRSContentObj("foo_unsupported_classname", mock.Mock(), [])
        self.assertIsNone(result)
        log_error.assert_called_once_with(
            "Unsupported base classname '%s' for resource schedule content", "foo_unsupported_classname"
        )

    @mock.patch.object(data, "get_timeframe", return_value=["TFS", "TFE"])
    @mock.patch.object(data, "get_prj_ids", return_value=["prj0", "prj1"])
    @mock.patch.object(data.ResourceScheduleHelper, "get_chart_data", return_value=["C", "S", "E"])
    def test_get_resource_schedule_data(self, _, __, ___):
        request = mock.MagicMock(json="")

        model = mock.MagicMock(
            spec=data.ResourceScheduleDataModel,
            schedule="schedule",
            ZOOM_LEVELS="ABC",
        )
        model.get_object_data = lambda *args: data.ResourceScheduleDataModel.get_object_data(model, *args)
        result = data.ResourceScheduleDataModel.get_resource_schedule_data(model, ["obj0", "obj1"], request)
        self.assertEqual(
            result,
            {
                'grid': {
                    'A': 'C',
                    'B': 'C',
                    'C': 'C',
                    'data': {},
                    'end_date': 'E',
                    'start_date': 'S'
                },
                'keysWithDuplicates': 'ABC',
            }
        )


CALENDAR_PROFILE_ID = "1cb4cf41-0f40-11df-a6f9-9435b380e702"
ORGANIZATION_ORG_ID = "131"  # Contact Software
PERSON_ID = "integrationperson"


@pytest.mark.integration
class TestResourceScheduleDataModelIntegration(testcase.RollbackTestCase):

    # Assign Person (not User) marked as Resource to organization and resolve
    # organisation's resource schedule elements

    def _create_person(self, personalnummer, isResource, capacity):
        new_kwargs = {
            "personalnummer": personalnummer,
            "is_resource": isResource,
            "capacity": capacity,
            "calendar_profile_id": CALENDAR_PROFILE_ID,
            "org_id": ORGANIZATION_ORG_ID,
            "login": personalnummer,
            "visibility_flag": True,
            "lastname": personalnummer,
        }
        # use operation so that user exits run and resource creation is triggered
        return operation("CDB_Create", Person, **new_kwargs)

    def _get_org_res_sched_id(self):
        org = Organization.KeywordQuery(org_id=ORGANIZATION_ORG_ID)[0]
        res_sched = org.getPrimaryResourceSchedule()  # creates res sched if necessary
        return res_sched.cdb_object_id

    def test_person_resource_in_org_res_sched(self):
        # Create Person marked as resource
        self._create_person(PERSON_ID, True, 8.0)
        # get res sched id
        res_sched_oid = self._get_org_res_sched_id()
        # resolve res sched for organisation
        url = f"/internal/timeschedule/{res_sched_oid}/data"
        payload = {
            "extraDataProps": {
                "timeFrameStartQuarter": 1,
                "timeFrameStartYear": 2022,
                "timeFrameUntilQuarter": 1,
                "timeFrameUntilYear": 2023,
            },
        }
        response = http_post(url, payload)
        # check no error in repsonse
        assert response['error'] is False
        # check if person is resolved in res sched rows
        found_person = False
        for row in response['rows']:
            if PERSON_ID in row['restLink']:
                found_person = True
                break
        assert found_person is True
