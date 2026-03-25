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


from cdb import rte, sig, util
from cs.taskboard.groups import add_group

GROUP_TASK = "Task"


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def register_groups():
    add_group(GROUP_TASK, util.Labels()["cs_pcs_taskboards_label_task"])
