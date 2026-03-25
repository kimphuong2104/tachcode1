# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2020 CONTACT Software GmbH
# All rights reserved.
# https://www.contact-software.com/

"""
CONTACT Elements Update-Task
"""


__docformat__ = "restructuredtext en"
__revision__ = "$Id$"

import logging


class RebuildUserDefinedViews:
    """
    Rebuild the database view 'cdb_action_resp_brows'
    """

    def run(self):
        LOG = logging.getLogger(__name__)

        from cdb.platform.mom.relations import DDUserDefinedView

        table_name = "cdb_action_resp_brows"
        t = DDUserDefinedView.ByKeys(table_name)
        if t:
            LOG.debug("Rebuilding %s", table_name)
            t.rebuild()


pre = []
post = [RebuildUserDefinedViews]
