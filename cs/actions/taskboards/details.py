# -*- mode: python; coding: utf-8 -*-
#
# Copyright (C) 1990 - 2022 CONTACT Software GmbH
# All rights reserved.
# http://www.contact-software.com
#

"""
This class is an interface to display information about
actions in the browser on a mask.
"""


__revision__ = "$Id: "
__docformat__ = "restructuredtext en"

import os

from cdb import rte, sig
from cdb.comparch.modules import get_module_dir

try:
    from cs.taskboard.details import add_detail
except ImportError:
    add_detail = None

from cs.actions import Action


@sig.connect(rte.APPLICATIONS_LOADED_HOOK)
def register_details():
    if add_detail:
        base_dir = get_module_dir("cs.actions")
        # Global detail mappings
        add_detail(
            Action._getClassname(),  # pylint: disable=protected-access
            os.path.join(base_dir, "taskboards", "views", "detail_cdb_action.json"),
        )
