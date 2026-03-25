#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

from __future__ import absolute_import
__revision__ = "$Id$"

from cdb import sqlapi


class DropOldSearchEntries(object):
    """ Drop unnecessary search settings.
    """
    def run(self):
        rs = sqlapi.RecordSet2("cdb_usr_setting", "setting_id='cs.web.search' and setting_id2='last_search_settings'")
        for r in rs:
            r.delete()


pre = []
post = [DropOldSearchEntries]
