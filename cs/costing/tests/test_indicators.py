#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

from __future__ import absolute_import

import mock

from cdb import testcase

from cs.costing.indicators import ResolveComponentsIndicators


class TestIndicators(testcase.RollbackTestCase):
    def test_ResolveComponentsIndicators_other_restname(self):
        self.assertEquals(
            ResolveComponentsIndicators("foo", []),
            None
        )

    @mock.patch("cs.costing.indicators.Indicator.KeywordQuery")
    @mock.patch("cs.costing.indicators.sqlapi")
    def test_ResolveComponentsIndicators(self, sqlapi, KeywordQuery):
        data = [
            mock.MagicMock(comp_object_id="1", data_source="foo", quantity=2),
            mock.MagicMock(comp_object_id="2", data_source="foo", quantity=1)
        ]
        sqlapi.RecordSet2 = mock.MagicMock(return_value=data)
        sqlapi.quote = mock.MagicMock(side_effect=lambda x: x)

        to_json = mock.MagicMock()
        indicator = mock.MagicMock(to_json=to_json)
        indicator.name = "ind"
        KeywordQuery.return_value = [indicator]
        self.assertEquals(
            ResolveComponentsIndicators("cdbpco_component", ['1', '2'], ["ind"]),
            {
                "ind": to_json.return_value
            }
        )

        to_json.assert_called_once_with({"1": {"foo": 2}, "2": {"foo": 1}})
        KeywordQuery.assert_called_once_with(
            rest_visible_name="cdbpco_component",
            name=["ind"]
        )
