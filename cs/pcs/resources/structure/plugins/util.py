#!/usr/bin/env powerscript
# coding: utf-8
#
# Copyright (C) 1990 - 2023 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from cdb import sqlapi
from cs.pcs.projects.project_structure.util import resolve_query
from cs.pcs.resources.structure.plugins.ctes import (
    get_query_pattern,
    load_query_pattern,
)
from cs.pcs.resources.web.models.helpers import get_quarter


def resolve_including_timeframe(sql_pattern_name, root_oid, request):
    timeFrame = request.json['extraDataProps']
    timeframe_start = get_quarter(timeFrame["timeFrameStartYear"], timeFrame["timeFrameStartQuarter"])
    timeframe_end = get_quarter(timeFrame["timeFrameUntilYear"], timeFrame["timeFrameUntilQuarter"], True)
    query_pattern = get_query_pattern(sql_pattern_name, load_query_pattern)
    query_str = query_pattern.format(
        oid=root_oid,
        start=sqlapi.SQLdate_literal(timeframe_start),
        end=sqlapi.SQLdate_literal(timeframe_end),
    )
    return resolve_query(query_str)
