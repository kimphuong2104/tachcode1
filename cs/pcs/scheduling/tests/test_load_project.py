#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

import mock
import pytest

from cs.pcs.scheduling import load_project


@pytest.mark.parametrize(
    "start_date,calendar_start",
    [
        (-1, -1),
        (1, 1),
        (10, 10),
        (10, 10),
    ],
)
def test_load_project(start_date, calendar_start):
    "[load_project] loads project and calendar starting at a certain date"
    project = {
        "start_time_fcast": start_date,
        "calendar_profile_id": "C",
        "days_fcast": "D",
    }
    with (
        mock.patch.object(load_project, "convert_days2network") as convert_days2network,
        mock.patch.object(load_project, "IndexedCalendar") as IndexedCalendar,
        # results beyond the first one are ignored
        mock.patch.object(load_project, "load", return_value=[project, None]),
    ):
        result = load_project.load_project("foo")
    assert result == (project, IndexedCalendar.return_value)
    IndexedCalendar.assert_called_once_with("C", calendar_start, "D")
    convert_days2network.assert_called_once_with(
        IndexedCalendar.return_value,
        project,
        load_project.START_DATES,
        load_project.END_DATES,
        load_project.DURATIONS,
    )
