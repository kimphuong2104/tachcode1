#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
CONTACT Elements Update-Task
"""

from __future__ import absolute_import

import logging


class RebuildUserDefinedViews(object):
    """Fix wrong collations from user defined views"""

    def run(self):
        log = logging.getLogger(__name__)

        from cdb import sqlapi

        if sqlapi.SQLdbms() != sqlapi.DBMS_MSSQL:
            log.info("Not Microsoft SQL Server, nothing to do")
            return

        from cdb.mssql import CollationDefault
        from cdb.platform.mom.relations import DDUserDefinedView

        views = CollationDefault.find_wrong_collations()
        log.info("Found %d views or tables with wrong collation settings", len(views))
        for view in views:
            v = DDUserDefinedView.ByKeys(view.table_name)
            if v:
                log.debug("Rebuilding %s", view.table_name)
                v.rebuild()


pre = []
post = [RebuildUserDefinedViews]


if __name__ == "__main__":
    RebuildUserDefinedViews().run()
