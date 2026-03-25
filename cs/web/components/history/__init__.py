#!/usr/bin/env powerscript
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2016 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
Web UI history of visited objects
"""

from __future__ import absolute_import
__revision__ = "$Id$"

from cdb.util import PersonalSettings


def get_history_size():
    """
    Returns the maximum number of objects to be stored in the history.
    """
    return int(PersonalSettings().getValueOrDefault("csweb.max_history_objs",
                                                    "", "25"))


def get_history_entries_per_class():
    """
    Returns the maximum number of objects of the same class to be stored
    in the history.
    """
    return int(PersonalSettings().getValueOrDefault("csweb.history_objs_per_class",
                                                    "", "20"))
