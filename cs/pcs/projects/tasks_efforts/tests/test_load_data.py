#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#


import unittest

import mock
import pytest

from cs.pcs.projects.tasks_efforts import load_data


@pytest.mark.unit
class TestInit(unittest.TestCase):
    @mock.patch.object(load_data.sqlapi, "SQLnumber")
    @mock.patch.object(load_data.sqlapi, "SQLstring")
    @mock.patch.object(load_data.sqlapi, "SQLrows")
    @mock.patch.object(load_data.sqlapi, "SQLselect")
    def test_get_efforts(self, SQLselect, SQLrows, SQLstring, SQLnumber):
        """Test get_efforts"""

        # Note: There two efforts entries for task foo_1
        mock_ts_1 = mock.MagicMock(task_id="foo_1", hours=1.0)
        mock_ts_2 = mock.MagicMock(task_id="foo_2", hours=2.0)
        mock_ts_3 = mock.MagicMock(task_id="foo_3", hours=3.0)

        SQLselect.return_value = [mock_ts_1, mock_ts_2, mock_ts_3]
        SQLrows.side_effect = len
        SQLstring.side_effect = lambda x, _, i: x[i].task_id
        SQLnumber.side_effect = lambda x, _, i: x[i].hours

        expected_dict = {"foo_1": 1.0, "foo_2": 2.0, "foo_3": 3.0}

        self.assertDictEqual(expected_dict, load_data.get_efforts("foo"))

        SQLselect.assert_called_once_with(
            "task_id, SUM(hours) AS hours FROM cdbpcs_time_sheet WHERE cdb_project_id='foo' "
            "GROUP BY task_id"
        )
        SQLrows.assert_called_once_with(SQLselect.return_value)

        SQLstring.assert_has_calls(
            [
                mock.call(SQLselect.return_value, 0, 0),
                mock.call(SQLselect.return_value, 0, 1),
                mock.call(SQLselect.return_value, 0, 2),
            ]
        )

        SQLnumber.assert_has_calls(
            [
                mock.call(SQLselect.return_value, 1, 0),
                mock.call(SQLselect.return_value, 1, 1),
                mock.call(SQLselect.return_value, 1, 2),
            ]
        )
