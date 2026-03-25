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

from cdb import sqlapi, ddl


class DoingtoInProgress(object):
    def run(self):
        t = ddl.Table('cs_taskboard_column')
        if t.exists():
            # adjust board_type and board_api
            sqlapi.SQLupdate(
                "cs_taskboard_column SET title_en= 'In Progress' "
                "WHERE title_de = 'Bearbeitung'"
            )


pre = []
post = [DoingtoInProgress]
