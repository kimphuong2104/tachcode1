#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
# pylint: disable=protected-access

import mock
import pytest
from cdb import testcase

from cs.pcs.scheduling import persist
from cs.pcs.scheduling.calendar import IndexedCalendar
from cs.pcs import helpers


def setup_module():
    testcase.run_level_setup()


@pytest.mark.parametrize(
    "dbms,expected",
    [
        (persist.sqlapi.DBMS_ORACLE, helpers.SPLIT_COUNT_ORACLE),
        (persist.sqlapi.DBMS_MSSQL, helpers.SPLIT_COUNT_MSSQL),
        (persist.sqlapi.DBMS_SQLITE, helpers.SPLIT_COUNT_SQLITE),
        (persist.sqlapi.DBMS_POSTGRES, helpers.SPLIT_COUNT_POSTGRES),
        ("unknown", KeyError),
        (persist.sqlapi.DBMS_INFORMIX, KeyError),
        (persist.sqlapi.DBMS_INGRES, KeyError),
        (persist.sqlapi.DBMS_SYBASE, KeyError),
    ],
)
def test_get_split_count(dbms, expected):
    "[_get_split_count]"
    with mock.patch.object(persist.sqlapi, "SQLdbms", return_value=dbms):
        if expected == KeyError:
            with pytest.raises(KeyError):
                persist._get_split_count()
        else:
            assert persist._get_split_count() == expected


@mock.patch.object(persist, "persist_project")
@mock.patch.object(persist, "persist_relships")
@mock.patch.object(persist, "persist_tasks", return_value=["T1", "T2", "T3", "T4"])
def test_persist_changes(p_tasks, p_relships, p_projects):
    "[persist_changes] call dedicated persist functions"
    task_data = [1, 2, 3, 4, 5, 6]
    result = persist.persist_changes(task_data, "D", "O", "N", "P", "C", "R")
    assert result == ("T1", "T2")
    p_tasks.assert_called_once_with(task_data, "N", "P", "C", "O")
    p_relships.assert_called_once_with("R", "D", "N")
    p_projects.assert_called_once_with("P", "C", "T3", "T4")


@pytest.mark.parametrize(
    "persistent,expected",
    [
        (None, TypeError),
        (2, TypeError),
        ([[1, 2, 3, 4, 5, 6]], ValueError),
        ([[1, 2, 3, 4, 5, 6, 7, 8]], ValueError),
    ],
)
def test_persist_relships_broken_relships(persistent, expected):
    "[persist_relships] persistent must be an iterable of iterables with 7 values"
    with pytest.raises(expected):
        persist.persist_relships(persistent, None, None)


@mock.patch.object(persist.sqlapi, "SQLupdate")
@mock.patch.object(persist, "partition", side_effect=lambda page, _: [page])
@mock.patch.object(persist, "_get_split_count")
def test_persist_relships_no_changes(_get_split_count, partition, SQLupdate):
    "[persist_relships] no diff -> no SQL update"
    persistent = [
        ("pred01", "succ01", "EA", 101, False, False, 0),
        # others are changed, but discarded
        ("pred00", "succ00", "EA", 100, False, False, 0),
        ("pred10", "succ10", "EA", 110, False, False, 1),
    ]
    network = {
        "succ00": ["DR", "ES", "EF", "LS", "LF", 3000, "ZZ", "FF", "TF"],
        "pred00": ["DR", "ES", "EF", "LS", "LF", "AA", 1000, "FF", "TF"],
        "succ10": ["DR", "ES", "EF", "LS", "LF", 3010, "ZZ", "FF", "TF"],
        "pred10": ["DR", "ES", "EF", "LS", "LF", "AA", 1010, "FF", "TF"],
        "succ01": ["DR", "ES", "EF", "LS", "LF", 3001, "ZZ", "FF", "TF"],
        "pred01": ["DR", "ES", "EF", "LS", "LF", "AA", 3001, "FF", "TF"],
    }
    assert persist.persist_relships(persistent, ["pred10", "succ01"], network) is None
    assert [x.call_count for x in (_get_split_count, partition, SQLupdate)] == [2, 2, 0]
    partition.assert_has_calls(
        [
            mock.call([], _get_split_count.return_value),
            mock.call([], _get_split_count.return_value),
        ]
    )
    SQLupdate.assert_not_called()


