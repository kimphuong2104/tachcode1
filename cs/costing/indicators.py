#!/usr/bin/env powerscript
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 1990 - 2021 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com

from collections import defaultdict

from cdb import sqlapi
from cdb import sig

from cs.pcs.projects.indicators import Indicator
from cs.pcs.projects.indicators import ResolveIndicators

"""
Indicators aggregate calculation components data in as few database roundtrips as possible.
"""

cloned_components_view = "cdbpco_comp_indicators_v"

@sig.connect(ResolveIndicators)
def ResolveComponentsIndicators(rest_name, comp_object_ids, indicator_whitelist=None):
    if rest_name != "cdbpco_component":
        return None
    raw_data = sqlapi.RecordSet2(
        cloned_components_view,
        " comp_object_id IN ('{}')".format(
            "', '".join(
                sqlapi.quote(comp_object_id[0])
                for comp_object_id in comp_object_ids)
        )
    )
    by_data_source = defaultdict(lambda: defaultdict(dict))

    for data_row in raw_data:
        by_data_source[data_row.comp_object_id][data_row.data_source] = int(data_row.quantity)

    ifilter = {"rest_visible_name": "cdbpco_component"}

    if indicator_whitelist:
        ifilter["name"] = indicator_whitelist

    return {
        indicator.name: indicator.to_json(by_data_source)
        for indicator in Indicator.KeywordQuery(**ifilter)
    }
