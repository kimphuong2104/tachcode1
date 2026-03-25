#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"


from cdb import sqlapi


class AdjustAggregationBoards(object):
    def run(self):
        sqlapi.SQLupdate(
            "cs_taskboard_board SET is_aggregation=1 "
            "WHERE board_type in ('personal_board', 'team_board')"
        )


pre = []
post = [AdjustAggregationBoards]
