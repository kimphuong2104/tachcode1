#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Morepath app for Web UI user substitution

Provides the substitutions where the authenticated user currently is substitute.

Dates are returned in the users local timezone.
"""

from __future__ import absolute_import
import six
__revision__ = "$Id$"

from . import App, get_uisupport_app
import datetime
from cdb import auth, sqlapi, typeconversion
from cs.platform.web.rest.app import get_collection_app
from cs.platform.org.user import UserSubstitute, AbsencePeriod
from cdb.objects.org import User


def user_date_fmt(value):
    return typeconversion.to_user_repr_date_format(value, None, True) if value else ""


class UserSubstitutionCollection(object):

    @classmethod
    def make_link(cls, request):
        return request.class_link(UserSubstitutionCollection, app=get_uisupport_app(request))

    def to_json(self, request):
        now = sqlapi.SQLdbms_date(datetime.datetime.utcnow().date())
        cond_subst = """(substitute = '%s'
                      AND (period_start IS NULL OR period_start <= %s)
                      AND (period_end IS NULL OR period_end >= %s))""" % (sqlapi.quote(auth.persno), now, now)

        # get my substitutions cases
        absence_combined = {}
        substitutions = UserSubstitute.Query(condition=cond_subst)
        if substitutions:
            cond_abs = """(personalnummer in (%s)
                        AND (period_start IS NULL OR period_start <= %s)
                        AND (period_end IS NULL OR period_end >= %s))""" % (", ".join(["'%s'" % s.personalnummer for s in substitutions]), now, now)

            # match with absence periods
            absence = AbsencePeriod.Query(condition=cond_abs)
            for a in absence:
                ac = absence_combined.setdefault(a.personalnummer, {"period_start": a.period_start,
                                                                    "period_end": a.period_end})
                if not a.period_start:  # open begin
                    ac["period_start"] = a.period_start
                elif ac["period_start"] and ac["period_start"] > a.period_start:
                    ac["period_start"] = a.period_start

                if not a.period_end:  # open end
                    ac["period_end"] = a.period_end
                elif ac["period_end"] and ac["period_end"] < a.period_end:
                    ac["period_end"] = a.period_end

            for s in substitutions:
                ac = absence_combined.get(s.personalnummer)
                if ac:
                    if s.period_start and ac.get("period_start") and s.period_start > ac.get("period_start"):
                        ac["period_start"] = s.period_start
                    if s.period_end and ac.get("period_end") and s.period_end < ac.get("period_end"):
                        ac["period_end"] = s.period_end

        return {
            'substitutions': [{'user_link': request.class_link(User, {"keys": k},
                                                               app=get_collection_app(request)),
                               'start': user_date_fmt(v.get("period_start")),
                               'end': user_date_fmt(v.get("period_end")),
                               'persno': k
                               } for (k, v) in six.iteritems(absence_combined)],
        }


@App.path(path='user_substitution', model=UserSubstitutionCollection)
def _get_user_substitution_collection():
    return UserSubstitutionCollection()


@App.json(model=UserSubstitutionCollection)
def _user_substitution_collection_get(model, request):
    return model.to_json(request)
