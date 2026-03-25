#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from cdb import sqlapi


class AdjustRatingSchemeOfChecklists:
    def run(self):
        sqlapi.SQLupdate(
            "cdbpcs_checklst SET rating_scheme = 'Grades' "
            "WHERE rating_scheme = 'GermanSchoolmarks' "
        )
        sqlapi.SQLupdate(
            "cdbpcs_cl_item SET rating_scheme = 'Grades' "
            "WHERE rating_scheme = 'GermanSchoolmarks' "
        )
        sqlapi.SQLupdate(
            "cdbpcs_rat_asgn SET rating_scheme = 'Grades' "
            "WHERE rating_scheme = 'GermanSchoolmarks' "
        )
        sqlapi.SQLupdate(
            "cdbpcs_rat_def SET name = 'Grades' WHERE name = 'GermanSchoolmarks' "
        )
        sqlapi.SQLupdate(
            "cdbpcs_rat_val SET name = 'Grades' WHERE name = 'GermanSchoolmarks' "
        )
        sqlapi.SQLupdate(
            "cdbpcs_rat_wght SET name = 'Grades' WHERE name = 'GermanSchoolmarks' "
        )


pre = []
post = [AdjustRatingSchemeOfChecklists]
