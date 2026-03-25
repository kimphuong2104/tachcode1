#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

from __future__ import absolute_import
__revision__ = "$Id$"

from cdb.comparch import protocol
from cdb import sqlapi


class FixLateWorkdayIndex(object):
    """Fix late workday index for all existing calendar profiles"""

    def run(self):
        from cs.calendar import CalendarProfile
        for cal_prof in CalendarProfile.Query():
            protocol.logMessage("Adjust late workday index for profile %s (%s)"
                                % (cal_prof.name, cal_prof.description))
            if sqlapi.SQLdbms() == sqlapi.DBMS_POSTGRES:
                upd = """cdb_calendar_entry
                SET late_work_idx = CASE WHEN day_type_id::int > 1 THEN early_work_idx +1 ELSE early_work_idx END
                WHERE calendar_profile_id = '{calendar_profile_id}'
                AND personalnummer IS NULL AND cdb_project_id IS NULL
                """.format(calendar_profile_id=cal_prof.cdb_object_id)
            else:
                upd = """cdb_calendar_entry
                SET late_work_idx = CASE WHEN day_type_id > 1 THEN early_work_idx +1 ELSE early_work_idx END
                WHERE calendar_profile_id = '{calendar_profile_id}'
                AND personalnummer IS NULL AND cdb_project_id IS NULL
                """.format(calendar_profile_id=cal_prof.cdb_object_id)
            sqlapi.SQLupdate(upd)


post = [FixLateWorkdayIndex]
