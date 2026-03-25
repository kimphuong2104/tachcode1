#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2013 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import
__revision__ = "$Id$"

from cdb.comparch import protocol


class GenerateCalendarEntries(object):

    def run(self):
        from cs.calendar import CalendarProfile
        for cal_prof in CalendarProfile.Query():
            protocol.logMessage("Generate calendar entries for profile %s (%s)"
                                % (cal_prof.name, cal_prof.description))
            cal_prof.generateBaseCalendar()
            protocol.logMessage("Generate workday index for profile %s (%s)"
                                % (cal_prof.name, cal_prof.description))
            cal_prof.generateWorkdayIndex()


post = [GenerateCalendarEntries]
