#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from __future__ import absolute_import
import six
__revision__ = "$Id$"

from cdb import sqlapi


class CreateDashboardPositions(object):
    """
    Enumerate the dashboard positions for all users.
    """
    def run(self):
        owners = sqlapi.SQLselect("DISTINCT owner FROM csweb_dashboard")

        for idx in six.moves.range(sqlapi.SQLrows(owners)):
            dashboards = sqlapi.RecordSet2('csweb_dashboard', "owner='%s'"
                                           % sqlapi.quote(owners.get_string("owner", idx)))
            for idx, db in enumerate(dashboards):
                db.update(position_index=idx)


pre = []
post = [CreateDashboardPositions]
