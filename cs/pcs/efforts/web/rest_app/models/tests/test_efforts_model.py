#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access,too-many-lines,no-value-for-parameter

import datetime
import unittest
from collections import defaultdict

import mock
import pytest
import webob
from cdb.objects.iconcache import IconCache
from cdb.objects.org import Person
from cdb.util import PersonalSettings

from cs.pcs.efforts import TimeSheet
from cs.pcs.efforts.stopwatch import Stopwatch
from cs.pcs.efforts.web.rest_app.models import efforts_model

__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

TESTUSER_PERSNO = "caddok"
TESTUSER_NAME = "Administrator"

days_interval = [
    datetime.date(2020, 3, 2),
    datetime.date(2020, 3, 3),
    datetime.date(2020, 3, 4),
    datetime.date(2020, 3, 5),
    datetime.date(2020, 3, 6),
    datetime.date(2020, 3, 7),
    datetime.date(2020, 3, 8),
]


@pytest.mark.unit
class TestEffortsModel(unittest.TestCase):
    maxDiff = None

    def _setup_model(self):
        self.model = efforts_model.EffortsModel()
        self.today = datetime.datetime(2020, 4, 7)

    def _setup_efforts(self):
        effort_data = [
            ["Foo 1", datetime.date(2020, 3, 2), 1.0],
            ["Foo 2", datetime.date(2020, 3, 2), 2.0],
            ["Bar 1", datetime.date(2020, 3, 4), 2.0],
            ["Foo 3", datetime.date(2020, 3, 8), 5.0],
            ["Bar 2", datetime.date(2020, 3, 10), 5.0],
        ]
        self.efforts = [
            mock.MagicMock(
                spec=TimeSheet,
                description=data[0],
                day=data[1],
                hours=data[2],
                person=TESTUSER_NAME,
                person_id=TESTUSER_PERSNO,
            )
            for data in effort_data
        ]

    def _setup_efforts_json(self):
        self.efforts_json = [
            {"hours": 1.0, "day": "2020-03-02"},
            {"hours": 4.0, "day": "2020-03-02"},
            {"hours": 2.0, "day": "2020-03-04"},
        ]

    def _setup_stopwatches_efforts(self):
        self._setup_stopwatches()
        swatch1, swatch2 = self.stopwatches
        effort_data = [
            ["Foo 1", self.today.date(), 1.0, swatch1, "#1"],
            [
                "Foo 2",
                self.today.date() + datetime.timedelta(days=1),
                2.0,
                swatch2,
                "#2",
            ],
        ]
        self.efforts = [
            mock.MagicMock(
                spec=TimeSheet,
                effort_id=data[4],
                description=data[0],
                day=data[1],
                hours=data[2],
                person=TESTUSER_NAME,
                person_id=TESTUSER_PERSNO,
                Stopwatches=[data[3]],
            )
            for data in effort_data
        ]

    def _setup_stopwatches(self):
        stopwatch1 = mock.MagicMock(
            spec=Stopwatch,
            start_time=self.today,
            end_time=self.today + datetime.timedelta(hours=1),
            booked=False,
            effort_id="#1",
            cdb_object_id="#1",
        )
        stopwatch2 = mock.MagicMock(
            spec=Stopwatch,
            start_time=self.today + datetime.timedelta(days=1),
            end_time=self.today + datetime.timedelta(days=1, hours=1),
            booked=True,
            effort_id="#2",
            cdb_object_id="#2",
        )
        self.stopwatches = [stopwatch1, stopwatch2]

    @mock.patch.object(efforts_model.dateutil, "parser")
    def test_parse_date(self, parser):
        "correct date format given to prevent ValueError"
        self._setup_model()
        parser.parse.return_value = datetime.datetime(2020, 3, 2, 5, 20, 33)
        date = self.model.parse_date("2020-03-02T05:20:33.000000")
        parser.parse.assert_called_once_with("2020-03-02T05:20:33.000000")
        self.assertEqual(date, datetime.date(2020, 3, 2))

    def test_get_day_data(self):
        TimeSheet.DAY_HOURS = 8
        test_data = [
            ["unreached", False, datetime.date(2020, 3, 2)],
            ["inprogress", False, datetime.date(2020, 3, 3)],
            ["no-variant", False, datetime.date(2020, 3, 4)],
        ]
        self._setup_model()
        self._setup_efforts_json()
        date = datetime.date(2020, 3, 3)
        for data in test_data:
            with mock.patch.object(efforts_model.datetime, "date") as dt:
                dt.today.return_value = date
                val = self.model.get_day_data(
                    data[2], self.efforts_json, TESTUSER_PERSNO
                )
                self.assertEqual(val, {"hours": 7.0, "variant": data[0]})

    @mock.patch.object(
        efforts_model.EffortsModel,
        "parse_date",
        side_effect=[
            datetime.date(2020, 3, 2),
            datetime.date(2020, 3, 2),
            datetime.date(2020, 3, 4),
        ],
    )
    @mock.patch.object(efforts_model.EffortsModel, "get_day_data", return_value="foo")
    def test_get_days_data(self, get_day_data, parse_date):
        self._setup_model()
        self._setup_efforts_json()
        days_efforts = {
            datetime.date(2020, 3, 2): [self.efforts_json[0], self.efforts_json[1]],
            datetime.date(2020, 3, 4): [self.efforts_json[2]],
        }
        days = [datetime.date(2020, 3, 2), datetime.date(2020, 3, 4)]
        val = self.model.get_days_data(days, self.efforts_json, TESTUSER_PERSNO)
        get_day_data.assert_has_calls(
            [
                mock.call(
                    days[0], days_efforts[datetime.date(2020, 3, 2)], TESTUSER_PERSNO
                ),
                mock.call(
                    days[1], days_efforts[datetime.date(2020, 3, 4)], TESTUSER_PERSNO
                ),
            ]
        )
        self.assertEqual(parse_date.call_count, 3)
        self.assertEqual(get_day_data.call_count, 2)
        self.assertEqual(val, {"2020-03-02": "foo", "2020-03-04": "foo"})

    @mock.patch.object(IconCache, "getIcon", return_value="myIcon")
    def test_get_columns_data(self, getIcon):
        self._setup_model()
        effort = {
            "description": "Foo",
            "hour": 1.0,
            "day": datetime.date(2020, 3, 5),
        }
        test_data = [
            [
                {"attribute": "cdbpcs_effort_entry", "kind": 100, "label": "foo"},
                {"icon": {"src": "myIcon", "title": "foo"}},
            ],
            [{"attribute": "day"}, datetime.date(2020, 3, 5).isoformat()],
            [{"attribute": "hour"}, 1.0],
            [{"attribute": "description"}, "Foo"],
        ]
        for data in test_data:
            val = self.model.get_columns_data(effort, data[0])
            self.assertEqual(val, data[1])
        getIcon.assert_called_once_with("cdbpcs_effort_entry")

    @mock.patch.object(efforts_model.rest, "get_collection_app", return_value="test")
    @mock.patch.object(
        efforts_model.EffortsModel, "__get_rest_object__", return_value={}
    )
    @mock.patch.object(
        efforts_model.EffortsModel, "get_columns_data", side_effect=["foo", "bar"]
    )
    @mock.patch.object(efforts_model, "get_webui_link", return_value="FOO-Link")
    def test_get_row_data(
        self, get_webui_link, get_columns_data, __get_rest_object__, get_collection_app
    ):
        self._setup_model()
        effort = {"cdb_object_id": "foooooooID", "restLink": "restLink"}
        request = "fooo"
        val = self.model.get_row_data(
            effort=effort, cols=["foo", "bar"], request=request
        )
        get_collection_app.assert_called_once_with("fooo")
        __get_rest_object__.assert_called_once_with(effort, "test", "fooo")
        get_columns_data.assert_has_calls(
            [mock.call(effort, "foo"), mock.call(effort, "bar")]
        )
        self.assertEqual(get_columns_data.call_count, 2)
        get_webui_link.assert_called_once()
        self.assertEqual(
            val,
            {
                "columns": ["foo", "bar"],
                "id": "foooooooID",
                "restLink": "restLink",
                "persistent_id": "foooooooID",
                "webuiLink": "FOO-Link",
            },
        )

    def test_get_default_cols_data(self):
        self._setup_model()
        cols = [
            {"attribute": "hours", "id": 1},
            {"attribute": "day", "id": 2},
            {"attribute": "description", "id": 3},
        ]
        val = self.model.get_default_cols_data(cols)
        self.assertEqual(val, {"initGroupBy": [2], "hoursColumnIndex": 0})

    def test_parse_stopwatch(self):
        start_times = [datetime.datetime(2020, 3, 24, 9, 30, 0), None]
        end_time = datetime.datetime(2020, 3, 24, 10, 30, 0)
        self._setup_model()

        for start_time in start_times:
            stopwatch = mock.MagicMock(
                spec=Stopwatch,
                start_time=start_time,
                end_time=end_time,
                booked=False,
                effort_id="#1",
                cdb_object_id="#1",
                is_virtual=False,
            )
            val = self.model.parse_stopwatch(stopwatch)
            self.assertEqual(
                val,
                {
                    "effort_id": "#1",
                    "start_time": start_time.isoformat() if start_time else None,
                    "end_time": end_time.isoformat(),
                    "booked": False,
                    "cdb_object_id": "#1",
                    "is_virtual": False,
                },
            )

    @mock.patch.object(efforts_model.Stopwatch, "KeywordQuery", return_value=[])
    @mock.patch.object(
        efforts_model.EffortsModel, "parse_stopwatch", return_value="foo"
    )
    def test_get_stopwatch_data_empty(self, parse_stopwatch, KeywordQuery):
        self._setup_model()
        self._setup_stopwatches_efforts()
        person = mock.MagicMock(spec=Person, personalnummer=TESTUSER_PERSNO)
        date = datetime.date(2020, 4, 7)
        with mock.patch.object(efforts_model.datetime, "date") as dt:
            dt.today.return_value = date
            val = self.model.get_stopwatch_data(self.efforts, person)
            self.assertEqual(KeywordQuery.call_count, 1)
            parse_stopwatch.assert_called_once_with(self.efforts[0].Stopwatches[0])
            self.assertEqual(
                val,
                {
                    "effortsStopwatches": {"#1": ["foo"]},
                    "otherStopwatches": defaultdict(list),
                },
            )

    @mock.patch.object(
        efforts_model.EffortsModel, "parse_stopwatch", return_value="foo"
    )
    def test_get_stopwatch_data_filled_keywordquery(self, parse_stopwatch):
        self._setup_model()
        self._setup_stopwatches_efforts()
        person = mock.MagicMock(spec=Person, personalnummer=TESTUSER_PERSNO)
        date = datetime.date(2020, 4, 7)
        stopwatch = mock.MagicMock(spec=Stopwatch, effort_id=1)
        with mock.patch.object(efforts_model.datetime, "date") as dt, mock.patch.object(
            efforts_model.Stopwatch, "KeywordQuery", return_value=[stopwatch]
        ) as KeywordQuery:
            dt.today.return_value = date
            val = self.model.get_stopwatch_data(self.efforts, person)
            self.assertEqual(KeywordQuery.call_count, 1)
            self.assertEqual(parse_stopwatch.call_count, 2)
            self.assertEqual(
                val,
                {
                    "effortsStopwatches": {"#1": ["foo"]},
                    "otherStopwatches": {"1": ["foo"]},
                },
            )

    @mock.patch.object(efforts_model.Person, "ByKeys")
    @mock.patch.object(efforts_model.logging, "exception")
    @mock.patch.object(
        efforts_model.EffortsModel, "parse_date", side_effect=ValueError()
    )
    def test_get_efforts_invalid_date_format(self, _, exception, ByKeys):
        self._setup_model()
        ByKeys.return_value.personalnummer = TESTUSER_PERSNO
        request = mock.Mock()
        request.params = {"from": "bar"}
        with self.assertRaises(webob.exc.HTTPBadRequest):
            self.model.get_efforts(request)
        exception.assert_called_once_with("No date passed or wrong date format used.")

    @mock.patch.object(efforts_model.Person, "ByKeys")
    @mock.patch.object(PersonalSettings, "getValueOrDefaultForUser", return_value="10")
    @mock.patch.object(
        efforts_model.ColumnsModel, "get_columns", return_value={"columns": "cols"}
    )
    def _get_efforts_request(self, params, access_granted, expected, _, __, ByKeys):
        model = mock.MagicMock(spec=efforts_model.EffortsModel)
        model.get_stopwatch_data.return_value = "watch"
        model.parse_date.return_value = datetime.date(2020, 4, 8)
        model.get_row_data.return_value = {"foo"}
        model.get_days_data.return_value = "foo"
        model.get_default_cols_data.return_value = "bar"
        model.__get_week_days__.return_value = days_interval
        TimeSheet.DAY_HOURS = 8
        self._setup_model()
        self._setup_efforts()
        ByKeys.return_value.personalnummer = TESTUSER_PERSNO
        request = mock.Mock(params=params)
        for effort in self.efforts:
            effort.CheckAccess.return_value = access_granted

        with mock.patch.object(
            efforts_model.TimeSheet, "KeywordQuery", return_value=self.efforts
        ):
            val = efforts_model.EffortsModel.get_efforts(model, request)
            self.assertEqual(val, expected)

    def test_get_efforts_without_params_no_access(self):
        self._get_efforts_request(
            False,
            False,
            {
                "efforts": [],
                "daysData": "foo",
                "columns": "cols",
                "defaultWeekHours": 40,
                "defaultWeekdayHours": 8,
                "defaultLimitHours": "10",
                "defaultColumnsData": "bar",
                "stopwatchData": "watch",
            },
        )

    def test_get_efforts_with_params_access(self):
        self._get_efforts_request(
            {"fromDate": 1, "toDate": 1},
            True,
            {
                "efforts": [{"foo"}, {"foo"}, {"foo"}, {"foo"}, {"foo"}],
                "daysData": "foo",
                "columns": "cols",
                "defaultLimitHours": "10",
                "defaultWeekHours": 40,
                "defaultWeekdayHours": 8,
                "defaultColumnsData": "bar",
                "stopwatchData": "watch",
            },
        )

    def test_get_efforts_with_params_access_and_specific_date(self):
        self._get_efforts_request(
            {"fromDate": 1, "toDate": 1, "specificDay": 2},
            True,
            {
                "efforts": [{"foo"}, {"foo"}, {"foo"}, {"foo"}, {"foo"}],
                "daysData": "foo",
                "columns": "cols",
                "defaultLimitHours": "10",
                "defaultWeekHours": 40,
                "defaultWeekdayHours": 8,
                "specificDayData": "foo",
                "defaultColumnsData": "bar",
                "stopwatchData": "watch",
            },
        )

    def test_get_efforts_without_params_access(self):
        "request without specific date"
        self._get_efforts_request(
            False,
            True,
            {
                "efforts": [{"foo"}, {"foo"}, {"foo"}, {"foo"}, {"foo"}],
                "daysData": "foo",
                "columns": "cols",
                "defaultLimitHours": "10",
                "defaultWeekHours": 40,
                "defaultWeekdayHours": 8,
                "defaultColumnsData": "bar",
                "stopwatchData": "watch",
            },
        )

    @mock.patch.object(efforts_model.Person, "ByKeys")
    @mock.patch.object(efforts_model.datetime, "date")
    def test_validate_stopwatches_valid(self, date, ByKeys):
        self._setup_model()
        self._setup_stopwatches()
        for sw in self.stopwatches:
            sw.CheckAccess.return_value = True
        ByKeys.return_value.personalnummer = TESTUSER_PERSNO

        with mock.patch.object(
            efforts_model.Stopwatch, "KeywordQuery", return_value=self.stopwatches
        ) as KeywordQuery:
            sws, person = self.model.validate_stopwatches(["#1", "#2"], "#1")
            KeywordQuery.assert_called_once_with(
                effort_id="#1",
                stopwatch_day=date.today.return_value,
                person_id=TESTUSER_PERSNO,
                booked=False,
                is_virtual=False,
            )
            self.assertEqual(person.personalnummer, TESTUSER_PERSNO)
            self.assertEqual(sws, self.stopwatches)
        for sw in self.stopwatches:
            sw.CheckAccess.assert_called_once_with("read")

    @mock.patch.object(efforts_model.logging, "exception")
    @mock.patch.object(efforts_model.Person, "ByKeys")
    @mock.patch.object(efforts_model.cdbwrapc, "get_label", return_value="error")
    def test_validate_stopwatches_invalid(self, get_label, ByKeys, exception):
        self._setup_model()
        self._setup_stopwatches()
        for sw in self.stopwatches:
            sw.CheckAccess.return_value = True
        ByKeys.return_value.personalnummer = TESTUSER_PERSNO
        Stopwatch.KeywordQuery = mock.MagicMock(return_value=self.stopwatches)

        with mock.patch.object(
            efforts_model.Stopwatch, "KeywordQuery", return_value=self.stopwatches
        ), self.assertRaises(webob.exc.HTTPConflict):
            self.model.validate_stopwatches(["#1"], "#1")
        get_label.assert_called_once_with("cdbpcs_efforts_stopwatch_refresh")
        exception.assert_called_once_with("error")
        for sw in self.stopwatches:
            sw.CheckAccess.assert_called_once_with("read")

    @mock.patch.object(efforts_model.logging, "exception")
    @mock.patch.object(efforts_model.cdbwrapc, "get_label", return_value="error")
    @mock.patch.object(efforts_model.Person, "ByKeys")
    @mock.patch.object(efforts_model.datetime, "date")
    def test_validate_stopwatches_invalid_no_access(
        self, date, ByKeys, get_label, exception
    ):
        self._setup_model()
        self._setup_stopwatches()
        for sw in self.stopwatches:
            sw.CheckAccess.return_value = False
        ByKeys.return_value.personalnummer = TESTUSER_PERSNO

        with mock.patch.object(
            efforts_model.Stopwatch, "KeywordQuery", return_value=self.stopwatches
        ) as KeywordQuery:
            with self.assertRaises(webob.exc.HTTPConflict):
                self.model.validate_stopwatches(["#1", "#2"], "#1")

            KeywordQuery.assert_called_once_with(
                effort_id="#1",
                stopwatch_day=date.today.return_value,
                person_id=TESTUSER_PERSNO,
                booked=False,
                is_virtual=False,
            )
        get_label.assert_called_once_with("cdbpcs_efforts_stopwatch_refresh")
        exception.assert_called_once_with("error")
        for sw in self.stopwatches:
            sw.CheckAccess.assert_called_once_with("read")

    @mock.patch.object(efforts_model.logging, "exception")
    def test_start_stopwatch_no_json_attr(self, exception):
        self._setup_model()
        request = {"foo": "bar"}

        with self.assertRaises(webob.exc.HTTPBadRequest):
            self.model.start_stopwatch(request)
        exception.assert_called_once_with('The request has no attribute "json"')

    @mock.patch.object(efforts_model.logging, "exception")
    def test_start_stopwatch_wrong_param(self, exception):
        self._setup_model()
        request = mock.Mock()
        request.json = "foo"

        with self.assertRaises(webob.exc.HTTPBadRequest):
            self.model.start_stopwatch(request)
        exception.assert_called_once_with("string indices must be integers, not 'str'")

    @mock.patch.object(
        efforts_model.EffortsModel, "parse_stopwatch", return_value="bar"
    )
    @mock.patch.object(efforts_model.operations, "operation", return_value="sws")
    @mock.patch.object(efforts_model.dateutil, "parser")
    def test_start_stopwatch(self, parser, operation, parse_stopwatch):
        self._setup_model()
        request = mock.Mock(
            json={
                "effort_id": 1,
                "start_time": "2020-03-02T05:20:33.000000",
                "is_virtual": True,
                "existing_stopwatches": "foo",
            }
        )
        person = mock.MagicMock(spec=Person, personalnummer=TESTUSER_PERSNO)
        parser.parse.return_value = datetime.datetime(2020, 3, 2, 5, 20, 33)

        with mock.patch.object(
            efforts_model.EffortsModel,
            "validate_stopwatches",
            return_value=("foo", person),
        ) as validate_sws:
            val = self.model.start_stopwatch(request)
            self.assertEqual(val, "bar")
            validate_sws.assert_called_once_with("foo", 1, True, True)
            operation.assert_called_once_with(
                "CDB_Create",
                efforts_model.Stopwatch,
                effort_id=1,
                stopwatch_day=datetime.date(2020, 3, 2),
                start_time=datetime.datetime(2020, 3, 2, 5, 20, 33),
                person_id=TESTUSER_PERSNO,
                booked=False,
                is_virtual=True,
            )
            parse_stopwatch.assert_called_once_with("sws")
            parser.parse.assert_called_once_with("2020-03-02T05:20:33.000000")

    @mock.patch.object(efforts_model.logging, "exception")
    def test_stop_stopwatch_no_json_attr(self, exception):
        self._setup_model()
        request = {"foo": "bar"}
        with self.assertRaises(webob.exc.HTTPBadRequest):
            self.model.stop_stopwatch(request)
        exception.assert_called_once_with('The request has no attribute "json"')

    @mock.patch.object(efforts_model.logging, "exception")
    def test_stop_stopwatch_wrong_param(self, exception):
        self._setup_model()
        request = mock.Mock()
        request.json = "foo"
        with self.assertRaises(webob.exc.HTTPBadRequest):
            self.model.stop_stopwatch(request)
        exception.assert_called_once_with("string indices must be integers, not 'str'")

    @mock.patch.object(efforts_model.dateutil, "parser")
    @mock.patch.object(efforts_model, "auth")
    @mock.patch.object(efforts_model.logging, "exception")
    def test_stop_stopwatch_no_access(self, exception, mock_auth, parser):
        self._setup_model()
        request = mock.Mock(
            json={
                "stopwatch_ids": [1],
                "end_time": "foo_time",
            }
        )
        stopwatch = mock.MagicMock(cdb_object_id="#1")
        stopwatch.CheckAccess = mock.MagicMock(return_value=False)
        with self.assertRaises(webob.exc.HTTPNotFound):
            with mock.patch.object(
                efforts_model.Stopwatch, "KeywordQuery", return_value=[stopwatch]
            ):
                self.model.stop_stopwatch(request)
        exception.assert_called_once_with(
            "Stop Stopwatches: '%s' has no save access on stopwatches: '%s'",
            mock_auth.persno,
            [1],
        )
        stopwatch.CheckAccess.assert_called_once_with("save")
        stopwatch.Update.assert_not_called()
        parser.parse.assert_called_once_with("foo_time")
        parser.parse.return_value.replace.assert_called_once_with(tzinfo=None)

    @mock.patch.object(efforts_model.EffortsModel, "record_stopwatches_helper")
    @mock.patch.object(
        efforts_model.EffortsModel, "parse_stopwatch", return_value="bar"
    )
    @mock.patch.object(efforts_model.dateutil, "parser")
    def test_stop_stopwatch_no_endtime_virtual(
        self, parser, parse_stopwatch, record_stopwatches_helper
    ):
        self._setup_model()
        request = mock.Mock(
            json={
                "stopwatch_ids": [1],
                "end_time": "2020-03-02T05:20:33.000000",
            }
        )
        stopwatch = mock.MagicMock(
            spec=Stopwatch,
            start_time=datetime.datetime(2020, 3, 1, 5, 20, 33),
            end_time=None,
            booked=False,
            effort_id="#1",
            cdb_object_id="#1",
            is_virtual=True,
        )
        parser.parse.return_value = datetime.datetime(2020, 3, 2, 5, 20, 33)
        with mock.patch.object(
            efforts_model.Stopwatch, "KeywordQuery", return_value=[stopwatch]
        ):
            val = self.model.stop_stopwatch(request)
            stopwatch.Update.assert_called_once_with(
                end_time=datetime.datetime(2020, 3, 2, 5, 20, 33, tzinfo=None)
            )
            self.assertEqual(val, "bar")
            parse_stopwatch.assert_called_once_with(stopwatch)
            self.assertEqual(record_stopwatches_helper.call_count, 0)
            parser.parse.assert_called_once_with("2020-03-02T05:20:33.000000")

    @mock.patch.object(efforts_model.logging, "exception")
    @mock.patch.object(efforts_model.dateutil, "parser")
    def test_stop_stopwatch_endtime_virtual(self, parser, exception):
        self._setup_model()
        request = mock.Mock(
            json={
                "stopwatch_ids": [1],
                "end_time": "2020-03-02T05:20:33.000000",
            }
        )
        stopwatch = mock.MagicMock(
            spec=Stopwatch,
            start_time=datetime.datetime(2020, 3, 1, 5, 20, 33),
            end_time=datetime.datetime(2020, 3, 2, 5, 20, 33),
            booked=False,
            effort_id="#1",
            cdb_object_id="#1",
            is_virtual=True,
        )
        parser.parse.return_value = datetime.datetime(2020, 3, 2, 5, 20, 33)
        with mock.patch.object(
            efforts_model.Stopwatch, "KeywordQuery", return_value=[stopwatch]
        ), self.assertRaises(webob.exc.HTTPConflict):
            self.model.stop_stopwatch(request)
        exception.assert_called_once_with(
            "Stopwatch is already stopped and the endtime is set!"
        )
        parser.parse.assert_called_once_with("2020-03-02T05:20:33.000000")

    @mock.patch.object(efforts_model.dateutil, "parser")
    @mock.patch.object(efforts_model.EffortsModel, "record_stopwatches_helper")
    @mock.patch.object(
        efforts_model.EffortsModel, "parse_stopwatch", return_value="bar"
    )
    def test_stop_stopwatch_no_endtime_not_virtual(
        self, parse_stopwatch, record_stopwatches_helper, parser
    ):
        self._setup_model()
        request = mock.Mock(
            json={
                "stopwatch_ids": [1],
                "end_time": "2020-03-02T05:20:33.000000",
            }
        )
        stopwatch = mock.MagicMock(
            spec=Stopwatch,
            start_time=datetime.datetime(2020, 3, 1, 5, 20, 33),
            end_time=None,
            booked=False,
            effort_id="#1",
            cdb_object_id="#1",
            is_virtual=False,
        )
        parser.parse.return_value = datetime.datetime(2020, 3, 2, 5, 20, 33)
        with mock.patch.object(
            efforts_model.Stopwatch, "KeywordQuery", return_value=[stopwatch]
        ):
            val = self.model.stop_stopwatch(request)
            stopwatch.Update.assert_called_once_with(
                end_time=datetime.datetime(2020, 3, 2, 5, 20, 33, tzinfo=None)
            )
            self.assertEqual(val, "bar")
            parse_stopwatch.assert_called_once_with(stopwatch)
            record_stopwatches_helper.assert_called_once_with(
                [stopwatch], stopwatch.effort_id, stopwatch.is_virtual
            )
            parser.parse.assert_called_once_with("2020-03-02T05:20:33.000000")

    @mock.patch.object(efforts_model.logging, "exception")
    def test_valid_stopwatches_no_params(self, exception):
        self._setup_model()
        request = {}
        with self.assertRaises(webob.exc.HTTPBadRequest):
            self.model.valid_stopwatches(request)
        exception.assert_called_once_with('The request has no attribute "params"!')

    @mock.patch.object(
        efforts_model.EffortsModel,
        "validate_stopwatches",
        side_effect=Exception("test"),
    )
    @mock.patch.object(efforts_model.logging, "exception")
    def test_valid_stopwatches_exception(self, exception, validate_swatches):
        self._setup_model()
        request = mock.MagicMock()
        request.params = {}
        with self.assertRaises(Exception):
            self.model.valid_stopwatches(request)
        exception.assert_called_once_with("test")
        validate_swatches.assert_called_once_with([], None, False, False)

    @mock.patch.object(
        efforts_model.EffortsModel, "validate_stopwatches", return_value=("foo", "bar")
    )
    def test_valid_stopwatches(self, validate_stopwatches):
        self._setup_model()
        request = mock.MagicMock(
            params={
                "stopwatch_ids": "1",
                "effort_id": "5",
                "is_virtual": "true",
            }
        )
        val = self.model.valid_stopwatches(request)
        validate_stopwatches.assert_called_once_with(["1"], 5, False, True)
        self.assertEqual(val, True)

    @mock.patch.object(efforts_model.logging, "exception")
    def test_record_stopwatches_no_json(self, exception):
        self._setup_model()
        request = {}
        with self.assertRaises(webob.exc.HTTPBadRequest):
            self.model.record_stopwatches(request)
        exception.assert_called_once_with('The request has no attribute "json"')

    @mock.patch.object(efforts_model.logging, "exception")
    def test_record_stopwatches_wrong_params(self, exception):
        self._setup_model()
        request = mock.MagicMock()
        request.json = {}
        with self.assertRaises(webob.exc.HTTPBadRequest):
            self.model.record_stopwatches(request)
        exception.assert_called_once_with("'stopwatch_ids'")

    @mock.patch.object(efforts_model.EffortsModel, "record_stopwatches_helper")
    @mock.patch.object(
        efforts_model.EffortsModel, "validate_stopwatches", return_value=("foo", "bar")
    )
    def test_record_stopwatches(self, validate_stopwatches, record_s_helper):
        self._setup_model()
        request = mock.MagicMock(
            json={
                "stopwatch_ids": [1],
                "effort_id": "5",
                "is_virtual": "true",
            }
        )
        self.model.record_stopwatches(request)
        validate_stopwatches.assert_called_once_with([1], 5, False, "true")
        record_s_helper.assert_called_once_with("foo", 5, "true")

    @mock.patch.object(efforts_model.TimeSheet, "KeywordQuery")
    def test_record_stopwatches_helper_is_virtual(self, KeywordQuery):
        self._setup_model()
        self._setup_stopwatches()
        for stopwatch in self.stopwatches:
            stopwatch.Update = mock.MagicMock()
        self.model.record_stopwatches_helper(self.stopwatches, 5, True)
        for stopwatch in self.stopwatches:
            stopwatch.Update.assert_called_once_with(booked=True)
        self.assertEqual(KeywordQuery.call_count, 0)

    @mock.patch.object(efforts_model.logging, "exception")
    @mock.patch.object(efforts_model.TimeSheet, "KeywordQuery")
    def test_record_stopwatches_helper_is_virtual_exception(
        self, KeywordQuery, exception
    ):
        self._setup_model()
        self._setup_stopwatches()
        for stopwatch in self.stopwatches:
            delattr(stopwatch, "end_time")
            stopwatch.Update = mock.MagicMock()
        with self.assertRaises(AttributeError):
            self.model.record_stopwatches_helper(self.stopwatches, 5, True)
        for stopwatch in self.stopwatches:
            self.assertEqual(stopwatch.Update.call_count, 0)
        self.assertEqual(KeywordQuery.call_count, 0)
        exception.assert_called_once()

    @mock.patch.object(efforts_model.logging, "exception")
    @mock.patch.object(efforts_model.TimeSheet, "KeywordQuery", return_value=None)
    def test_record_stopwatches_helper_not_virtual_wrong_id(
        self, KeywordQuery, exception
    ):
        self._setup_model()
        self._setup_stopwatches()
        for stopwatch in self.stopwatches:
            stopwatch.Update = mock.MagicMock()
        with self.assertRaises(Exception):
            self.model.record_stopwatches_helper(self.stopwatches, "foo", False)
        exception.assert_called_once_with(
            "invalid literal for int() with base 10: 'foo'"
        )
        self.assertEqual(KeywordQuery.call_count, 0)
        for stopwatch in self.stopwatches:
            stopwatch.Update.assert_called_once_with(booked=True)

    @mock.patch.object(efforts_model, "auth")
    @mock.patch.object(efforts_model.logging, "exception")
    @mock.patch.object(efforts_model.TimeSheet, "KeywordQuery", return_value=[])
    def test_record_stopwatches_helper_not_virtual_no_effort(
        self, KeywordQuery, exception, auth
    ):
        auth.persno = "foo_user"
        self._setup_model()
        self._setup_stopwatches()
        for stopwatch in self.stopwatches:
            stopwatch.Update = mock.MagicMock()
        with self.assertRaises(webob.exc.HTTPNotFound):
            self.model.record_stopwatches_helper(self.stopwatches, 5, False)
        exception.assert_called_once_with(
            "'%s' has no save access on effort: '%s'", "foo_user", 5
        )
        KeywordQuery.assert_called_once_with(effort_id=5)
        for stopwatch in self.stopwatches:
            stopwatch.Update.assert_called_once_with(booked=True)

    @mock.patch.object(efforts_model, "auth")
    @mock.patch.object(efforts_model.logging, "exception")
    @mock.patch.object(efforts_model.TimeSheet, "KeywordQuery")
    def test_record_stopwatches_helper_not_virtual_no_effort_access(
        self, KeywordQuery, exception, auth
    ):
        auth.persno = "foo_user"
        self._setup_model()
        self._setup_stopwatches()
        for stopwatch in self.stopwatches:
            stopwatch.Update = mock.MagicMock()
            stopwatch.CheckAccess.return_value = False
        KeywordQuery.return_value = self.stopwatches
        with self.assertRaises(webob.exc.HTTPNotFound):
            self.model.record_stopwatches_helper(self.stopwatches, 5, False)
        exception.assert_called_once_with(
            "'%s' has no save access on effort: '%s'", "foo_user", 5
        )
        KeywordQuery.assert_called_once_with(effort_id=5)
        for stopwatch in self.stopwatches:
            stopwatch.Update.assert_called_once_with(booked=True)
            stopwatch.CheckAccess.assert_called_once_with("save")

    @mock.patch.object(efforts_model.TimeSheet, "KeywordQuery")
    def test_record_stopwatches_helper_not_virtual(self, KeywordQuery):
        self._setup_model()
        self._setup_stopwatches()
        effort = mock.MagicMock(spec=TimeSheet, hours=1)
        KeywordQuery.return_value = [effort]
        for stopwatch in self.stopwatches:
            stopwatch.Update = mock.MagicMock()
        self.model.record_stopwatches_helper(self.stopwatches, 5, False)
        effort.Update.assert_called_once_with(hours=3)

    def test_reset_stopwatches(self):
        self._setup_model()
        stopwatch = mock.MagicMock(spec=Stopwatch, booked=False)
        request = mock.Mock(
            json={
                "effort_id": 1,
                "stopwatch_ids": 2,
                "is_virtual": False,
            }
        )
        with mock.patch.object(
            efforts_model.EffortsModel,
            "validate_stopwatches",
            return_value=([stopwatch], "person"),
        ) as vs:
            self.model.reset_stopwaches(request)
            vs.assert_called_once_with(2, 1, False, False)
            stopwatch.Update.assert_called_once_with(booked=True)

    @mock.patch.object(efforts_model.logging, "exception")
    def test_reset_stopwatches_no_json_attr(self, exception):
        self._setup_model()
        request = {}
        with self.assertRaises(webob.exc.HTTPBadRequest):
            self.model.reset_stopwaches(request)
        exception.assert_called_once_with('The request has no attribute "json"')

    @mock.patch.object(efforts_model.logging, "exception")
    def test_reset_stopwatches_error(self, exception):
        self._setup_model()
        request = mock.Mock()
        request.json = {}
        with self.assertRaises(webob.exc.HTTPBadRequest):
            self.model.reset_stopwaches(request)
        self.assertEqual(exception.call_count, 1)

    def test___get_rest_object__(self):
        self.skipTest("Very simple method.")

    def test___get_week_days_with_parameter__(self):
        val = efforts_model.EffortsModel.__get_week_days__(datetime.date(2020, 2, 26))
        self.assertEqual(
            val,
            [
                datetime.date(2020, 2, 24),
                datetime.date(2020, 2, 25),
                datetime.date(2020, 2, 26),
                datetime.date(2020, 2, 27),
                datetime.date(2020, 2, 28),
                datetime.date(2020, 2, 29),
                datetime.date(2020, 3, 1),
            ],
        )

    @mock.patch.object(efforts_model, "datetime")
    def test___get_week_days_without_parameter__(self, mock_dt):
        mock_dt.date.today.return_value = datetime.date(2022, 8, 9)
        mock_dt.timedelta = datetime.timedelta
        self.assertEqual(
            efforts_model.EffortsModel.__get_week_days__(),
            [
                datetime.date(2022, 8, 8),
                datetime.date(2022, 8, 9),
                datetime.date(2022, 8, 10),
                datetime.date(2022, 8, 11),
                datetime.date(2022, 8, 12),
                datetime.date(2022, 8, 13),
                datetime.date(2022, 8, 14),
            ],
        )

    def test___get_day_range_param_none__(self):
        val = efforts_model.EffortsModel.__get_day_range__(
            None, datetime.date(2020, 3, 4)
        )
        self.assertEqual(val, [])

    def test___get_day_range_correct_params__(self):
        val = efforts_model.EffortsModel.__get_day_range__(
            datetime.date(2020, 3, 2), datetime.date(2020, 3, 4)
        )
        self.assertEqual(
            val,
            [
                datetime.date(2020, 3, 2),
                datetime.date(2020, 3, 3),
                datetime.date(2020, 3, 4),
            ],
        )


@pytest.mark.unit
class TestColumnsModel(unittest.TestCase):
    def test_get_columns(self):
        val = efforts_model.ColumnsModel.get_columns()
        expected_cols = [
            "cdbpcs_effort_entry",
            "day",
            "cdb_project_id",
            "cdb_project_id",
            "project_name",
            "task_name",
            "description",
            "location",
            "mapped_eff_act_type_name",
            "hours",
        ]
        self.assertEqual(len(val["columns"]), 9)
        cols = []
        for i in range(0, 6, 1):
            cols.append(val["columns"][i]["attribute"])
        self.assertEqual(cols.sort(), expected_cols.sort())


if __name__ == "__main__":
    unittest.main()
