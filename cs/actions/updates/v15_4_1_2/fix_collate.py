#!/usr/bin/env powerscript
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2018 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#

"""
CONTACT Elements Update-Task
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import logging


class RebuildUserDefinedViews:
    """Fix wrong collations from user defined views"""

    def run(self):
        LOG = logging.getLogger(__name__)

        from cdb import sqlapi

        if sqlapi.SQLdbms() != sqlapi.DBMS_MSSQL:
            LOG.info("Not Microsoft SQL Server, nothing to do")
            return

        from cdb.mssql import CollationDefault
        from cdb.platform.mom.relations import DDUserDefinedView

        views = CollationDefault.find_wrong_collations()
        LOG.info("Found %d views or tables with wrong collation settings", len(views))
        for view in views:
            v = DDUserDefinedView.ByKeys(view.table_name)
            if v:
                LOG.debug("Rebuilding %s", view.table_name)
                v.rebuild()

        views = CollationDefault.find_wrong_collations()
        if views:
            LOG.warning(
                "Found %d views or tables still having wrong collation settings",
                len(views),
            )