@mock.patch.object(persist.sqlapi, "SQLupdate")
@mock.patch.object(persist, "partition", side_effect=lambda page, _: [page])
@mock.patch.object(persist, "_get_split_count")
def test_persist_relships(_get_split_count, partition, SQLupdate):
    "[persist_relships] diff -> up to two SQL updates"
    persistent = [
        # "bits" in IDs signal old and new violation
        ("pred00", "succ00", "EA", 100, False, False, 0),
        ("pred01", "succ01", "EA", 101, False, False, 0),
        ("2-pred", "2-succ", "EA", 201, False, False, 0),
        ("pred10", "succ10", "EA", 110, False, False, 1),
        ("pred11", "succ11", "EA", 111, False, False, 1),
    ]
    network = {
        # not violated (succAA - predZZ >= relship gap)
        "succ00": ["DR", "ES", "EF", "LS", "LF", 3000, "ZZ", "FF", "TF"],
        "pred00": ["DR", "ES", "EF", "LS", "LF", "AA", 1000, "FF", "TF"],
        "succ10": ["DR", "ES", "EF", "LS", "LF", 3010, "ZZ", "FF", "TF"],
        "pred10": ["DR", "ES", "EF", "LS", "LF", "AA", 1010, "FF", "TF"],
        # violated (succAA - predZZ < relship gap)
        "succ01": ["DR", "ES", "EF", "LS", "LF", 3001, "ZZ", "FF", "TF"],
        "pred01": ["DR", "ES", "EF", "LS", "LF", "AA", 3001, "FF", "TF"],
        "2-succ": ["DR", "ES", "EF", "LS", "LF", 3002, "ZZ", "FF", "TF"],
        "2-pred": ["DR", "ES", "EF", "LS", "LF", "AA", 3002, "FF", "TF"],
        "succ11": ["DR", "ES", "EF", "LS", "LF", 3011, "ZZ", "FF", "TF"],
        "pred11": ["DR", "ES", "EF", "LS", "LF", "AA", 3011, "FF", "TF"],
    }
    assert persist.persist_relships(persistent, "D", network) is None
    assert [x.call_count for x in (_get_split_count, partition, SQLupdate)] == [2, 2, 2]
    partition.assert_has_calls(
        [
            mock.call([("pred10", "succ10")], _get_split_count.return_value),
            mock.call(
                [("pred01", "succ01"), ("2-pred", "2-succ")],
                _get_split_count.return_value,
            ),
        ]
    )
    SQLupdate.assert_has_calls(
        [
            mock.call(
                "cdbpcs_taskrel SET violation = 0"
                " WHERE (pred_task_oid = 'pred10' AND succ_task_oid = 'succ10')"
            ),
            mock.call(
                "cdbpcs_taskrel SET violation = 1"
                " WHERE (pred_task_oid = 'pred01' AND succ_task_oid = 'succ01')"
                " OR (pred_task_oid = '2-pred' AND succ_task_oid = '2-succ')"
            ),
        ]
    )


@pytest.mark.parametrize(
    "project,min_start,max_date,sql_changes",
    [
        # diff -> one SQL update
        (
            {
                "fixed": 1,
                "force_set_start": 0,
                # changed
                "start_time_plan": None,
                # unchanged
                "end_time_plan": 20,
                "days": 10,
            },
            10,
            20,
            "start_time_plan = NEW_DATE, cdb_adate = NEW_ADATE, cdb_apersno = NEW_PERSNO",
        ),
        (
            {
                "fixed": 0,
                "force_set_start": 0,
                # changed
                "start_time_fcast": None,
                # unchanged
                "end_time_fcast": 20,
                "days_fcast": 10,
            },
            10,
            20,
            "start_time_fcast = NEW_DATE, cdb_adate = NEW_ADATE, cdb_apersno = NEW_PERSNO",
        ),
        # no diff -> no SQL update
        (
            {
                "fixed": 1,
                "force_set_start": 0,
                "start_time_plan": 10,
                "end_time_plan": 20,
                "days": 10,
            },
            10,
            20,
            None,
        ),
        (
            {
                "fixed": 0,
                "force_set_start": 0,
                "start_time_fcast": 10,
                "end_time_fcast": 20,
                "days_fcast": 10,
            },
            10,
            20,
            None,
        ),
        # days will always be at least 1
        (
            {
                "fixed": 0,
                "force_set_start": 0,
                "start_time_fcast": 10,
                "end_time_fcast": 11,
                "days_fcast": 1,
            },
            10,
            -20,
            None,
        ),
        # force reset of fcast
        (
            {
                "fixed": 0,
                "force_set_start": 1,
                "days_fcast": 10,
                # unchanged, but will be reset
                "start_time_fcast": 10,
                "end_time_fcast": 20,
            },
            10,
            20,
            "start_time_fcast = NEW_DATE, "
            "end_time_fcast = NEW_DATE, "
            "cdb_adate = NEW_ADATE, "
            "cdb_apersno = NEW_PERSNO",
        ),
    ],
)
def test_persist_project(project, min_start, max_date, sql_changes):
    "[persist_project] project -> SQL update?"
    project["cdb_project_id"] = "foo"
    calendar = mock.Mock(spec=IndexedCalendar)
    calendar.network2day.return_value = "NEW_DATE"
    # make_literal is very slow when run for the first time, so mock it
    with (
        mock.patch.object(
            persist.sqlapi, "make_literal", side_effect=lambda _, __, v: f"{v}"
        ),
        mock.patch.object(
            persist.Project,
            "MakeChangeControlAttributes",
            return_value={"cdb_mdate": "NEW_ADATE", "cdb_mpersno": "NEW_PERSNO"},
        ),
        mock.patch.object(persist.sqlapi, "SQLupdate") as SQLupdate,
    ):
        assert persist.persist_project(project, calendar, min_start, max_date) is None

    if sql_changes:
        SQLupdate.assert_called_once_with(
            f"cdbpcs_project SET {sql_changes} WHERE cdb_project_id = 'foo'"
        )
    else:
        SQLupdate.assert_not_called()
