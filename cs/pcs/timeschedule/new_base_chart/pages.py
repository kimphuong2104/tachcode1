#!/usr/bin/env python
# -*- python -*- coding: utf-8 -*-
#
# Copyright (C) 2014 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/

__revision__ = "$Id$"

from cdb import auth, i18n
from cdb.objects import Forward
from cdb.objects.org import Person

from cs.pcs.timeschedule.new_base_chart import nanoroute

fCalendarProfile = Forward("cs.calendar.CalendarProfile")

router = nanoroute.LookUp()

# =======================
# handle data api request
# =======================


@router.json("settings")
def get_app_settings(_page):
    """
    Calendar setup
    If the current user does not have a valid calendar profile,
    the system first tries to use the default calendar profile.
    If no default calendar profile is defined, the cs.pcs default is used: All weekdays are workdays
    :return: {calendar exceptions, workdays, date format)
    :rtype: dict
    """
    current_user = Person.ByKeys(personalnummer=auth.persno)

    cp = current_user.CalendarProfile
    if not cp and current_user.DefaultCalendarProfileName:
        cp = fCalendarProfile.get_by_name(current_user.DefaultCalendarProfileName)

    cal_excs = {}
    workdays = current_user.default_work_days

    if cp:
        cal_excs = dict(
            [
                (e.day.strftime("%d.%m.%Y"), int(e.day_type_id) == 1)
                for e in cp.Exceptions
            ]
        )
        workdays = {
            "1": int(cp.mo_type_id) == 1,
            "2": int(cp.tu_type_id) == 1,
            "3": int(cp.we_type_id) == 1,
            "4": int(cp.th_type_id) == 1,
            "5": int(cp.fr_type_id) == 1,
            "6": int(cp.sa_type_id) == 1,
            "7": int(cp.su_type_id) == 1,
        }

    settings = {
        "calendar_exceptions": cal_excs,
        "workdays": workdays,
        "date_format": i18n.get_date_format(),
    }
    return settings
