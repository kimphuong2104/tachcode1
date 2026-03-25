#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2012 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

from __future__ import absolute_import

import six

from cdb import sig
from cdb import ue
from cdb import sqlapi
from cdb.classbody import classbody

from cdb.objects import Reference_1

from cdb.objects.org import Person
from cs.calendar import CalendarProfile


@classbody
class Person(object):

    CalendarProfile = Reference_1(CalendarProfile, Person.calendar_profile_id)

    @sig.connect(Person, 'create', 'pre')
    @sig.connect(Person, 'copy', 'pre')
    @sig.connect(Person, 'modify', 'pre')
    def _ensureCalendarProfile(self, ctx):
        if self.active_account == '1' and not self.calendar_profile_id:
            raise ue.Exception("cdb_cal_prof_mand")

    @classmethod
    @sig.connect(Person, list, "cdb_cal_prof_chg", "now")
    def cdb_cal_prof_chg_now(cls, ctx):
        MAX_ELEMS_IN_CLAUSE = 500
        list_of_groups = []
        # Split into distinct groups.
        list_of_persno = [obj.personalnummer for obj in ctx.objects]
        cutoffs = list(six.moves.range(0, len(list_of_persno), MAX_ELEMS_IN_CLAUSE)) + [len(list_of_persno)]
        for n in six.moves.range(len(cutoffs) - 1):
            list_of_groups.append(list_of_persno[cutoffs[n]:cutoffs[n + 1]])
        for pers_group in list_of_groups:
            persno_str = ", ".join(["'%s'" % sqlapi.quote(pers) for
                                    pers in pers_group])
            sqlapi.SQLupdate("angestellter SET calendar_profile_id = '%s' "
                             "WHERE personalnummer in ( %s )" %
                             (ctx.dialog.calendar_profile_id, persno_str))
