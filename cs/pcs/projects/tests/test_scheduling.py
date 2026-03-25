#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#
# pylint: disable=protected-access

import mock
import pytest

from cs.pcs.projects import scheduling


@pytest.mark.parametrize("skip", [0, 1])
def test_recalculate_do_followups(skip):
    p = mock.MagicMock(spec=scheduling.Project, msp_active=0, cdb_project_id="id")
    with mock.patch.object(scheduling.Project, "ByKeys"):
        assert scheduling.Project.recalculate(p, None, skip) is None
    p.recalculate_now.assert_called_once_with(skip_followups=skip)


@mock.patch.object(scheduling.sig, "emit")
@mock.patch.object(scheduling, "schedule", return_value=[1, 2, 3, 4])
def test_recalculate_now_default(schedule, emit):
    "[recalculate_now] default parameters"
    p = mock.Mock(spec=scheduling.Project)
    p.cdb_project_id = "id"
    assert scheduling.Project.recalculate_now(p) is None

    schedule.assert_called_once_with(p.cdb_project_id)
    p.aggregate.assert_called_once_with()
    emit.assert_has_calls(
        [
            mock.call(scheduling.Project, "adjustAllocationsOnly"),
            mock.call()(p, 2),
            mock.call(scheduling.Project, "do_consistency_checks"),
            mock.call()(p, 1),
        ]
    )


@pytest.mark.parametrize(
    "skip_scheduling,skip_followups",
    [
        (0, 0),
        (0, 1),
        (1, 0),
        (1, 1),
    ],
)
def test_recalculate_now(skip_scheduling, skip_followups):
    "[recalculate_now]"
    p = mock.Mock(spec=scheduling.Project)
    p.cdb_project_id = "id"
    with (
        mock.patch.object(scheduling.sig, "emit") as emit,
        mock.patch.object(
            scheduling, "schedule", return_value=[1, 2, 3, 4]
        ) as schedule,
    ):
        assert (
            scheduling.Project.recalculate_now(
                p, skip_scheduling=skip_scheduling, skip_followups=skip_followups
            )
            is None
        )
    p.aggregate.assert_called_once_with()

    if skip_scheduling:
        schedule.assert_not_called()
    else:
        schedule.assert_called_once_with(p.cdb_project_id)

    if skip_scheduling or skip_followups:
        emit.assert_not_called()
    else:
        emit.assert_has_calls(
            [
                mock.call(scheduling.Project, "adjustAllocationsOnly"),
                mock.call()(p, 2),
                mock.call(scheduling.Project, "do_consistency_checks"),
                mock.call()(p, 1),
            ]
        )
