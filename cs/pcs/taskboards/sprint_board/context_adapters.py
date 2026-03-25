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


from cs.taskboard.interfaces.context_adapter import ContextAdapter


class SprintBoardProjectContextAdapter(ContextAdapter):
    @classmethod
    def get_header_dialog_name(cls):
        return "pcs_prj_sprint_taskboard_header"


class SprintBoardTaskContextAdapter(ContextAdapter):
    @classmethod
    def get_header_dialog_name(cls):
        return "pcs_task_sprint_taskboard_header"
