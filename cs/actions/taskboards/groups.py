#!/usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2019 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
"""
This class is an interface for grouping actions on a taskboard
"""


__docformat__ = ""
__revision__ = "$Id: "


from cdb import rte, sig
from cs.taskboard.constants import GROUP_RESPONSIBLE
from cs.taskboard.groups import add_group_mapping, get_subject_group_context

from cs.actions import Action


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def register_groups():
    # Global group mappings
    add_group_mapping(
        Action._getClassname(),  # pylint: disable=protected-access
        {
            GROUP_RESPONSIBLE: get_subject_group_context,
        },
    )
