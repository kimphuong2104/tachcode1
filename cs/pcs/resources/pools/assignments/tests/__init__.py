#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

__revision__ = "$Id$"

import datetime
import unittest

import mock
import pytest

from cs.pcs.resources.pools.assignments import Resource, ResourcePoolAssignment

# Since also protected method have to be tested ignore warnings for protected access
# pylint: disable=protected-access


@pytest.mark.unit
class TestResourcePoolAssignment(unittest.TestCase):
    def test__get_minimum_end(self):
        """
        Test _get_minimum_end with
            - demands and assignments, that ie in the past
            - concurrent rpas in the past and future
        Expected result is the day before the start of the
        future concurrent rpa.
        """
        mock_today = datetime.datetime(2021, 4, 15)
        mock_one_week_prior = datetime.datetime(2021, 4, 8)
        mock_one_week_later = datetime.datetime(2021, 4, 22)

        rpa = mock.MagicMock(spec=ResourcePoolAssignment, start_date=mock_today)
        # always return today
        rpa._get_end = mock.MagicMock(return_value=mock_today)
        # mock existing demands and assignments, that are not interesting
        mock_task_1 = mock.MagicMock(end_time_fcast=mock_one_week_prior)
        mock_task_2 = mock.MagicMock(end_time_fcast=mock_one_week_prior)
        rpa.ResourceDemands = [mock.MagicMock(Task=mock_task_1)]
        rpa.ResourceAllocations = [mock.MagicMock(Task=mock_task_2)]

        rpa.Concurrent = [
            # one rpa already ended
            mock.MagicMock(
                spec=ResourcePoolAssignment,
                start_date=mock_one_week_prior,
                end_date=mock_one_week_prior,
            ),
            # another rpa starting in the future
            mock.MagicMock(
                spec=ResourcePoolAssignment,
                start_date=mock_one_week_later,
            ),
        ]

        self.assertEqual(
            ResourcePoolAssignment._get_minimum_end(rpa), rpa.getNextDate.return_value
        )

        rpa._get_end.assert_called_once_with(min_end=None)
        rpa.getNextDate.assert_called_once_with(mock_one_week_later, -1)


@pytest.mark.unit
class TestResource(unittest.TestCase):
    def test__disable_all_fields(self):
        mock_ctx = mock.MagicMock()
        mock_resource = mock.MagicMock(Resource)

        Resource.disable_all_fields(mock_resource, mock_ctx)

        mock_ctx.set_readonly.assert_has_calls(
            [
                mock.call("name"),
                mock.call("capacity"),
                mock.call("calendar_profile_id"),
                mock.call("referenced_oid"),
            ]
        )


if __name__ == "__main__":
    unittest.main()
